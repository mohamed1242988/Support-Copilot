# test_sync_one_ticket.py
"""
Test script – sync the assigned‑agent name for a *single* Freshdesk ticket.

Usage (from the project root):
    python test_sync_one_ticket.py <TICKET_ID>
"""

import sys
import sqlite3
import importlib
import time
from pathlib import Path

# ----------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------
DB_PATH = Path(r"C:/AI Project/SupportCopilot/storage/support_copilot.db")
SLEEP_BETWEEN_CALLS = 0.1   # tiny pause to stay well under Freshdesk rate limits


def _get_agent_name(agent_id):
    """Lazy import of the Freshdesk helper that returns a readable name."""
    freshdesk_mod = importlib.import_module("integrations.freshdesk")
    return freshdesk_mod.get_agent_name(agent_id)


def _get_ticket_details(ticket_id):
    """Fetch freshdesk ticket JSON – re‑uses the same helper as the app."""
    freshdesk_mod = importlib.import_module("integrations.freshdesk")
    # The helper already asks for `include=conversations`; we only need the ticket itself.
    return freshdesk_mod.get_ticket_details(ticket_id)


def sync_one_ticket(ticket_id: int):
    # -------------------------------------------------
    # 1️⃣ Pull ticket data from Freshdesk
    # -------------------------------------------------
    try:
        ticket_json = _get_ticket_details(ticket_id)
    except Exception as exc:
        print(f"❌  Failed to fetch ticket {ticket_id} from Freshdesk – {exc}")
        return

    # -------------------------------------------------
    # 2️⃣ Extract the numeric responder_id (if any)
    # -------------------------------------------------
    responder_id = ticket_json.get("responder_id")
    if not responder_id:
        print(f"⚠️  Ticket {ticket_id} has no assigned agent (responder_id is null).")
        return

    # -------------------------------------------------
    # 3️⃣ Resolve the numeric ID to a printable name
    # -------------------------------------------------
    try:
        agent_name = _get_agent_name(responder_id)
    except Exception as exc:
        print(f"❌  Could not resolve agent ID {responder_id} – {exc}")
        return

    if not agent_name:
        print(f"⚠️  Freshdesk returned no name for agent ID {responder_id}.")
        return

    # -------------------------------------------------
    # 4️⃣ Update the local SQLite row
    # -------------------------------------------------
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute(
        "SELECT assigned_agent FROM freshdesk_tickets WHERE id = ?",
        (ticket_id,),
    )
    row = cur.fetchone()
    if row is None:
        print(f"❌  Ticket {ticket_id} not found in the local database.")
        conn.close()
        return

    # Show the before/after values (helps you verify the change)
    old_val = row[0]
    print(f"🗂️  Ticket {ticket_id} – current assigned_agent: {old_val!r}")
    print(f"🔁  Updating assigned_agent to: {agent_name!r}")

    cur.execute(
        "UPDATE freshdesk_tickets SET assigned_agent = ? WHERE id = ?",
        (agent_name, ticket_id),
    )
    conn.commit()
    conn.close()

    print(f"✅  Ticket {ticket_id} updated successfully.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python test_sync_one_ticket.py <TICKET_ID>")
        sys.exit(1)

    try:
        tid = int(sys.argv[1])
    except ValueError:
        print("❗  Ticket ID must be an integer.")
        sys.exit(1)

    # Optional tiny pause – protects you from hitting a 429 if you run many tests in a row
    time.sleep(SLEEP_BETWEEN_CALLS)

    sync_one_ticket(tid)