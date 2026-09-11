# test_delete_ticket.py
import sys
import requests
from requests.auth import HTTPBasicAuth

sys.path.insert(0, r"c:\AI Project\SupportCopilot")
from config.config import FRESHDESK_API_KEY, FRESHDESK_DOMAIN

TICKET_ID = 494455  # ← change to the ticket you want to delete

url = f"{FRESHDESK_DOMAIN}/api/v2/tickets/{TICKET_ID}"

response = requests.delete(
    url,
    auth=HTTPBasicAuth(FRESHDESK_API_KEY, "X"),
    verify=False
)

if response.status_code == 204:
    print(f"✅ Ticket {TICKET_ID} deleted successfully")
else:
    print(f"❌ Error {response.status_code}: {response.text}")