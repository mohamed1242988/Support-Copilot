# test_update_followup_by.py
import json
import sys
import requests
from requests.auth import HTTPBasicAuth

sys.path.insert(0, r"c:\AI Project\SupportCopilot")
from config.config import FRESHDESK_API_KEY, FRESHDESK_DOMAIN

TICKET_ID = 494455
FOLLOWUP_DATE = "2026-09-25"
STATUS = 2

AUTH = HTTPBasicAuth(FRESHDESK_API_KEY, "X")

# 1. Update ticket status + follow-up date
url = f"{FRESHDESK_DOMAIN}/api/v2/tickets/{TICKET_ID}"

response = requests.put(
    url,
    auth=AUTH,
    verify=False,
    json={
        "status": STATUS,
        "custom_fields": {
            "cf_followup_by": FOLLOWUP_DATE
        }
    }
)

if response.status_code == 200:
    updated = response.json()
    cf = updated.get("custom_fields", {})

    print(
        f"✅ Status: {updated.get('status')} | "
        f"cf_followup_by: {cf.get('cf_followup_by')}"
    )
else:
    print(f"❌ Ticket update error {response.status_code}: {response.text}")


# 2. Add private note
note_url = f"{FRESHDESK_DOMAIN}/api/v2/tickets/{TICKET_ID}/notes"

note_response = requests.post(
    note_url,
    auth=AUTH,
    verify=False,
    json={
        "body": "Follow-up is due. Please review the ticket and take any necessary follow-up actions.",
        "private": True
    }
)

if note_response.status_code == 201:
    print("✅ Private note added successfully")
else:
    print(
        f"❌ Note error {note_response.status_code}: "
        f"{note_response.text}"
    )