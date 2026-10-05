import sys
import sqlite3
import requests
from requests.auth import HTTPBasicAuth

# ---------------------------------------------------------
# Project imports
# ---------------------------------------------------------

sys.path.insert(0, r"C:\AI Project\SupportCopilot")

from config.config import FRESHDESK_API_KEY, FRESHDESK_DOMAIN


# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------

DB_PATH = r"C:\AI Project\SupportCopilot\storage\support_copilot.db"

SURVEY_ID = "8760f2ac-963d-438f-835d-1157c6afc80d"
TARGET_GROUP_ID = 68000003793


# ---------------------------------------------------------
# Database
# ---------------------------------------------------------

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Add CSAT columns if they don't already exist
columns = {
    row[1]
    for row in cursor.execute("PRAGMA table_info(Freshdesk_tickets)")
}

if "csat_responded_at" not in columns:
    cursor.execute("""
        ALTER TABLE Freshdesk_tickets
        ADD COLUMN csat_responded_at TEXT NULL
    """)

if "csat_rating" not in columns:
    cursor.execute("""
        ALTER TABLE Freshdesk_tickets
        ADD COLUMN csat_rating INTEGER NULL
    """)

if "csat_feedback" not in columns:
    cursor.execute("""
        ALTER TABLE Freshdesk_tickets
        ADD COLUMN csat_feedback TEXT NULL
    """)

conn.commit()


# ---------------------------------------------------------
# Freshdesk CSAT API
# ---------------------------------------------------------

url = (
    f"{FRESHDESK_DOMAIN}/api/v2/customer-satisfaction/"
    f"surveys/{SURVEY_ID}/responses?per_page=100"
)

page = 1
total_responses = 0
group_responses = 0
complete_responses = 0
updated_tickets = 0
tickets_not_found = 0


while url:

    print(f"\nFetching CSAT page {page}...")

    response = requests.get(
        url,
        auth=HTTPBasicAuth(FRESHDESK_API_KEY, "X"),
        verify=False
    )

    if response.status_code != 200:
        print(f"ERROR {response.status_code}: {response.text}")
        break

    data = response.json()
    responses = data.get("data", [])

    total_responses += len(responses)

    for survey_response in responses:

        # -------------------------------------------------
        # Only process our group
        # -------------------------------------------------

        if survey_response.get("group_id") != TARGET_GROUP_ID:
            continue

        group_responses += 1

        # -------------------------------------------------
        # Only process completed surveys
        # -------------------------------------------------

        if survey_response.get("status") != "COMPLETE":
            continue

        complete_responses += 1

        freshdesk_id = survey_response.get("ticket_id")

        if not freshdesk_id:
            continue

        # -------------------------------------------------
        # Extract rating and feedback
        # -------------------------------------------------

        rating = None
        feedback = None

        for answer in survey_response.get("answers", []):

            question_id = answer.get("question_id")
            value = answer.get("value")

            if question_id == "Q_1":
                rating = value

            elif isinstance(value, str) and value.strip():
                feedback = value.strip()

        # -------------------------------------------------
        # Response timestamp
        # -------------------------------------------------

        csat_responded_at = survey_response.get("updated_at")

        # -------------------------------------------------
        # Update existing Freshdesk ticket
        # -------------------------------------------------

        cursor.execute(
            """
            UPDATE Freshdesk_tickets
            SET
                csat_responded_at = ?,
                csat_rating = ?,
                csat_feedback = ?
            WHERE id = ?
            """,
            (
                csat_responded_at,
                rating,
                feedback,
                freshdesk_id
            )
        )

        if cursor.rowcount > 0:
            updated_tickets += 1
        else:
            tickets_not_found += 1

    conn.commit()

    print(
        f"Returned: {len(responses)} | "
        f"Group: {group_responses} | "
        f"Complete: {complete_responses} | "
        f"Updated: {updated_tickets}"
    )

    # -----------------------------------------------------
    # Token-based pagination
    # -----------------------------------------------------

    url = data.get("paging", {}).get("next")
    page += 1


# ---------------------------------------------------------
# Summary
# ---------------------------------------------------------

conn.close()

print("\n========================================")
print("CSAT BACKFILL COMPLETE")
print("========================================")
print(f"Total API responses:     {total_responses}")
print(f"Target group responses:  {group_responses}")
print(f"Complete responses:      {complete_responses}")
print(f"Tickets updated:         {updated_tickets}")
print(f"Tickets not found:       {tickets_not_found}")
print("========================================")