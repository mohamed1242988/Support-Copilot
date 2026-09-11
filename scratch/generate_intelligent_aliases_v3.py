# scratch/generate_intelligent_aliases_v3.py
"""Generate smarter aliases for customers.

Logic:
1. Ensure the `alias` column exists (creates it if missing) and adds an index.
2. For each customer (rowid, Name):
   - Clean the name (strip trailing parentheses content).
   - If the cleaned name is a single word, skip alias generation – the name itself is already concise.
   - Otherwise build a set of candidate aliases:
        a) **Initials** – first letters of each capitalised word in the name.
        b) **Frequent tokens** from ticket `subject` and `description_text` (lower‑cased alphanum tokens,
           keep those that appear at least 3 times for that customer).
        c) **Email usernames** extracted from the `body_text` of all conversations belonging to tickets of
           that customer.  The pattern is any word containing "@" followed by a domain.  The part before "@"
           (the username) is taken, lower‑cased, and stripped of non‑alphanum characters.  Usernames from the
           internal domain "uplandsoftware" are ignored.
   - Keep at most three distinct aliases (initials + up to two others) and store them as a comma‑separated
     string in `customers.alias`.
3. Print a compact JSON report of the customers that received an alias.

Run with:
    python scratch\generate_intelligent_aliases_v3.py
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
    return re.sub(r"\s*\(.*?\)\s*", "", name).strip()

def _initials(name: str) -> str:
    words = re.findall(r"[A-Z][a-zA-Z]*", name)
    return "".join(w[0] for w in words).lower() if words else ""

def _ticket_tokens(customer_id: int) -> set:
    """Collect frequent tokens from subject and description_text for a given customer."""
    with _conn() as conn:
        rows = conn.execute(
            "SELECT subject, description_text FROM Freshdesk_tickets WHERE Customer_ID = ?",
            (customer_id,)
        ).fetchall()
    token_counter = Counter()
    for row in rows:
        for field in (row["subject"], row["description_text"]):
            if not field:
                continue
            # simple tokenisation: lower‑case, keep alphanum, split on whitespace
            for token in field.lower().split():
                token = "".join(_word_regex.findall(token))
                if 1 < len(token) <= 12:  # ignore 1‑char tokens, limit length
                    token_counter[token] += 1
    # keep tokens that appear at least 3 times
    return {tok for tok, cnt in token_counter.items() if cnt >= 3}

def _email_usernames(customer_id: int) -> set:
    """Extract the part before '@' from any email appearing in conversation body_text.
    Conversations are linked to tickets via ticket_id.
    """
    usernames = set()
    with _conn() as conn:
        # First find ticket ids for this customer
        ticket_ids = [r["id"] for r in conn.execute(
            "SELECT id FROM Freshdesk_tickets WHERE Customer_ID = ?",
            (customer_id,)
        ).fetchall()]
        if not ticket_ids:
            return usernames
        # Then fetch conversations for those tickets
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
            # Skip single‑word names
            if len(name.split()) <= 1:
                continue
            aliases = set()
            # initials
            ini = _initials(name)
            if ini:
                aliases.add(ini)
            # frequent token from tickets
            aliases.update(_ticket_tokens(cid))
            # email usernames from conversations
            aliases.update(_email_usernames(cid))
            if not aliases:
                continue
            # Keep at most MAX_ALIASES, preserve order (initials first)
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
