"""
One-time script to backfill existing Freshdesk tickets in SQLite with the new extended fields,
mapped status/priority text, arrow separators, and assignee agent names.
"""
from storage.database import get_connection, save_ticket
from integrations.freshdesk import (
    get_ticket_details,
    get_agent_name,
    get_or_create_customer,
)


def backfill_existing_tickets():
    conn = get_connection()
    cursor = conn.cursor()

    ticket_ids = [
        row[0]
        for row in cursor.execute(
            "SELECT id FROM freshdesk_tickets ORDER BY id DESC"
        ).fetchall()
    ]
    conn.close()

    print(f"Starting backfill for {len(ticket_ids)} existing tickets...")

    for idx, ticket_id in enumerate(ticket_ids, 1):
        print(f"[{idx}/{len(ticket_ids)}] Updating ticket {ticket_id}...")
        try:
            details = get_ticket_details(ticket_id)
            customer_id, customer_name = get_or_create_customer(
                details.get("company_id")
            )
            details["customer_id"] = customer_id
            details["customer_name"] = customer_name
            details["assignee"] = get_agent_name(details.get("responder_id"))

            save_ticket(details)
        except Exception as exc:
            print(f"Error updating ticket {ticket_id}: {exc}")

    print("\nBackfill completed successfully!")


if __name__ == "__main__":
    backfill_existing_tickets()