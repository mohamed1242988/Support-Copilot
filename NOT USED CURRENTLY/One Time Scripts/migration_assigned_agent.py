# migration_assigned_agent.py
import sqlite3
import importlib
from pathlib import Path
from storage.database import DATABASE_PATH   # only the DB‑path constant

# ----------------------------------------------------------------------
# Set to True only if you want a full rebuild of the FTS index.
# Keep False for the normal incremental update.
# ----------------------------------------------------------------------
FULL_REINDEX = False


# -------------------------------------------------
# 1️⃣ Ensure the `assigned_agent` column exists
# -------------------------------------------------
def ensure_assigned_agent_column():
    """
    Opens a short‑lived connection, makes sure the column exists,
    then commits & closes the connection so no lock is held afterwards.
    Returns the final list of column names (used later for back‑fill).
    """
    conn = sqlite3.connect(DATABASE_PATH)
    cur = conn.cursor()

    cur.execute("PRAGMA table_info(freshdesk_tickets)")
    cols = [row[1] for row in cur.fetchall()]

    # Rename legacy column if needed
    if "responder_id" in cols and "assigned_agent" not in cols:
        cur.execute(
            "ALTER TABLE freshdesk_tickets RENAME COLUMN responder_id TO assigned_agent"
        )
        cols.append("assigned_agent")

    # Add the column only if it truly does not exist
    if "assigned_agent" not in cols:
        cur.execute("ALTER TABLE freshdesk_tickets ADD COLUMN assigned_agent TEXT")
        cols.append("assigned_agent")

    conn.commit()
    conn.close()
    return cols


# -------------------------------------------------
# 2️⃣ (Optional) Back‑fill `assigned_agent` for rows that are still NULL
# -------------------------------------------------
def backfill_assigned_agent():
    """
    This step **does not call the Freshdesk API** – it only uses a static
    in‑memory map you can edit below if you want to resolve numeric IDs
    to names locally. If you don’t need any back‑fill, just leave the map empty;
    the function will quickly exit.
    """
    # ---- EDIT this map with any known id → name pairs you have ----
    STATIC_AGENT_MAP = {
        # 101: "Alice Smith",
        # 102: "Bob Jones",
        # …
    }
    # --------------------------------------------------------------

    if not STATIC_AGENT_MAP:
        print("No static agent map supplied – skipping back‑fill.")
        return 0

    conn = sqlite3.connect(DATABASE_PATH)
    cur = conn.cursor()

    # Find tickets where the name is still NULL but we have a numeric ID somewhere
    cur.execute(
        """
        SELECT id, assignee
        FROM freshdesk_tickets
        WHERE assigned_agent IS NULL
        """
    )
    rows = cur.fetchall()
    updated = 0

    for ticket_id, assignee_val in rows:
        if assignee_val is None:
            continue
        name = STATIC_AGENT_MAP.get(assignee_val)
        if name:
            cur.execute(
                "UPDATE freshdesk_tickets SET assigned_agent = ? WHERE id = ?",
                (name, ticket_id),
            )
            updated += 1

    conn.commit()
    conn.close()
    print(f"Back‑filled {updated} rows using the static map.")
    return updated


# -------------------------------------------------
# 3️⃣ Re‑create the table without the obsolete columns
# -------------------------------------------------
def recreate_table_without_obsolete():
    """
    Because SQLite cannot DROP columns, we:
      1️⃣ Create a brand‑new table that contains everything *except*
          `assignee` and `responder_id`.
      2️⃣ Copy the data from the old table (those columns are simply omitted).
      3️⃣ Drop the old table and rename the new one.
    This function runs in its own connection – the previous connection
    has already been closed, so no lock remains.
    """
    conn = sqlite3.connect(DATABASE_PATH)
    cur = conn.cursor()

    # 1️⃣ New schema (no `assignee`, no `responder_id`)
    cur.execute(
        """
        CREATE TABLE freshdesk_tickets_new (
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

    # 2️⃣ Copy data (ignore the obsolete columns)
    cur.execute(
        """
        INSERT INTO freshdesk_tickets_new
        SELECT
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
        FROM freshdesk_tickets
        """
    )

    # 3️⃣ Drop old table & rename new one
    cur.execute("DROP TABLE freshdesk_tickets")
    cur.execute("ALTER TABLE freshdesk_tickets_new RENAME TO freshdesk_tickets")

    conn.commit()
    conn.close()
    print("Re‑created `freshdesk_tickets` without `assignee` (and any `responder_id`).")


# -------------------------------------------------
# 4️⃣ Refresh the FTS5 index
# -------------------------------------------------
def update_fts():
    conn = sqlite3.connect(DATABASE_PATH)
    cur = conn.cursor()

    if FULL_REINDEX:
        # Full rebuild – delete everything and re‑insert
        cur.execute("DELETE FROM freshdesk_fts WHERE document_type = 'ticket'")
        cur.execute(
            "SELECT id, subject, description_text, assigned_agent FROM freshdesk_tickets"
        )
        for tid, subject, desc, agent in cur.fetchall():
            fts = f"{desc or ''} | Agent: {agent or ''}".strip()
            cur.execute(
                """
                INSERT INTO freshdesk_fts (document_id, document_type, title, content)
                VALUES (?, 'ticket', ?, ?)
                """,
                (tid, subject, fts),
            )
    else:
        # Incremental – only tickets that already have a name
        cur.execute(
            """
            SELECT id, subject, description_text, assigned_agent
            FROM freshdesk_tickets
            WHERE assigned_agent IS NOT NULL
            """
        )
        for tid, subject, desc, agent in cur.fetchall():
            cur.execute(
                "DELETE FROM freshdesk_fts WHERE document_id = ? AND document_type = 'ticket'",
                (tid,),
            )
            fts = f"{desc or ''} | Agent: {agent or ''}".strip()
            cur.execute(
                """
                INSERT INTO freshdesk_fts (document_id, document_type, title, content)
                VALUES (?, 'ticket', ?, ?)
                """,
                (tid, subject, fts),
            )

    conn.commit()
    conn.close()
    print("FTS index refreshed.")


# -------------------------------------------------
# 5️⃣ Orchestrator
# -------------------------------------------------
def migrate():
    # Step 1 – ensure column exists (this closes its own connection)
    cols = ensure_assigned_agent_column()

    # Optional back‑fill – safe because we already closed the connection above
    backfill_assigned_agent()

    # Step 3 – recreate the table without the old columns
    recreate_table_without_obsolete()

    # Step 4 – refresh the full‑text search index
    update_fts()

    print("\n=== Migration complete ===")
    print(" • `assigned_agent` column is present and stores the agent name.")
    print(" • Obsolete columns `assignee` (and any leftover `responder_id`) are gone.")
    print(" • FTS5 table now includes the agent name for searchable tickets.\n")


if __name__ == "__main__":
    migrate()