# scratch/inspect_freshdesk_schema.py
"""Utility to print the column names of Freshdesk tables.
Used to discover which column holds email addresses for tickets.
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(r"c:/AI Project/SupportCopilot/storage/support_copilot.db")

def print_columns(table):
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute(f"PRAGMA table_info({table})")
        cols = cur.fetchall()
        print(f"Columns for {table}:")
        for col in cols:
            # col format: cid, name, type, notnull, dflt_value, pk
            print(f"  {col[1]} ({col[2]})")

if __name__ == "__main__":
    for tbl in ["Freshdesk_tickets", "Freshdesk_conversations"]:
        print_columns(tbl)
