import json
import sys
import requests
from requests.auth import HTTPBasicAuth

# Load project config
sys.path.insert(0, r"c:\AI Project\SupportCopilot")
from config.config import JIRA_BASE_URL, JIRA_EMAIL, JIRA_API_TOKEN

# 1. Provide a specific Issue Key (e.g., 'PROJ-1234') or set to None to fetch the latest issue
ISSUE_KEY = 'TE-107014' 
PROJECT_KEY = "BA"  # Used if ISSUE_KEY is None

headers = {
    "Accept": "application/json"
}
auth = HTTPBasicAuth(JIRA_EMAIL, JIRA_API_TOKEN)

# If no issue key is provided, search for the latest 1 issue
if not ISSUE_KEY:
    search_url = f"{JIRA_BASE_URL}/rest/api/3/search/jql"
    payload = {
        "jql": f'project = "{PROJECT_KEY}" ORDER BY updated DESC',
        "maxResults": 1,
        "fields": ["*all"]
    }
    res = requests.post(search_url, json=payload, headers=headers, auth=auth)
    if res.status_code != 200:
        print(f"Error fetching issue: {res.status_code} - {res.text}")
        sys.exit(1)
    
    issues = res.json().get("issues", [])
    if not issues:
        print(f"No issues found for project '{PROJECT_KEY}'")
        sys.exit(0)
    
    issue_data = issues[0]
    ISSUE_KEY = issue_data["key"]
else:
    # Fetch specific issue with field names and schema expanded
    issue_url = f"{JIRA_BASE_URL}/rest/api/3/issue/{ISSUE_KEY}?expand=names,schema"
    res = requests.get(issue_url, headers=headers, auth=auth)
    if res.status_code != 200:
        print(f"Error fetching issue: {res.status_code} - {res.text}")
        sys.exit(1)
    issue_data = res.json()

print(f"=== Inspecting Jira Issue: {ISSUE_KEY} ===\n")

# Field Names Mapping (Field ID -> Human Readable Name)
# Jira returns names mapping under 'names' if expanded or we can inspect fields directly
field_names = issue_data.get("names", {})
fields = issue_data.get("fields", {})

print(f"{'Field ID':<30} | {'Field Display Name':<35} | Sample Value (preview)")
print("-" * 100)

for field_id, value in fields.items():
    if value is not None:
        display_name = field_names.get(field_id, field_id)
        val_str = str(value)
        preview = (val_str[:50] + "...") if len(val_str) > 50 else val_str
        print(f"{field_id:<30} | {display_name:<35} | {preview}")

# Optional: Save complete raw payload to inspect nested structures (ADF description, sub-objects, etc.)
output_filename = f"jira_{ISSUE_KEY}_payload.json"
with open(output_filename, "w", encoding="utf-8") as f:
    json.dump(issue_data, f, indent=2, ensure_ascii=False)

print(f"\n[✓] Full raw JSON saved to '{output_filename}' for deep inspection.")