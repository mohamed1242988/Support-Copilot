import requests
from requests.auth import HTTPBasicAuth

from config.config import FRESHDESK_API_KEY, FRESHDESK_DOMAIN

SURVEY_ID = "8760f2ac-963d-438f-835d-1157c6afc80d"
TICKET_ID = 311155  # <-- replace with a historical ticket ID

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

    response.raise_for_status()
    data = response.json()

    for r in data.get("data", []):
        if str(r.get("ticket_id")) == str(TICKET_ID):
            print("FOUND:")
            print(r)
            raise SystemExit

    url = data.get("paging", {}).get("next")

print("No CSAT response found for this ticket.")