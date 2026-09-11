import requests
from requests.auth import HTTPBasicAuth

from config.config import (
    JIRA_BASE_URL,
    JIRA_EMAIL,
    JIRA_API_TOKEN
)


headers = {
    "Accept": "application/json"
}


def flatten_adf(node):
    """
    Recursively extracts plain text from Atlassian Document Format (ADF).
    """

    if not node:
        return ""

    if isinstance(node, list):
        return "\n".join(
            filter(
                None,
                (flatten_adf(item) for item in node)
            )
        )

    if not isinstance(node, dict):
        return ""

    text = ""

    if node.get("type") == "text":
        text += node.get("text", "")

    if "content" in node:

        child_text = "".join(
            flatten_adf(child)
            for child in node["content"]
        )

        if node.get("type") == "paragraph":
            child_text += "\n"

        text += child_text

    return text.strip()



def fetch_jira_issues(
    project_key,
    updated_since=None
):
    """
    Fetches all Jira issues for a project.
    """

    url = f"{JIRA_BASE_URL}/rest/api/3/search/jql"

    jql = f'project = "{project_key}"'

    if updated_since:
        jql += (
        f' AND updated >= "{updated_since}"'
        )

    jql += " ORDER BY updated DESC"

    results = []

    body = {
        "jql": jql,
        "maxResults": 100,
        "fields": [
            "summary",
            "description",
            "status",
            "created",
            "updated"
        ]
    }

    while True:

        response = requests.post(
            url,
            json=body,
            headers=headers,
            auth=HTTPBasicAuth(
                JIRA_EMAIL,
                JIRA_API_TOKEN
            )
        )

        if response.status_code != 200:
            print(response.text)
            return []

        data = response.json()
        issues = data.get(
            "issues",
            []
        )

        if not issues:
            break

        for issue in issues:

            results.append({
                "key": issue["key"],
                "project": project_key,
                "summary": issue["fields"]["summary"],
                "description": flatten_adf(
                    issue["fields"]["description"]
                ),
                "status": issue["fields"]["status"]["name"],
                "created_at": issue["fields"]["created"],
                "updated_at": issue["fields"]["updated"],
            })
        print(f"Total fetched: {len(results)}")
        next_page_token = data.get(
            "nextPageToken"
        )

        if not next_page_token:
            break

        body["nextPageToken"] = next_page_token

    return results

def fetch_jira_comments(issue_key):
    """
    Fetches comments for a Jira issue.
    """

    url = (
        f"{JIRA_BASE_URL}/rest/api/3/issue/"
        f"{issue_key}/comment"
    )

    response = requests.get(
        url,
        headers=headers,
        auth=HTTPBasicAuth(
            JIRA_EMAIL,
            JIRA_API_TOKEN
        )
    )

    if response.status_code != 200:
        print(response.text)
        return []

    comments = response.json().get(
        "comments",
        []
    )

    results = []

    for comment in comments:

        results.append({
            "comment_id": comment["id"],
            "issue_key": issue_key,
            "author": comment["author"]["displayName"],
            "body": flatten_adf(comment["body"]),
            "created_at": comment["created"]
        })

    return results