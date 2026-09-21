from typing import List, Dict, Any
import sqlite3
import re
import json
# ----------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------
from pathlib import Path
_DB_PATH = str(Path(__file__).resolve().parent.parent / "storage" / "support_copilot.db")

def _conn() -> sqlite3.Connection:
    """Create a new SQLite connection with Row factory."""
    conn = sqlite3.connect(_DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


# ----------------------------------------------------------------------
# Generic database access
# ----------------------------------------------------------------------
def _shrink_rows(rows, max_field=400, max_chars=30000):
    """Cut long text fields and cap total size. Returns (rows, truncated)."""
    out, total, truncated = [], 0, False
    for row in rows:
        row = {
            k: (v[:max_field] + "…[cut]" if isinstance(v, str) and len(v) > max_field else v)
            for k, v in row.items()
        }
        size = len(json.dumps(row, ensure_ascii=False, default=str))
        if total + size > max_chars:
            truncated = True
            break
        out.append(row)
        total += size
    return out, truncated
_SCHEMA_CACHE = None  # Global cache for schema


_COLUMN_MEANINGS = {
    ("freshdesk_tickets", "relates_to"): {
        "description": "The PSA module or product category this issue relates to, as set by support team members. Consider this as a strong signal for the ticket's category, but combine it with your own reasoning of the subject/description when categorizing issues.",
        "semantic_type": "category",
    },
    ("freshdesk_tickets", "internal_status"): {
        "description": "Internal escalation/workflow state. Separate from `status`; never put internal_status values in a status filter.",
        "semantic_type": "workflow_state",
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


def query_database(sql: str) -> Dict[str, Any]:
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


    # ------------------------------------------------------------------
    # Execute the query
    # ------------------------------------------------------------------
    with _conn() as conn:
        conn.execute("PRAGMA query_only = ON")
        # Let SQLite validate every referenced column, including columns used
        # in WHERE, JOIN, GROUP BY, ORDER BY, and HAVING clauses.
        try:
            conn.execute(f"EXPLAIN QUERY PLAN {sql.rstrip(';')}")
            cursor = conn.execute(sql)
        except sqlite3.OperationalError as exc:
            if "no such column" in str(exc).lower():
                raise ValueError(
                    f"{exc}. Retry with an exact column name from the schema; "
                    "do not substitute a guessed field."
                ) from exc
            raise
        rows = [dict(r) for r in cursor.fetchmany(101)]
        row_capped = len(rows) > 100
        rows, size_capped = _shrink_rows(rows[:100])
        result = {"results": rows, "row_count": len(rows)}
        if row_capped or size_capped:
            result["truncated"] = True
            result["note"] = (
                "Result was cut; row_count is NOT a total. Use COUNT(*)/GROUP BY, "
                "add filters, or select fewer columns."
            )
        return result


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
        for col in schema.get("freshdesk_tickets", []):
            if col["type"].upper() != "TEXT" or col["name"].lower() in {"subject", "description_text"}:
                continue
            vals = [
                r[0] for r in conn.execute(
                    f'SELECT DISTINCT "{col["name"]}" FROM freshdesk_tickets '
                    f'WHERE "{col["name"]}" IS NOT NULL LIMIT 31'
                ).fetchall()
            ]
            if len(vals) <= 30:
                col["valid_values"] = vals
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
            {"name": "public_agent_reply", "meaning": "freshdesk_conversations.incoming = 0 AND private = 0"},
            {"name": "public_customer_comment", "meaning": "freshdesk_conversations.incoming = 1 AND private = 0"},
            {"name": "private_note", "meaning": "freshdesk_conversations.private = 1 (any incoming value)"},
            {
                "name": "no_comment_author",
                "meaning": "Conversations have no author column. Never name who wrote a comment; say 'an agent reply' unless the body is signed.",
            },
            {
                "name": "last_comment",
                "meaning": "Default = any comment (public or private, agent or customer). Compute in SQL, never by reading all conversations: "
                           "FROM freshdesk_tickets t LEFT JOIN freshdesk_conversations c ON c.ticket_id = t.id "
                           "AND c.created_at = (SELECT MAX(created_at) FROM freshdesk_conversations WHERE ticket_id = t.id)",
            },
            {
                "name": "last_public_comment",
                "meaning": "Only when the user says 'public'. Same pattern as last_comment, adding 'AND c.private = 0' to the JOIN and 'AND private = 0' inside the subquery.",
            },
            {
                "name": "last_customer_comment",
                "meaning": "Only when the user says 'by the client/customer'. Same pattern, adding 'AND c.incoming = 1 AND c.private = 0' to the JOIN and 'AND incoming = 1 AND private = 0' inside the subquery.",
            },
            {
                "name": "missed_follow_up",
                "meaning": "followup_by is in the past and no qualifying agent conversation exists after that date",
            },
            {"name": "active_ticket", "meaning": "status NOT IN ('Resolved', 'Closed')"},
            {
                "name": "missing_values",
                "meaning": "NULL/empty fields (e.g. relates_to not set by the agent) are data. Never filter them out unless the user asks; "
                           "include them as 'Not set' (e.g. COALESCE(relates_to, 'Not set')) with their count.",
            },
            {
                "name": "category_breakdown",
                "meaning": "For questions about categories, GROUP BY COALESCE(relates_to, 'Not set') with COUNT(*). "
                           "If 'Not set' tickets exist, say how many and offer to suggest a category for them from subject/description. "
                           "Only infer when the user agrees, using a short list of those tickets. State that inferred categories are suggestions.",
            },
            {
                "name": "escalated_to_rd",
                "meaning": "Currently escalated to R&D: status NOT IN ('Resolved','Closed') AND (status = 'On-Hold (Escalated)' "
                           "OR internal_status IN ('Escalated -> Development In Progress','Escalation Complete','Escalated -> Development Deferred')). "
                           "Use exact internal_status values; never put them in the status filter.",
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
        if isinstance(ticket_data.get("description_text"), str):
            ticket_data["description_text"] = ticket_data["description_text"][:1500]
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
        rows, _ = _shrink_rows([dict(row) for row in cursor.fetchall()], max_field=300)
        return rows



# ----------------------------------------------------------------------
# Retrieve all conversations belonging to a ticket
# ----------------------------------------------------------------------
def get_conversations_for_ticket(ticket_id: int) -> List[Dict[str, Any]]:
    """Return conversations for a ticket, oldest first. Newest are kept if size-capped."""
    with _conn() as conn:
        cursor = conn.execute(
            """
            SELECT *
            FROM Freshdesk_conversations
            WHERE ticket_id = ?
            ORDER BY created_at DESC
            """,
            (ticket_id,),
        )
        rows = [dict(row) for row in cursor.fetchall()]
    rows, truncated = _shrink_rows(rows, max_field=1500, max_chars=60000)
    rows.reverse()
    if truncated:
        rows.insert(0, {"note": "Older conversations omitted for size; only the newest are shown."})
    return rows


def invalidate_schema_cache() -> None:
    """Call after a sync so valid values refresh."""
    global _SCHEMA_CACHE
    _SCHEMA_CACHE = None