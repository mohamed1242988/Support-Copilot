import pathlib
# import moved inside function to avoid circular import
import sqlite3
import re
import math


DATABASE_PATH = (
    pathlib.Path(__file__).resolve().parent /
    "support_copilot.db"
)



def get_connection():
    """
    Creates and returns a SQLite database connection.
    """
    return sqlite3.connect(DATABASE_PATH)

# ----------------------------------------------------------------------
# Text Mappings
# ----------------------------------------------------------------------
STATUS_MAP = {
    2: "Open",
    3: "Pending",
    4: "Resolved",
    5: "Closed",
    6: "On-Hold (Escalated)",
}

PRIORITY_MAP = {
    1: "Low",
    2: "Medium",
    3: "High",
    4: "Urgent",
}


def _join_fields(items, sep=" -> "):
    """Joins non-empty string values with an arrow separator."""
    valid = [str(x).strip() for x in items if x is not None and str(x).strip()]
    return sep.join(valid) if valid else None


def _ensure_freshdesk_columns(connection):
    """Auto-adds new columns to freshdesk_tickets if missing."""
    existing = [row[1] for row in connection.execute("PRAGMA table_info(freshdesk_tickets)").fetchall()]
    new_cols = {
        "type": "TEXT",
        "relates_to": "TEXT",
        "internal_status": "TEXT",
        "jira_ticket_id": "TEXT",
        "assigned_agent": "TEXT",
        "followup_by": "TEXT",
        "resolution_category": "TEXT",
        "resolution_summary": "TEXT",
        "tags": "TEXT",
    }
    for col_name, col_type in new_cols.items():
        if col_name not in existing:
            connection.execute(f"ALTER TABLE freshdesk_tickets ADD COLUMN {col_name} {col_type}")
    connection.commit()


def initialize_database():
    """
    Creates database tables if they do not already exist.
    """

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS freshdesk_tickets (
            id INTEGER PRIMARY KEY,
            subject TEXT,
            description_text TEXT,
            status TEXT,
            priority TEXT,
            created_at TEXT,
            updated_at TEXT,
            Customer_ID INTEGER,
            Customer_Name TEXT,
            type TEXT,
            relates_to TEXT,
            internal_status TEXT,
            jira_ticket_id TEXT,
            assigned_agent TEXT,
            followup_by TEXT,
            resolution_category TEXT,
            resolution_summary TEXT,
            tags TEXT
        )
        """
    )

    _ensure_freshdesk_columns(connection)

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS freshdesk_conversations (
            id INTEGER PRIMARY KEY,
            ticket_id INTEGER,
            body_text TEXT,
            incoming BOOLEAN,
            private BOOLEAN,
            created_at TEXT,

            FOREIGN KEY(ticket_id)
            REFERENCES freshdesk_tickets(id)
        )
        """
    )

    cursor.execute(
        """
		CREATE VIRTUAL TABLE IF NOT EXISTS freshdesk_fts
		USING fts5(
		document_id UNINDEXED,
		document_type UNINDEXED,
		title,
		content
		)
		"""
	)

    

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS jira_issues (
        key TEXT PRIMARY KEY,
        project TEXT NOT NULL,
        summary TEXT,
        description TEXT,
        status TEXT,
        created_at TEXT,
        updated_at TEXT
        )
        """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS jira_comments (
        id TEXT PRIMARY KEY,
        issue_key TEXT NOT NULL,
        author TEXT,
        body TEXT,
        created_at TEXT,
        FOREIGN KEY(issue_key)
            REFERENCES jira_issues(key)
            ON DELETE CASCADE
        )
        """)

    cursor.execute(
        """
		CREATE VIRTUAL TABLE IF NOT EXISTS jira_fts
		USING fts5(
		document_id UNINDEXED,
		document_type UNINDEXED,
		title,
		content
		)
		"""
	)


    cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS sync_state (
                key TEXT PRIMARY KEY,
                value TEXT
            )
            """
        )

    connection.commit()
    connection.close()


def get_customer(customer_id):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT Freshdesk_ID, Name
        FROM customers
        WHERE Freshdesk_ID = ?
        """,
        (customer_id,)
    )

    customer = cursor.fetchone()

    connection.close()

    return customer

def save_ticket(ticket):
    """
    Inserts or updates a ticket with extended fields.
    """

    connection = get_connection()
    _ensure_freshdesk_columns(connection)
    cursor = connection.cursor()

    cf = ticket.get("custom_fields") or {}

    relates_to = _join_fields([cf.get("cf_psa_relates_to"), cf.get("cf_psa_relates_to_l2")])
    internal_status = _join_fields([cf.get("cf_internal_status"), cf.get("cf_internal_status_l2")])
    resolution_cat = _join_fields([
        cf.get("cf_resolution_category_l1"),
        cf.get("cf_resolution_category_l2"),
        cf.get("cf_resolution_category_l3")
    ])

    tags_list = ticket.get("tags") or []
    tags_str = ", ".join(tags_list) if isinstance(tags_list, list) else str(tags_list)

    # Convert numeric status & priority to human-readable text
    raw_status = ticket.get("status")
    status_text = STATUS_MAP.get(raw_status, str(raw_status)) if isinstance(raw_status, int) else raw_status

    raw_priority = ticket.get("priority")
    priority_text = PRIORITY_MAP.get(raw_priority, str(raw_priority)) if isinstance(raw_priority, int) else raw_priority

    # Import lazily to avoid circular import
    from integrations.freshdesk import get_agent_name
    # Determine assigned agent name using the new column
    assigned_agent_name = ticket.get("assigned_agent") or (
        get_agent_name(ticket.get("responder_id"))
        if ticket.get("responder_id")
        else None
    )


    cursor.execute(
        """
        INSERT OR REPLACE INTO freshdesk_tickets (
            id,
            subject,
            description_text,
            status,
            priority,
            created_at,
            updated_at,
            Customer_ID,
            Customer_Name,
            type,
            relates_to,
            internal_status,
            jira_ticket_id,
            assigned_agent,
            followup_by,
            resolution_category,
            resolution_summary,
            tags
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            ticket["id"],
            ticket.get("subject"),
            ticket.get("description_text"),
            status_text,
            priority_text,
            ticket.get("created_at"),
            ticket.get("updated_at"),
            ticket.get("customer_id"),
            ticket.get("customer_name"),
            ticket.get("type"),
            relates_to,
            internal_status,
            cf.get("cf_jira_ticket_id"),
            assigned_agent_name,
            cf.get("cf_followup_by"),
            resolution_cat,
            cf.get("cf_resolution_summary"),
            tags_str,
        )
    )

    cursor.execute(
        """
        DELETE FROM freshdesk_fts
        WHERE document_id = ? AND document_type = 'ticket'
        """,
        (ticket["id"],)
    )

    desc_text = ticket.get("description_text") or ""
    res_summary = cf.get("cf_resolution_summary") or ""
    fts_content = f"{desc_text} | Resolution: {res_summary} | Tags: {tags_str}"

    cursor.execute(
        """
        INSERT INTO freshdesk_fts (
            document_id,
            document_type,
            title,
            content
        )
        VALUES (?, 'ticket', ?, ?)
        """,
        (
            ticket["id"],
            ticket.get("subject"),
            fts_content
        )
    )

    connection.commit()
    connection.close()


def save_conversations(ticket_id, conversations):
    """
    Replaces conversations belonging to a ticket.
    """

    connection = get_connection()
    cursor = connection.cursor()

    # Remove existing FTS entries for this ticket's conversations
    cursor.execute(
        """
        DELETE FROM freshdesk_fts
        WHERE document_id IN (
            SELECT id
            FROM freshdesk_conversations
            WHERE ticket_id = ?
        )
        AND document_type = 'conversation'
        """,
        (ticket_id,)
    )

    # Remove existing conversations
    cursor.execute(
        "DELETE FROM freshdesk_conversations WHERE ticket_id = ?",
        (ticket_id,)
    )

    # Insert conversations and update FTS
    for conversation in conversations:

        cursor.execute(
            """
            INSERT INTO freshdesk_conversations (
                id,
                ticket_id,
                body_text,
                incoming,
                private,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                conversation["id"],
                ticket_id,
                conversation["body_text"],
                conversation["incoming"],
                conversation["private"],
                conversation["created_at"]
            )
        )

        cursor.execute(
            """
            INSERT INTO freshdesk_fts (
                document_id,
                document_type,
                title,
                content
            )
            VALUES (?, 'conversation', ?, ?)
            """,
            (
                conversation["id"],
                "",
                conversation["body_text"]
            )
        )

    connection.commit()
    connection.close()


def get_sync_state(key):
    """
    Retrieves a synchronization value.
    """

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT value
        FROM sync_state
        WHERE key = ?
        """,
        (key,)
    )

    result = cursor.fetchone()

    connection.close()

    if result:
        return result[0]

    return None


def update_sync_state(key, value):
    """
    Inserts or updates a synchronization value.
    """

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT OR REPLACE INTO sync_state (
            key,
            value
        )
        VALUES (?, ?)
        """,
        (
            key,
            value
        )
    )

    connection.commit()
    connection.close()


STOP_WORDS = {
    "a", "an", "the", "and", "or", "is", "are", "to", "of",
    "for", "in", "on", "with", "from", "by"
}

def prepare_search_terms(query: str) -> list[str]:
    tokens = re.findall(r"[A-Za-z0-9_.-]+", query.lower())

    return [
        token
        for token in tokens
        if token not in STOP_WORDS and len(token) >= 2
    ]

def build_fts_retrieval_stages(
    cursor,
    fts_table: str,
    document_type: str,
    terms: list[str],
) -> tuple[list[tuple[str, str, list[str]]], dict[str, dict[str, float | int]]]:
    """Build strict-to-broad FTS queries and their corpus statistics."""

    quoted_terms = [f'"{term}"' for term in terms]
    all_terms_query = " AND ".join(quoted_terms)
    stages = [("all_terms", all_terms_query, [])]

    cursor.execute(
        f"SELECT COUNT(*) FROM {fts_table} WHERE document_type = ?",
        (document_type,),
    )
    total_documents = cursor.fetchone()[0]

    term_frequencies = []
    term_statistics = {}
    for index, term in enumerate(terms):
        cursor.execute(
            f"""
            SELECT COUNT(*)
            FROM {fts_table}
            WHERE document_type = ?
            AND {fts_table} MATCH ?
            """,
            (document_type, f'"{term}"'),
        )
        document_count = cursor.fetchone()[0]
        idf = math.log((total_documents + 1) / (document_count + 1)) + 1
        term_statistics[term] = {
            "document_frequency": document_count,
            "idf": round(idf, 4),
        }

        if document_count > 0:
            term_frequencies.append((document_count, index, term))

    anchor_terms = [
        term
        for _, _, term in sorted(term_frequencies)
    ]

    for size, stage_name in ((3, "anchor_three_terms"), (2, "anchor_two_terms")):
        if len(anchor_terms) < size:
            continue

        anchor_query = " AND ".join(
            f'"{term}"'
            for term in anchor_terms[:size]
        )
        if anchor_query != all_terms_query:
            stages.append((stage_name, anchor_query, anchor_terms[:size]))

    stages.append(("fallback_or", " OR ".join(quoted_terms), []))
    return stages, term_statistics

def get_ticket(ticket_id):
    """
    Retrieves one ticket and its conversations.
    """

    connection = get_connection()
    connection.row_factory = sqlite3.Row

    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT *
        FROM freshdesk_tickets
        WHERE id = ?
        """,
        (ticket_id,)
    )

    ticket = cursor.fetchone()

    if not ticket:
        connection.close()
        return None

    ticket = dict(ticket)

    cursor.execute(
        """
        SELECT *
        FROM freshdesk_conversations
        WHERE ticket_id = ?
        ORDER BY created_at
        """,
        (ticket_id,)
    )

    ticket["conversations"] = [
        dict(row)
        for row in cursor.fetchall()
    ]

    connection.close()

    return ticket


def search_local_tickets(query, limit=50, exclude_ticket_id=None):
    """
    Searches local Freshdesk tickets using FTS5.
    """

    connection = get_connection()
    connection.row_factory = sqlite3.Row
    cursor = connection.cursor()

    terms = prepare_search_terms(query)


    if not terms:
        connection.close()
        return []

    sql = """
        WITH matches AS (
            SELECT document_id AS ticket_id, bm25(freshdesk_fts) AS rank
            FROM freshdesk_fts
            WHERE document_type = 'ticket'
            AND freshdesk_fts MATCH ?

            UNION ALL

            SELECT c.ticket_id, bm25(freshdesk_fts) AS rank
            FROM freshdesk_conversations c
            JOIN freshdesk_fts
                ON freshdesk_fts.document_id = c.id
            WHERE freshdesk_fts.document_type = 'conversation'
            AND freshdesk_fts MATCH ?
        ), ranked_tickets AS (
            SELECT ticket_id, MIN(rank) AS rank
            FROM matches
            GROUP BY ticket_id
        )
        SELECT t.*, r.rank AS bm25_rank
        FROM freshdesk_tickets t
        JOIN ranked_tickets r ON r.ticket_id = t.id
    """

    if exclude_ticket_id is not None:
        sql += " AND t.id != ?"

    sql += """
        ORDER BY r.rank ASC, t.updated_at DESC
        LIMIT ?
    """

    rows = []
    retrieval_stage = "fallback_or"
    retrieval_stages, term_statistics = build_fts_retrieval_stages(
        cursor, "freshdesk_fts", "ticket", terms
    )
    selected_anchors = []
    retrieval_query = ""
    for retrieval_stage, fts_query, selected_anchors in retrieval_stages:
        retrieval_query = fts_query
        parameters = [fts_query, fts_query]
        if exclude_ticket_id is not None:
            parameters.append(exclude_ticket_id)
        parameters.append(limit)
        cursor.execute(sql, parameters)
        rows = cursor.fetchall()
        if len(rows) >= limit:
            break

    tickets = [dict(row) for row in rows]
    for ticket in tickets:
        ticket["retrieval_stage"] = retrieval_stage
        ticket["retrieval_query"] = retrieval_query
        ticket["selected_anchors"] = selected_anchors
        ticket["term_statistics"] = term_statistics

    connection.close()

    return tickets


def save_jira_issue(issue):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT OR REPLACE INTO jira_issues (
            key,
            project,
            summary,
            description,
            status,
            created_at,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            issue["key"],
            issue["project"],
            issue["summary"],
            issue["description"],
            issue["status"],
            issue["created_at"],
            issue["updated_at"],
        )
    )

    cursor.execute(
        """
        DELETE FROM jira_fts
        WHERE document_id = ? AND document_type = 'issue'
        """,
        (issue["key"],)
    )

    cursor.execute(
        """
        INSERT INTO jira_fts (
            document_id,
            document_type,
            title,
            content
        )
        VALUES (?, 'issue', ?, ?)
        """,
        (
            issue["key"],
            issue["summary"],
            issue["description"]
        )
    )

    connection.commit()
    connection.close()

def get_jira_comments(issue_key):
    """
    Retrieves cached Jira comments.
    """

    connection = get_connection()
    connection.row_factory = sqlite3.Row

    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT *
        FROM jira_comments
        WHERE issue_key = ?
        """,
        (issue_key,)
    )

    comments = [
        dict(row)
        for row in cursor.fetchall()
    ]

    connection.close()

    return comments


import hashlib
import sqlite3

def save_jira_comment(comment):

    if not isinstance(comment, dict):
        print(f"Skipping non-dict Jira comment: {type(comment).__name__} -> {comment!r}")
        return

    connection = get_connection()
    cursor = connection.cursor()

    issue_key = comment.get("issue_key") or comment.get("issueKey") or "unknown"
    body = comment.get("body") or comment.get("body_text") or ""
    author = comment.get("author")
    if isinstance(author, dict):
        author = author.get("displayName") or author.get("name")

    created_at = comment.get("created_at") or comment.get("created") or ""

    comment_id = comment.get("id")
    if not comment_id:
        seed = f"{issue_key}|{created_at}|{body}"
        comment_id = hashlib.sha1(seed.encode("utf-8")).hexdigest()

    try:
        cursor.execute(
            """
            INSERT OR REPLACE INTO jira_comments (
                id, issue_key, author, body, created_at
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (comment_id, issue_key, author, body, created_at)
        )

        cursor.execute(
            """
            DELETE FROM jira_fts
            WHERE document_id = ? AND document_type = 'comment'
            """,
            (comment_id,)
        )

        cursor.execute(
            """
            INSERT INTO jira_fts (
                document_id, document_type, title, content
            )
            VALUES (?, 'comment', ?, ?)
            """,
            (comment_id, "", body)
        )

        connection.commit()

    except Exception as exc:
        connection.rollback()
        print(f"Could not save Jira comment: {exc}")

    finally:
        connection.close()

def search_local_jira(query, limit=50):
    """
    Searches local Jira issues using FTS5.
    """

    connection = get_connection()
    connection.row_factory = sqlite3.Row

    cursor = connection.cursor()

    terms = prepare_search_terms(query)


    if not terms:
        connection.close()
        return []

    sql = """
        WITH matches AS (
            SELECT document_id AS issue_key, bm25(jira_fts) AS rank
            FROM jira_fts
            WHERE document_type = 'issue'
            AND jira_fts MATCH ?

            UNION ALL

            SELECT c.issue_key, bm25(jira_fts) AS rank
            FROM jira_comments c
            JOIN jira_fts
                ON jira_fts.document_id = c.id
            WHERE jira_fts.document_type = 'comment'
            AND jira_fts MATCH ?
        ), ranked_issues AS (
            SELECT issue_key, MIN(rank) AS rank
            FROM matches
            GROUP BY issue_key
        )
        SELECT j.*, r.rank AS bm25_rank
        FROM jira_issues j
        JOIN ranked_issues r ON r.issue_key = j.key
        ORDER BY r.rank ASC, j.updated_at DESC
        LIMIT ?
    """

    rows = []
    retrieval_stage = "fallback_or"
    retrieval_stages, term_statistics = build_fts_retrieval_stages(
        cursor, "jira_fts", "issue", terms
    )
    selected_anchors = []
    retrieval_query = ""
    for retrieval_stage, fts_query, selected_anchors in retrieval_stages:
        retrieval_query = fts_query
        cursor.execute(sql, (fts_query, fts_query, limit))
        rows = cursor.fetchall()
        if len(rows) >= limit:
            break

    issues = [dict(row) for row in rows]
    for issue in issues:
        issue["retrieval_stage"] = retrieval_stage
        issue["retrieval_query"] = retrieval_query
        issue["selected_anchors"] = selected_anchors
        issue["term_statistics"] = term_statistics

    connection.close()

    return issues


def rebuild_fts_indexes():
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("DELETE FROM freshdesk_fts")
    cursor.execute("DELETE FROM jira_fts")

    cursor.execute(
        """
        INSERT INTO freshdesk_fts (
            document_id,
            document_type,
            title,
            content
        )
        SELECT id, 'ticket', subject, description_text
        FROM freshdesk_tickets
        """
    )

    cursor.execute(
        """
        INSERT INTO freshdesk_fts (
            document_id,
            document_type,
            title,
            content
        )
        SELECT id, 'conversation', '', body_text
        FROM freshdesk_conversations
        """
    )

    cursor.execute(
        """
        INSERT INTO jira_fts (
            document_id,
            document_type,
            title,
            content
        )
        SELECT key, 'issue', summary, description
        FROM jira_issues
        """
    )

    cursor.execute(
        """
        INSERT INTO jira_fts (
            document_id,
            document_type,
            title,
            content
        )
        SELECT id, 'comment', '', body
        FROM jira_comments
        """
    )

    connection.commit()
    connection.close()
