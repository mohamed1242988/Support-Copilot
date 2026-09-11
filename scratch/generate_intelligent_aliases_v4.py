# scratch/generate_intelligent_aliases_v4.py
"""Generate smarter aliases for customers.

Enhanced logic:
1. Ensure the `alias` column exists (creates it if missing) and adds an index.
2. For each customer (rowid, Name):
   - Clean the name (strip trailing parentheses content).
   - Skip alias generation for single‑word names.
   - Build a set of candidate aliases:
        a) **Initials** – first letters of each capitalised word.
        b) **Frequent tokens** from ticket `subject` and `description_text` (appear ≥3 times).
        c) **Email usernames** extracted from conversation `body_text` (regex for @domain), ignoring the internal domain "uplandsoftware".
   - Keep at most three distinct aliases (initials first, then others) and store them as a comma‑separated string in `customers.alias`.
3. Print a compact JSON report of customers that received/updated an alias.

Run with:
    python scratch\generate_intelligent_aliases_v4.py
"""

import sqlite3
import json
import re
from collections import Counter
from pathlib import Path

DB_PATH = Path(r"c:/AI Project/SupportCopilot/storage/support_copilot.db")
MAX_ALIASES = 3
EXCLUDE_DOMAIN = "uplandsoftware"

_word_regex = re.compile(r"[a-z0-9]+")
_email_regex = re.compile(r"([A-Za-z0-9._%+-]+)@([A-Za-z0-9.-]+\.[A-Za-z]{2,})")

def _conn():
    # Use a longer timeout to avoid "database is locked" errors.
    conn = sqlite3.connect(DB_PATH, timeout=30)
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
    return re.sub(r"\s*\(.*?\)\s*", "", name).strip()

def _initials(name: str) -> str:
    words = re.findall(r"[A-Z][a-zA-Z]*", name)
    return "".join(w[0] for w in words).lower() if words else ""

def _ticket_tokens(customer_id: int) -> set:
    """Collect tokens that appear frequently in a customer's tickets."""
    with _conn() as conn:
        rows = conn.execute(
            "SELECT subject, description_text FROM Freshdesk_tickets WHERE Customer_ID = ?",
            (customer_id,)
        ).fetchall()
    counter = Counter()
    for row in rows:
        for field in (row["subject"], row["description_text"]):
            if not field:
                continue
            for token in field.lower().split():
                token = "".join(_word_regex.findall(token))
                if 1 < len(token) <= 12:
                    counter[token] += 1
    return {tok for tok, cnt in counter.items() if cnt >= 3}

def _email_usernames(customer_id: int) -> set:
    """Extract usernames from any email address found in conversation bodies for the customer."""
    usernames = set()
    with _conn() as conn:
        ticket_ids = [r["id"] for r in conn.execute(
            "SELECT id FROM Freshdesk_tickets WHERE Customer_ID = ?",
            (customer_id,)
        ).fetchall()]
        if not ticket_ids:
            return usernames
        placeholders = ",".join(["?"] * len(ticket_ids))
        query = f"SELECT body_text FROM Freshdesk_conversations WHERE ticket_id IN ({placeholders})"
        rows = conn.execute(query, ticket_ids).fetchall()
    for row in rows:
        body = row["body_text"]
        if not body:
            continue
        for match in _email_regex.finditer(body):
            username, domain = match.groups()
            if EXCLUDE_DOMAIN in domain.lower():
                continue
            username = "".join(_word_regex.findall(username.lower()))
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
            if len(name.split()) <= 1:
                continue
            aliases = set()
            ini = _initials(name)
            if ini:
                aliases.add(ini)
            aliases.update(_ticket_tokens(cid))
            aliases.update(_email_usernames(cid))
            if not aliases:
                continue
            ordered = []
            if ini and ini in aliases:
                ordered.append(ini)
                aliases.remove(ini)
            for a in list(aliases)[: MAX_ALIASES - len(ordered)]:
                ordered.append(a)
            alias_str = ",".join(ordered)
            cur_val = conn.execute("SELECT alias FROM customers WHERE rowid = ?", (cid,)).fetchone()["alias"]
            if cur_val != alias_str:
                conn.execute("UPDATE customers SET alias = ? WHERE rowid = ?", (alias_str, cid))
                report.append({"customer_id": cid, "customer_name": raw_name, "new_alias": alias_str})
        conn.commit()
    print(json.dumps({"updated": report}, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
