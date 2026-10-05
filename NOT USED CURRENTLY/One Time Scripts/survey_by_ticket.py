import json
import sys
import requests
from requests.auth import HTTPBasicAuth

sys.path.insert(0, r"c:\AI Project\SupportCopilot")
from config.config import FRESHDESK_API_KEY, FRESHDESK_DOMAIN

TICKET_ID = 481982
SURVEY_ID = "8760f2ac-963d-438f-835d-1157c6afc80d"

url = (
    f"{FRESHDESK_DOMAIN}/api/v2/customer-satisfaction/"
    f"surveys/{SURVEY_ID}/responses?per_page=100"
)

while url:
    response = requests.get(
        url,
        auth=HTTPBasicAuth(FRESHDESK_API_KEY, "X"),
        verify=False
    )

    if response.status_code != 200:
        print(f"Error {response.status_code}: {response.text}")
        break

    data = response.json()

    for survey_response in data.get("data", []):
        if str(survey_response.get("ticket_id")) == str(TICKET_ID):
            print(json.dumps(
                survey_response,
                indent=2,
                ensure_ascii=False
            ))
            raise SystemExit

    url = data.get("paging", {}).get("next")

print(f"No CSAT response found for ticket {TICKET_ID}")