import json
import sys
import requests
from requests.auth import HTTPBasicAuth

# Load project config for Domain & API Key
sys.path.insert(0, r"c:\AI Project\SupportCopilot")
from config.config import FRESHDESK_API_KEY, FRESHDESK_DOMAIN

# Replace with any ticket number you want to inspect
TICKET_ID = 316372

url = f"{FRESHDESK_DOMAIN}/api/v2/tickets/{TICKET_ID}"

response = requests.get(
    url, auth=HTTPBasicAuth(FRESHDESK_API_KEY, "X"), verify=False
)

if response.status_code == 200:
    ticket_data = response.json()
    # Pretty-print all fields
    print(json.dumps(ticket_data, indent=2, ensure_ascii=False))
else:
    print(f"Error {response.status_code}: {response.text}")