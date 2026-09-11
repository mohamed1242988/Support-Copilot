import sqlite3
import requests
from requests.auth import HTTPBasicAuth
from config.config import FRESHDESK_DOMAIN, FRESHDESK_API_KEY
import time


DB_PATH = r"storage\support_copilot.db"

AUTH = HTTPBasicAuth(FRESHDESK_API_KEY, "X")


def get_all_companies():
    """
    Retrieves all Freshdesk companies using pagination.
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

        print(f"Retrieved company page {page}: {len(batch)} companies")

        if len(batch) < per_page:
            break

        page += 1

    return companies


def get_existing_ticket_ids():
    """
    Retrieves all existing ticket IDs from SQLite.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id
        FROM Tickets
    """)

    ticket_ids = [row[0] for row in cursor.fetchall()]

    conn.close()

    return ticket_ids


def get_ticket_details(ticket_id):
    """
    Retrieves a single Freshdesk ticket.
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


def migrate_tickets(ticket_ids, companies):
    """
    Retrieves company_id from each Freshdesk ticket,
    inserts the company if it is used, and updates the ticket.
    """

    # Create a quick company lookup:
    # Freshdesk company ID -> company name
    company_lookup = {
        company["id"]: company["name"]
        for company in companies
    }

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    used_company_ids = set()
    updated_tickets = 0
    tickets_without_company = 0

    for index, ticket_id in enumerate(ticket_ids, start=1):

        ticket = get_ticket_details(ticket_id)

        company_id = ticket.get("company_id")

        if company_id is None:
            tickets_without_company += 1
            continue

        company_name = company_lookup.get(company_id)

        if company_name is None:
            print(
                f"WARNING: Company {company_id} "
                f"not found in companies API."
            )
            continue

        # Add company to customers if it doesn't already exist
        cursor.execute("""
            INSERT OR IGNORE INTO customers
            (Freshdesk_ID, Name)
            VALUES (?, ?)
        """, (
            company_id,
            company_name
        ))

        # Update the ticket
        cursor.execute("""
            UPDATE Tickets
            SET
                Customer_ID = ?,
                Customer_Name = ?
            WHERE id = ?
        """, (
            company_id,
            company_name,
            ticket_id
        ))

        used_company_ids.add(company_id)
        updated_tickets += 1

        if index % 25 == 0:
            conn.commit()

            print(
                f"Processed {index}/{len(ticket_ids)} tickets | "
                f"Updated: {updated_tickets}"
            )

    conn.commit()
    conn.close()

    print()
    print(f"Tickets processed: {len(ticket_ids)}")
    print(f"Tickets updated: {updated_tickets}")
    print(f"Tickets without company: {tickets_without_company}")
    print(f"Companies used: {len(used_company_ids)}")


def validate_migration():
    """
    Validates the migration results.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT COUNT(*)
        FROM customers
    """)
    customer_count = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*)
        FROM Tickets
        WHERE Customer_ID IS NOT NULL
    """)
    tickets_with_customer = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*)
        FROM Tickets
        WHERE Customer_ID IS NOT NULL
        AND Customer_Name IS NULL
    """)
    missing_names = cursor.fetchone()[0]

    conn.close()

    print()
    print("=== Migration Validation ===")
    print(f"Customers in database: {customer_count}")
    print(f"Tickets with Customer_ID: {tickets_with_customer}")
    print(f"Tickets with missing Customer_Name: {missing_names}")


def main():

    print("=== Starting Customer Migration ===")
    print()

    print("Retrieving all Freshdesk companies...")
    companies = get_all_companies()

    print(f"Total Freshdesk companies retrieved: {len(companies)}")
    print()

    print("Retrieving existing ticket IDs...")
    ticket_ids = get_existing_ticket_ids()

    print(f"Total existing tickets: {len(ticket_ids)}")
    print()

    print("Migrating customer information...")
    migrate_tickets(ticket_ids, companies)

    validate_migration()

    print()
    print("Migration completed successfully.")


if __name__ == "__main__":
    main()