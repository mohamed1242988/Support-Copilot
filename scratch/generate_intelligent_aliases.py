# scratch/generate_intelligent_aliases.py
"""Generate smarter aliases for customers.

Approach:
1. Ensure the `alias` column exists (lazy migration).
2. For each customer:
   * If the official name is a **single word** (after stripping parentheses), we keep the alias empty – the name itself is already short.
   * Otherwise we build a set of candidate aliases:
        - **Initials**: first letters of each capitalised word in the name (e.g., "Business Development Bank of Canada" → "bdc").
        - **Email usernames** found in tickets for that customer, **excluding** any address that contains "uplandsoftware" (the internal domain).
        - Simple token cleanup (lower‑case, remove punctuation).
   * Keep at most three distinct aliases, join them with commas, and store them in the `customers.alias` column.
3. Print a compact JSON report of the customers that received aliases.

Run with:
    python scratch/generate_intelligent_aliases.py
"""

import sqlite3
import json
import re
from pathlib import Path

DB_PATH = Path(r"c:/AI Project/SupportCopilot/storage/support_copilot.db")
MAX_ALIASES = 3
EXCLUDE_DOMAIN = "uplandsoftware"

_word_regex = re.compile(r"[A-Za-z0-9]+")

def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def _ensure_alias_column():
    with _conn() as conn:
        cols = [c["name"] for c in conn.execute("PRAGMA table_info(customers)")]
        if "alias" not in cols:
            conn.execute("ALTER TABLE customers ADD COLUMN alias TEXT")
            conn.commit()
        conn.execute("CREATE INDEX IF NOT EXISTS idx_customers_alias ON customers(alias)")
        conn.commit()

def _clean_name(name: str) -> str:
    # Remove trailing parentheses content and extra spaces
    name = re.sub(r"\s*\(.*?\)\s*", "", name).strip()
    return name

def _initials(name: str) -> str:
    words = [w for w in re.findall(r"[A-Z][a-zA-Z]*", name)]
    if not words:
        return ""
    return "".join(w[0] for w in words).lower()

def _extract_email_usernames(customer_id: int) -> set:
    """Collect the part before '@' of ticket email fields, excluding internal domain."""
    usernames = set()
    with _conn() as conn:
        rows = conn.execute(
            "SELECT email FROM Freshdesk_tickets WHERE Customer_ID = ?",
            (customer_id,)
        ).fetchall()
    for row in rows:
        email = row["email"]
        if not email or EXCLUDE_DOMAIN in email.lower():
            continue
        username = email.split('@')[0].lower()
        # simple cleanup – keep alphanum only
        username = "".join(_word_regex.findall(username))
        if username:
            usernames.add(username)
    return usernames

def main():
    _ensure_alias_column()
    report = []
    with _conn() as conn:
        customers = conn.execute("SELECT rowid AS id, Name FROM customers").fetchall()
        for cust in customers:
            cid = cust["id"]
            raw_name = cust["Name"]
            name = _clean_name(raw_name)
            # If name is a single word, skip alias generation
            if len(name.split()) <= 1:
                continue
            aliases = set()
            # 1️⃣ initials
            ini = _initials(name)
            if ini:
                aliases.add(ini)
            # 2️⃣ email usernames
            aliases.update(_extract_email_usernames(cid))
            # keep only a few
            if not aliases:
                continue
            alias_str = ",".join(list(aliases)[:MAX_ALIASES])
            # Update DB if changed
            cur_val = conn.execute("SELECT alias FROM customers WHERE rowid = ?", (cid,)).fetchone()["alias"]
            if cur_val != alias_str:
                conn.execute("UPDATE customers SET alias = ? WHERE rowid = ?", (alias_str, cid))
                report.append({"customer_id": cid, "customer_name": raw_name, "new_alias": alias_str})
        conn.commit()
    print(json.dumps({"updated": report}, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
