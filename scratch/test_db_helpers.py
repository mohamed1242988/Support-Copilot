# scratch/test_db_helpers.py
import sys
sys.path.append('c:/AI Project/SupportCopilot')   # make the project importable

from services.db_helpers import query_database, get_database_schema

def main():
    # 1️⃣ Load schema (should be cached on second call)
    schema = get_database_schema()
    print("✅ Schema loaded. Tables:", list(schema['tables'].keys())[:5])

    # 2️⃣ Run a simple validated query (no LIMIT → default 100 will be added)
    try:
        rows = query_database(
            "SELECT id, subject, Customer_Name FROM Freshdesk_tickets "
            "WHERE Customer_Name LIKE '%Mary Kay%'"
        )
        print(f"✅ Query succeeded – returned {len(rows)} rows (max 100).")
        for row in rows[:5]:
            print(row)
    except Exception as e:
        print("❌ Query error:", e)

    # 3️⃣ Try an invalid column to see the validation error
    try:
        query_database("SELECT created_by FROM Freshdesk_tickets LIMIT 1")
    except Exception as e:
        print("✅ Expected validation error:", e)

if __name__ == '__main__':
    main()