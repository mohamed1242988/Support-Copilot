import requests
from requests.auth import HTTPBasicAuth
from config.config import FRESHDESK_DOMAIN, FRESHDESK_API_KEY

import time

AUTH = HTTPBasicAuth(FRESHDESK_API_KEY, "X")


def get_companies():
    """
    Retrieves all companies using pagination.
    """
    companies = []
    page = 1
    per_page = 100

    while True:
        url = (
            f"{FRESHDESK_DOMAIN}"
            f"/api/v2/companies"
            f"?page={page}&per_page={per_page}"
        )

        response = requests.get(
            url,
            auth=AUTH,
            verify=False
        )

        if response.status_code == 429:
            print("Rate limit reached. Waiting 10 seconds...")
            time.sleep(10)
            continue

        response.raise_for_status()

        batch = response.json()

        if not batch:
            break

        companies.extend(batch)

        print(f"Retrieved page {page}: {len(batch)} companies")

        if len(batch) < per_page:
            break

        page += 1

    return companies

result = get_companies()

print(result)