"""
One-time script to import all historical Freshdesk tickets for group 68000007023.
Includes automatic retries for network/DNS glitches and rate limits.
"""
import time
from datetime import datetime, timezone
import requests

from config.config import FRESHDESK_DOMAIN
from integrations.freshdesk import (
    AUTH,
    get_ticket_details,
    get_or_create_customer,
    get_agent_name,
)
from storage.database import (
    initialize_database,
    save_ticket,
    save_conversations,
)

TARGET_GROUP_ID = 68000007023


def safe_get(url, params=None, max_retries=5, delay=10):
    """
    Performs requests.get with automatic retries for DNS/network drops and 429 rate limits.
    """
    for attempt in range(1, max_retries + 1):
        try:
            response = requests.get(url, params=params, auth=AUTH, verify=False)
            
            if response.status_code == 429:
                print("Rate limit reached (429). Waiting 60s...")
                time.sleep(60)
                continue

            response.raise_for_status()
            return response.json()

        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            print(f"[Network Glitch] Attempt {attempt}/{max_retries} failed: {e}. Retrying in {delay}s...")
            time.sleep(delay)
        except Exception:
            raise

    raise RuntimeError(f"Failed to fetch {url} after {max_retries} retries.")


def search_tickets_by_query(query_str, page=1):
    """Executes a search query against Freshdesk safely with network retry."""
    url = f"{FRESHDESK_DOMAIN}/api/v2/search/tickets"
    return safe_get(url, params={"query": f'"{query_str}"', "page": page})


def process_ticket(ticket_id):
    """Fetches details with retry on network drops, resolves customer & agent, and saves."""
    for attempt in range(1, 4):
        try:
            details = get_ticket_details(ticket_id)
            break
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            print(f"Network error on ticket {ticket_id} (attempt {attempt}/3). Retrying in 5s...")
            time.sleep(5)
    else:
        raise RuntimeError(f"Could not fetch ticket {ticket_id} after retries.")

    # 1. Customer resolution
    cust_id, cust_name = get_or_create_customer(details.get("company_id"))
    details["customer_id"] = cust_id
    details["customer_name"] = cust_name

    # 2. Agent resolution (retains numeric ID if unmapped)
    responder_id = details.get("responder_id")
    agent_name = get_agent_name(responder_id)
    details["assigned_agent"] = agent_name if agent_name else (str(responder_id) if responder_id else None)

    # 3. Save ticket and conversations
    save_ticket(details)
    save_conversations(ticket_id, details.get("conversations", []))


def sync_query_chunk(query_str):
    """Paginates through pages (up to 10) for a specific query chunk."""
    page = 1
    total_processed = 0
    while page <= 10:
        result = search_tickets_by_query(query_str, page=page)
        tickets = result.get("results", [])
        if not tickets:
            break

        for t in tickets:
            print(f"  -> Importing ticket {t['id']} ({t.get('subject', '')[:40]}...)")
            try:
                process_ticket(t["id"])
                total_processed += 1
            except Exception as e:
                print(f"  [ERROR] Failed on ticket {t['id']}: {e}")

        page += 1
    return total_processed


def fetch_all_group_tickets(start_date=None, end_date=None):
    """
    Recursively slices time windows if total tickets exceed Freshdesk's 300 search ceiling.
    """
    query_parts = [f"group_id:{TARGET_GROUP_ID}"]
    if start_date:
        query_parts.append(f"created_at:>'{start_date[:10]}'")
    if end_date:
        query_parts.append(f"created_at:<'{end_date[:10]}'")

    query_str = " AND ".join(query_parts)
    initial_res = search_tickets_by_query(query_str, page=1)
    total = initial_res.get("total", 0)

    if total == 0:
        return 0

    # Fits within Freshdesk's 10-page / 300-ticket limit
    if total <= 300:
        print(f"Fetching chunk ({total} tickets) with query: {query_str}")
        return sync_query_chunk(query_str)

    # Automatic time-slicing to bypass the 300-ticket ceiling without missing tickets
    if not start_date:
        start_date = "2020-01-01"
    if not end_date:
        end_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    s_dt = datetime.fromisoformat(start_date)
    e_dt = datetime.fromisoformat(end_date)
    mid_str = (s_dt + ((e_dt - s_dt) / 2)).strftime("%Y-%m-%d")

    print(f"Total {total} exceeds 300 ceiling. Auto-partitioning at {mid_str}...")
    left = fetch_all_group_tickets(start_date, mid_str)
    right = fetch_all_group_tickets(mid_str, end_date)
    return left + right


def run():
    initialize_database()
    print(f"=== Starting full historical import for group {TARGET_GROUP_ID} ===")
    count = fetch_all_group_tickets()
    print(f"=== Completed: {count} tickets processed successfully ===")


if __name__ == "__main__":
    run()