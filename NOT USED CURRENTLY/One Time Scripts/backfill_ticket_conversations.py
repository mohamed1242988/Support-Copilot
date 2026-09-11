# backfill_conversations.py
"""
One-off script to re-fetch ALL conversations for every ticket in the DB.
Fixes the 10-conversation cap from the old ?include=conversations approach.

Run from the project root:
    python backfill_conversations.py
"""

import sqlite3
import time
import importlib
from pathlib import Path

DB_PATH = Path(r"C:/AI Project/SupportCopilot/storage/support_copilot.db")
SLEEP_BETWEEN_TICKETS = 0.2  # seconds between tickets to respect rate limits


def main():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT id FROM freshdesk_tickets ORDER BY id")
    ticket_ids = [row[0] for row in cur.fetchall()]
    conn.close()

    total = len(ticket_ids)
    print(f"🔎  Found {total:,} tickets. Starting backfill...")

    freshdesk = importlib.import_module("integrations.freshdesk")
    db = importlib.import_module("storage.database")

    updated = 0
    errors = 0

    for idx, ticket_id in enumerate(ticket_ids, start=1):
        try:
            conversations = freshdesk.get_all_conversations(ticket_id)
            db.save_conversations(ticket_id, conversations)
            updated += 1
        except Exception as exc:
            errors += 1
            print(f"⚠️  Ticket {ticket_id} – error: {exc}")

        if idx % 50 == 0:
            print(f"⏱️  {idx:,}/{total:,} processed – updated {updated:,}, errors {errors:,}")

        time.sleep(SLEEP_BETWEEN_TICKETS)

    print(f"\n✅  Done. Updated: {updated:,} | Errors: {errors:,}")


if __name__ == "__main__":
    main()