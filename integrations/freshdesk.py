import requests
from requests.auth import HTTPBasicAuth
from config.config import FRESHDESK_DOMAIN, FRESHDESK_API_KEY
from storage.database import get_customer,get_connection

import time


AUTH = HTTPBasicAuth(FRESHDESK_API_KEY, "X")

_AGENT_NAME_CACHE = {}
# Static mapping for responder IDs (fallback when API fails)
STATIC_AGENT_MAP = {
    68002801307: "Basel Aymen",
    68003267304: "Bassam Gaber",
    68002712510: "Ciprian Cordas",
    68002682919: "Hager Khaled",
    68009160176: "Nariman Shalash",
    68002711344: "Mohamed Khalid",
    68002712505: "Youssef Hassan",
    68002682935: "Osama Kamal",
    68002682923: "Ahmed Ateek",
}


def get_agent_name(agent_id):
    """
    Retrieves Freshdesk agent name by ID with local in-memory caching.
    """
    if not agent_id:
        return None

    # 1️⃣ Check static fallback map first
    if agent_id in STATIC_AGENT_MAP:
        return STATIC_AGENT_MAP[agent_id]
    # 2️⃣ Check in‑memory cache
    if agent_id in _AGENT_NAME_CACHE:
        return _AGENT_NAME_CACHE[agent_id]

    url = f"{FRESHDESK_DOMAIN}/api/v2/agents/{agent_id}"
    try:
        response = requests.get(url, auth=AUTH, verify=False)
        if response.status_code == 429:
            time.sleep(10)
            return get_agent_name(agent_id)
        if response.status_code == 200:
            agent_data = response.json()
            contact = agent_data.get("contact", {})
            name = contact.get("name") or agent_data.get("name")
            _AGENT_NAME_CACHE[agent_id] = name
            return name
    except Exception:
        pass

    return None


def search_tickets(updated_from=None, updated_to=None, page=1):
    """
    Searches Freshdesk tickets for our product group.
    """

    url = f"{FRESHDESK_DOMAIN}/api/v2/search/tickets"

    query = "group_id:68000003793"

    if updated_from:
        query += f" AND updated_at:>'{updated_from[:10]}'"

    if updated_to:
        query += f" AND updated_at:<'{updated_to[:10]}'"

    params = {
        "query": f'"{query}"',
        "page": page
    }

    response = requests.get(
        url,
        params=params,
        auth=AUTH,
        verify=False
    )

    if response.status_code == 429:
        print("Rate limit reached. Waiting 60 seconds...")
        time.sleep(60)

        return search_tickets(
            updated_from=updated_from,
            updated_to=updated_to,
            page=page
        )

    response.raise_for_status()

    return response.json()


def get_all_conversations(ticket_id):
    """
    Retrieves ALL conversations for a ticket via paginated API calls.
    Freshdesk caps embedded conversations at 10; this bypasses that limit.
    """
    all_conversations = []
    page = 1

    while True:
        url = f"{FRESHDESK_DOMAIN}/api/v2/tickets/{ticket_id}/conversations"
        response = requests.get(
            url,
            params={"page": page, "per_page": 100},
            auth=AUTH,
            verify=False
        )

        if response.status_code == 429:
            print("Rate limit reached. Waiting 20 seconds...")
            time.sleep(20)
            continue

        if response.status_code == 404:
            break

        response.raise_for_status()

        page_data = response.json()
        if not page_data:
            break  # no more pages

        all_conversations.extend(page_data)
        page += 1

    return all_conversations


def get_ticket_details(ticket_id):
    """
    Retrieves a single ticket with ALL conversations (paginated, no 10-item cap).
    """
    url = f"{FRESHDESK_DOMAIN}/api/v2/tickets/{ticket_id}"

    response = requests.get(url, auth=AUTH, verify=False)

    if response.status_code == 429:
        print("Rate limit reached. Waiting 20 seconds...")
        time.sleep(20)
        return get_ticket_details(ticket_id)

    response.raise_for_status()

    ticket = response.json()
    ticket["conversations"] = get_all_conversations(ticket_id)
    return ticket

def get_or_create_customer(company_id):
    """
    Returns customer information from the local database.
    If the customer does not exist, retrieves it from Freshdesk
    and adds it to the local database.
    """

    if company_id is None:
        return None, None

    customer = get_customer(company_id)

    if customer:
        return customer[0], customer[1]

    company = get_company(company_id)

    customer_id = company["id"]
    customer_name = company["name"]

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT INTO customers (Freshdesk_ID, Name)
        VALUES (?, ?)
        """,
        (customer_id, customer_name)
    )

    connection.commit()
    connection.close()

    return customer_id, customer_name

def get_company(company_id):
    """
    Retrieves a Freshdesk company by ID.
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

        return get_company(company_id)

    response.raise_for_status()

    return response.json()