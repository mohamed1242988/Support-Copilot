# test_followup_scheduler.py
import sys
import requests
from requests.auth import HTTPBasicAuth
from services.sync import incremental_sync
from config.config import FRESHDESK_API_KEY, FRESHDESK_DOMAIN
from storage.database import get_connection

sys.path.insert(0, r"c:\AI Project\SupportCopilot")

incremental_sync()

STATUS = 2  # 2=Open, 3=Pending, 4=Resolved, 5=Closed
AUTH = HTTPBasicAuth(FRESHDESK_API_KEY, "X")

COMMENT = "Follow-up is due. Please review the ticket and take any necessary follow-up actions."


# 1. Find tickets that are due for follow-up
connection = get_connection()
cursor = connection.cursor()

cursor.execute("""
    SELECT id
    FROM freshdesk_tickets
    WHERE DATE(followup_by) <= DATE('now')
    AND status NOT IN ('Closed', 'Resolved')
    AND assigned_agent IS NOT NULL
    AND assigned_agent NOT LIKE '%Ciprian%'
""")

tickets = cursor.fetchall()
connection.close()

print(f"Found {len(tickets)} ticket(s) requiring follow-up.")


# 2. Process each ticket
for row in tickets:

    ticket_id = row[0]

    print(f"\nProcessing ticket {ticket_id}...")

        # Update status
    ticket_url = f"{FRESHDESK_DOMAIN}/api/v2/tickets/{ticket_id}"

    response = requests.put(
        ticket_url,
        auth=AUTH,
        verify=False,
        json={
            "status": STATUS
        }
    )

    if response.status_code == 200:
        print("  ✅ Status updated")
    else:
        print(f"  ❌ Status update failed: {response.status_code}")
        continue


    # Add private note
    note_url = f"{FRESHDESK_DOMAIN}/api/v2/tickets/{ticket_id}/notes"

    note_response = requests.post(
        note_url,
        auth=AUTH,
        verify=False,
        json={
            "body": COMMENT,
            "private": True
        }
    )

    if note_response.status_code == 201:
        print("  ✅ Private note added")
    else:
        print(f"  ❌ Note failed: {note_response.status_code}")
    
