# scratch/print_freshdesk_schema.py
"""Print column information for Freshdesk tables.
Used to discover which column holds email addresses for tickets.
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(r"c:/AI Project/SupportCopilot/storage/support_copilot.db")

def print_table_info(table):
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute(f"PRAGMA table_info({table})")
        rows = cur.fetchall()
        print(f"Columns for {table}:")
        for row in rows:
            # row: cid, name, type, notnull, dflt_value, pk
            print(f"  {row[1]} ({row[2]})")

if __name__ == "__main__":
    for tbl in ["Freshdesk_tickets", "Freshdesk_conversations"]:
        print_table_info(tbl)
