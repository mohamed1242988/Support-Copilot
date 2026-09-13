from datetime import datetime, timezone, timedelta 

from storage.database import (
    initialize_database,
    save_ticket,
    save_conversations,
    get_sync_state,
    update_sync_state,
    save_jira_issue,
    save_jira_comment
)

from integrations.freshdesk import (
    get_or_create_customer,
    search_tickets,
    get_ticket_details,
    get_agent_name
)

from integrations.jira import (
    fetch_jira_issues,
    fetch_jira_comments
)





def get_ticket_count_for_range(updated_from, updated_to):
    """
    Returns the total number of Freshdesk tickets
    matching a date range.
    """

    result = search_tickets(
        updated_from=updated_from,
        updated_to=updated_to,
        page=1
    )

    return result["total"]

def sync_date_range_with_split(updated_from, updated_to):
    """
    Synchronizes a date range.
    If Freshdesk result count exceeds the API limit,
    split the range into smaller chunks.
    """

    total = get_ticket_count_for_range(
        updated_from,
        updated_to
    )

    print(
        f"Date range {updated_from} -> {updated_to} contains {total} tickets"
    )


    if total <= 300:

        return sync_date_range(
            updated_from,
            updated_to
        )

        


    print(
        "Range exceeds Freshdesk limit. Splitting..."
    )


    start = datetime.fromisoformat(
        updated_from.replace("Z", "")
    )

    end = datetime.fromisoformat(
        updated_to.replace("Z", "")
    )


    middle = start + (
        (end - start) / 2
    )


    middle_date = middle.strftime(
        "%Y-%m-%d"
    )


    left = sync_date_range_with_split(
    updated_from,
    middle_date
)

    right = sync_date_range_with_split(
    middle_date,
    updated_to
    )

    return max(
    x for x in (left, right)
    if x is not None
    )

def sync_date_range(updated_from, updated_to):
    """
    Synchronizes Freshdesk tickets for a specific date range.
    """

    page = 1

    latest_updated = None

    while True:

        if page > 10:
            print(
                "Freshdesk page limit reached. Date range needs splitting."
            )
            break

        print(f"Searching page {page}...")

        result = search_tickets(
            updated_from=updated_from,
            updated_to=updated_to,
            page=page
        )

        tickets = result["results"]

        print(
            f"Page {page}: {len(tickets)} tickets found"
        )

        if not tickets:
            break


        for ticket in tickets:

            ticket_id = ticket["id"]

            print(
                f"Synchronizing ticket {ticket_id}"
            )

            details = get_ticket_details(ticket_id)

            customer_id, customer_name = get_or_create_customer(
                details.get("company_id")
            )

            details["customer_id"] = customer_id
            details["customer_name"] = customer_name
            details["assigned_agent"] = get_agent_name(details.get("responder_id"))

            if (
                latest_updated is None
                or details["updated_at"] > latest_updated
            ):
                latest_updated = details["updated_at"]

            save_ticket(details)

            save_conversations(
                ticket_id,
                details.get("conversations", [])
            )


        page += 1
    return latest_updated



def initial_sync():
    """
    Performs initial synchronization for all Freshdesk history.
    """

    initialize_database()

    date_ranges = [
        ("2026-05-01", "2026-06-01"),
        ("2026-06-01", "2026-07-01"),
        ("2026-07-01", "2026-08-01")
    ]

    for start_date, end_date in date_ranges:

        print(
            f"Syncing range {start_date} -> {end_date}"
        )

        sync_date_range(
            updated_from=start_date,
            updated_to=end_date
        )


    print("Initial synchronization completed.")



def incremental_sync():
    """
    Synchronizes Freshdesk tickets updated since the last sync.
    """

    last_sync = get_sync_state("last_sync")

    if not last_sync:
        print("No previous sync found. Run initial sync first.")
        return

    print(f"Starting incremental sync from {last_sync}")

    current_time = datetime.now(timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )

    latest_updated = sync_date_range_with_split(
        updated_from=last_sync,
        updated_to=current_time
    )

    if latest_updated:
        update_sync_state("last_sync", latest_updated)

    print("Last Freshdesk updated =", latest_updated)
    print("Incremental Freshdesk sync completed.")

def sync_jira_projects(projects):
    """
    Sync Jira issues and comments for provided projects.
    """

    one_year_ago = datetime.now().astimezone() - timedelta(days=365)

    for project in projects:

        print(f"Syncing Jira project: {project}")

        last_sync = get_sync_state(
            f"jira_{project}_last_sync"
        )

        issues = fetch_jira_issues(
            project,
            updated_since=last_sync
        )

        print(f"Fetched {len(issues)} issues")

        for issue in issues:

            save_jira_issue(issue)

            issue_updated = datetime.fromisoformat(
                issue["updated_at"].replace("Z", "+00:00")
            )

            if issue_updated >= one_year_ago.astimezone(issue_updated.tzinfo):

                comments = fetch_jira_comments(
                    issue["key"]
                )

                for comment in comments:
                    save_jira_comment(comment)

        if issues:

            latest_updated = max(
                issue["updated_at"]
                for issue in issues
            )

            update_sync_state(
                f"jira_{project}_last_sync",
                latest_updated
            )

        print(
            f"{project}: {len(issues)} issues synced"
        )