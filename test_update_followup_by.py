# test_update_followup_by.py
import json
import sys
import requests
from requests.auth import HTTPBasicAuth

sys.path.insert(0, r"c:\AI Project\SupportCopilot")
from config.config import FRESHDESK_API_KEY, FRESHDESK_DOMAIN

TICKET_ID = 490916                      # ← change to your test ticket
FOLLOWUP_DATE = "2026-09-25" # ← ISO 8601 UTC datetime
STATUS = 3                              # ← 2=Open, 3=Pending, 4=Resolved, 5=Closed

url = f"{FRESHDESK_DOMAIN}/api/v2/tickets/{TICKET_ID}"

response = requests.put(
    url,
    auth=HTTPBasicAuth(FRESHDESK_API_KEY, "X"),
    verify=False,
    json={
        "status": STATUS,
        "custom_fields": {"cf_followup_by": FOLLOWUP_DATE}
    }
)

if response.status_code == 200:
    updated = response.json()
    cf = updated.get("custom_fields", {})
    print(f"✅  Status: {updated.get('status')} | cf_followup_by: {cf.get('cf_followup_by')}")
else:
    print(f"❌  Error {response.status_code}: {response.text}")