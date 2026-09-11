from integrations.freshdesk import get_ticket_details, get_agent_name
from storage.database import get_connection


def backfill_assigned_agents():
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT id
        FROM freshdesk_tickets
        ORDER BY id
    """)

    ticket_ids = [row[0] for row in cursor.fetchall()]
    connection.close()

    total = len(ticket_ids)
    updated = 0
    unassigned = 0
    failed = 0

    print(f"Found {total} tickets to process.\n")

    for index, ticket_id in enumerate(ticket_ids, start=1):

        print(f"[{index}/{total}] Processing ticket {ticket_id}...")

        try:
            # Get current ticket details from Freshdesk
            details = get_ticket_details(ticket_id)

            responder_id = details.get("responder_id")

            if not responder_id:
                print("  -> No assigned agent.")
                unassigned += 1
                continue

            # Use the existing agent mapping/API logic
            agent_name = get_agent_name(responder_id)

            if not agent_name:
                print(
                    f"  -> Could not resolve responder_id "
                    f"{responder_id}"
                )
                failed += 1
                continue

            connection = get_connection()
            cursor = connection.cursor()

            cursor.execute("""
                UPDATE freshdesk_tickets
                SET assigned_agent = ?
                WHERE id = ?
            """, (agent_name, ticket_id))

            connection.commit()
            connection.close()

            updated += 1

            print(
                f"  -> responder_id: {responder_id}"
                f" | agent: {agent_name}"
            )

        except Exception as e:
            failed += 1
            print(f"  -> ERROR: {e}")

    print("\n================================")
    print("Backfill completed.")
    print(f"Total tickets : {total}")
    print(f"Updated       : {updated}")
    print(f"Unassigned    : {unassigned}")
    print(f"Failed        : {failed}")
    print("================================")


if __name__ == "__main__":
    backfill_assigned_agents()