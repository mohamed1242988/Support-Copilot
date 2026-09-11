import requests
from requests.auth import HTTPBasicAuth
from config.config import FRESHDESK_DOMAIN, FRESHDESK_API_KEY

import time

AUTH = HTTPBasicAuth(FRESHDESK_API_KEY, "X")


def get_ticket_details(ticket_id):
    """
    Retrieves a single ticket.
    """

    url = (
        f"{FRESHDESK_DOMAIN}"
        f"/api/v2/tickets/{ticket_id}"
    )

    response = requests.get(
        url,
        auth=AUTH,
        verify=False
    )

    if response.status_code == 429:
        print("Rate limit reached. Waiting 10 seconds...")
        time.sleep(10)

        return get_ticket_details(ticket_id)

    response.raise_for_status()

    return response.json()


#result = get_ticket_details(12505)

url = (
        f"{FRESHDESK_DOMAIN}"
        f"/api/v2/companies"
    )

response = requests.get(
        url,
        auth=AUTH,
        verify=False
    )

#print(result)


def get_companies(company_id):
    """
    Retrieves a single company.
    """

    url = (
        f"{FRESHDESK_DOMAIN}"
        f"/api/v2/companies/{company_id}"
    )

    response = requests.get(
        url,
        auth=AUTH,
        verify=False
    )

    if response.status_code == 429:
        print("Rate limit reached. Waiting 10 seconds...")
        time.sleep(10)

        return get_companies(company_id)

    response.raise_for_status()

    return response.json()

result=get_companies(68000199329)

print(result)