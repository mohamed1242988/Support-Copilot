from typing import List, Dict, Any
import sqlite3
import re

# ----------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------
_DB_PATH = "c:/AI Project/SupportCopilot/storage/support_copilot.db"


def _conn() -> sqlite3.Connection:
    """Create a new SQLite connection with Row factory."""
    conn = sqlite3.connect(_DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


# ----------------------------------------------------------------------
# Generic database access
# ----------------------------------------------------------------------
_SCHEMA_CACHE = None  # Global cache for schema


_COLUMN_MEANINGS = {
    ("freshdesk_tickets", "relates_to"): {
        "description": "The PSA module or product category this issue relates to, as set by support team members. Consider this as a strong signal for the ticket's category, but combine it with your own reasoning of the subject/description when categorizing issues.",
        "semantic_type": "category",
    },
    ("freshdesk_tickets", "followup_by"): {
        "description": "Date by which the assigned agent promised a follow-up.",
        "semantic_type": "follow_up_deadline",
    },
    ("freshdesk_tickets", "created_at"): {
        "description": "When the Freshdesk ticket was created.",
        "semantic_type": "timestamp",
    },
    ("freshdesk_tickets", "updated_at"): {
        "description": "Last ticket record update; may include changes unrelated to conversations.",
        "semantic_type": "timestamp",
    },
    ("freshdesk_conversations", "created_at"): {
        "description": "When the conversation or note was created; use this to verify an actual update.",
        "semantic_type": "timestamp",
    },
    ("freshdesk_conversations", "incoming"): {
        "description": "Whether the message came from the customer; 0 means agent-authored.",
        "semantic_type": "message_direction",
    },
    ("freshdesk_conversations", "private"): {
        "description": "Whether the message is private; 0 means public reply and 1 means internal note.",
        "semantic_type": "visibility",
    },
}


def query_database(sql: str) -> List[Dict[str, Any]]:
    """
    Execute a READ‑ONLY SQL query with schema validation.

    - Only SELECT / WITH statements are permitted.
    - Enforces a default row limit of 100 (can be overridden with an explicit LIMIT).
    - Validates referenced tables and columns against the cached schema.
    - Auto‑rewrites `=` on ``customer_name`` / ``company_name`` to a ``LIKE '%value%'`` pattern.
    """
    # Basic statement type check
    sql_clean = sql.strip().lower()
    if not (sql_clean.startswith("select") or sql_clean.startswith("with")):
        raise ValueError("Only SELECT or WITH queries are allowed.")

    # Disallow forbidden keywords
    forbidden = [
        "insert ",
        "update ",
        "delete ",
        "drop ",
        "alter ",
        "create ",
        "replace ",
        "attach ",
        "detach ",
    ]
    for keyword in forbidden:
        keyword_name = keyword.strip()
        if re.search(rf"(?<![\w.]){re.escape(keyword_name)}\b", sql_clean):
            raise ValueError(f"Forbidden SQL operation: {keyword_name}")

    # ------------------------------------------------------------------
    # Auto‑rewrite exact equality on name columns to a LIKE pattern.
    # Allows callers to write e.g. WHERE customer_name = 'Acme' and have it
    # safely transformed to WHERE customer_name LIKE '%Acme%'.
    # ------------------------------------------------------------------
    sql = re.sub(
        r"(?i)\b(customer_name|company_name|assigned_agent)\b\s*=\s*'([^']*)'",
        r"\1 LIKE '%\2%'",
        sql,
    )
    sql = re.sub(
        r'(?i)\b(customer_name|company_name|assigned_agent)\b\s*=\s*"([^"]*)"',
        r"\1 LIKE '%\2%'",
        sql,
    )

    # SQLite equality is case-sensitive for ordinary TEXT columns. Apply
    # NOCASE to quoted text comparisons so filters such as priority = 'urgent'
    # also match values stored as 'Urgent' or 'URGENT'.
    sql = re.sub(
        r"(?i)(\b[\w.]+\b)\s*(COLLATE\s+NOCASE\s*)?(=|!=|<>)\s*('(?:''|[^'])*'|\"(?:\"\"|[^\"])*\")",
        r"\1 COLLATE NOCASE \3 \4",
        sql,
    )

    # Load (and cache) schema for validation
    schema_obj = get_database_schema()
    tables_schema = schema_obj["tables"]

    # ------------------------------------------------------------------
    # Validate referenced tables
    # ------------------------------------------------------------------
    table_names = re.findall(r"(?:from|join)\s+([`\"']?\w+[`\"']?)", sql, flags=re.IGNORECASE)
    for tbl in table_names:
        tbl_clean = tbl.strip('`"\'')
        if tbl_clean.lower() not in {name.lower() for name in tables_schema}:
            raise ValueError(
                f"Referenced table '{tbl_clean}' does not exist in the database schema."
            )

    # ------------------------------------------------------------------
    # Validate referenced columns (lightweight + wildcard support)
    # ------------------------------------------------------------------
    select_match = re.search(
        r"select\s+(.*?)\s+from",
        sql,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if select_match:
        cols_section = select_match.group(1).strip()
        # If the user asked for the wildcard, skip column validation entirely.
        if cols_section == "*":
            pass  # ok – everything is selected
        else:
            cols = [c.strip() for c in cols_section.split(",")]
            for col in cols:
                # Allow qualified wildcards like ``t.*`` – treat them as ok.
                if col.endswith(".*"):
                    continue
                # Skip function calls (e.g. COUNT(*))
                if "(" in col:
                    continue
                col_name = col.split(".")[-1]
                # Case‑insensitive check against schema column names
                col_name_lower = col_name.lower()
                if not any(
                    col_name_lower == c["name"].lower()
                    for cols_list in tables_schema.values()
                    for c in cols_list
                ):
                    raise ValueError(f"Column '{col_name}' not found in any known table.")

    # Ensure a sensible row limit (default 100) if not explicitly set
    if "limit" not in sql_clean:
        sql = f"{sql.rstrip(';')} LIMIT 100;"

    # ------------------------------------------------------------------
    # Execute the query
    # ------------------------------------------------------------------
    with _conn() as conn:
        # Let SQLite validate every referenced column, including columns used
        # in WHERE, JOIN, GROUP BY, ORDER BY, and HAVING clauses.
        try:
            conn.execute(f"EXPLAIN QUERY PLAN {sql.rstrip(';')}")
            cursor = conn.execute(sql)
        except sqlite3.OperationalError as exc:
            if "no such column" in str(exc).lower():
                raise ValueError(
                    f"{exc}. Use get_database_schema and retry with an exact column name; "
                    "do not substitute a guessed field."
                ) from exc
            raise
        rows = cursor.fetchmany(100)  # enforce max rows
        return [dict(row) for row in rows]


# ----------------------------------------------------------------------
# Database schema extraction & caching
# ----------------------------------------------------------------------
def get_database_schema() -> Dict[str, Any]:
    """
    Return a cleaned database schema.

    - Excludes internal FTS and SQLite meta tables.
    - Provides a short description for each column (derived from the column name).
    - Includes a ``relationships`` list that describes foreign‑key links.
    - Result is cached in ``_SCHEMA_CACHE`` for fast reuse.
    """
    global _SCHEMA_CACHE
    if _SCHEMA_CACHE is not None:
        return _SCHEMA_CACHE

    with _conn() as conn:
        # Pull all user tables excluding SQLite internal tables.
        tables = conn.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
              AND name NOT LIKE 'sqlite_%'
            ORDER BY name
            """
        ).fetchall()

        schema: Dict[str, List[Dict[str, Any]]] = {}
        for table_row in tables:
            table_name = table_row["name"]
            # Skip full‑text search helper tables (they have no useful business data).
            if table_name.startswith("freshdesk_fts") or table_name.startswith("jira_fts"):
                continue

            # Retrieve column info for this table
            columns = conn.execute(f"PRAGMA table_info('{table_name}')").fetchall()
            # Build a simple description from the column name (can be expanded later).
            schema[table_name] = [
                {
                    "name": column["name"],
                    "type": column["type"],
                    "primary_key": bool(column["pk"]),
                    **_COLUMN_MEANINGS.get(
                        (table_name.lower(), column["name"].lower()),
                        {
                            "description": f"{column['name']}: {column['name'].replace('_', ' ')}",
                        },
                    ),
                }
                for column in columns
            ]

        # Define explicit relationships that the model can rely on.
        relationships = [
            {
                "from_table": "freshdesk_conversations",
                "from_column": "ticket_id",
                "to_table": "freshdesk_tickets",
                "to_column": "id",
                "meaning": "Conversation history belonging to a Freshdesk ticket.",
            },
            {
                "from_table": "jira_comments",
                "from_column": "issue",
                "to_table": "jira_issues",
                "to_column": "key",
                "meaning": "Comments belonging to a Jira issue.",
            },
        ]

        business_rules = [
            {
                "name": "agent_conversation",
                "meaning": "freshdesk_conversations.incoming = 0",
            },
            {
                "name": "customer_conversation",
                "meaning": "freshdesk_conversations.incoming = 1",
            },
            {
                "name": "public_agent_reply",
                "meaning": "freshdesk_conversations.incoming = 0 AND freshdesk_conversations.private = 0",
            },
            {
                "name": "internal_agent_note",
                "meaning": "freshdesk_conversations.incoming = 0 AND freshdesk_conversations.private = 1",
            },
            {
                "name": "missed_follow_up",
                "meaning": "followup_by is in the past and no qualifying agent conversation exists after that date",
            },
            {
                "name": "active_ticket",
                "meaning": "status is not Resolved or Closed",
            },
        ]

        _SCHEMA_CACHE = {
            "tables": schema,
            "relationships": relationships,
            "business_rules": business_rules,
        }
        return _SCHEMA_CACHE


# ----------------------------------------------------------------------
# Helper: ensure the ``alias`` column + index exist on ``customers``
# ----------------------------------------------------------------------
def _ensure_alias_column() -> None:
    """Create the ``alias`` column on ``customers`` if it does not exist."""
    with _conn() as conn:
        cols = [c["name"] for c in conn.execute('PRAGMA table_info(customers)')]
        if "alias" not in cols:
            conn.execute('ALTER TABLE customers ADD COLUMN alias TEXT')
            conn.commit()
        # Index for fast LIKE queries on the new column
        conn.execute('CREATE INDEX IF NOT EXISTS idx_customers_alias ON customers(alias)')
        conn.commit()


# Run the column creation when the module is imported
_ensure_alias_column()


# ----------------------------------------------------------------------
# Freshdesk ticket helpers
# ----------------------------------------------------------------------
def get_ticket_by_id(ticket_id: int) -> Dict[str, Any]:
    """Return a single ticket row along with its conversations (or an error dict if not found)."""
    with _conn() as conn:
        row = conn.execute(
            """
            SELECT *
            FROM freshdesk_tickets
            WHERE id = ?
            """,
            (ticket_id,),
        ).fetchone()

        if not row:
            return {"error": f"Ticket {ticket_id} not found"}
        
        ticket_data = dict(row)
        ticket_data["conversations"] = get_conversations_for_ticket(ticket_id)
        return ticket_data


# ----------------------------------------------------------------------
# Specialized Freshdesk full‑text search
# ----------------------------------------------------------------------
def search_tickets(query: str) -> List[Dict[str, Any]]:
    """
    Execute a full‑text search against the ``Freshdesk_fts`` virtual table.

    The caller supplies the raw query string; no extra ``WHERE`` clause guards are needed.
    """
    # ------------------------------------------------------------------
    # Pre‑process natural‑language query into FTS‑compatible MATCH expression
    # ------------------------------------------------------------------
    # 1️⃣  Normalise: lower‑case and strip punctuation
    cleaned = re.sub(r"[^\w\s]", " ", query.lower())
    # 2️⃣  Remove generic time‑phrases that are not indexed
    tokens = [t for t in cleaned.split() if t not in {"last", "month", "months", "recent", "issues", "autodesk"}]
    # 3️⃣  Build MATCH: OR between remaining tokens (or fallback to the whole string)
    if tokens:
        match_expr = " OR ".join(f'"{t}"' for t in tokens)
    else:
        match_expr = f'"{cleaned.strip()}"'

    with _conn() as conn:
        cursor = conn.execute(
            """
            SELECT *
            FROM Freshdesk_fts
            WHERE Freshdesk_fts MATCH ?
            ORDER BY rank
            LIMIT 50
            """,
            (match_expr,),
        )
        return [dict(row) for row in cursor.fetchall()]



# ----------------------------------------------------------------------
# Retrieve all conversations belonging to a ticket
# ----------------------------------------------------------------------
def get_conversations_for_ticket(ticket_id: int) -> List[Dict[str, Any]]:
    """Return the list of `Freshdesk_conversations` for the given ticket."""
    with _conn() as conn:
        cursor = conn.execute(
            """
            SELECT *
            FROM Freshdesk_conversations
            WHERE ticket_id = ?
            ORDER BY created_at ASC
            """,
            (ticket_id,),
        )
        return [dict(row) for row in cursor.fetchall()]