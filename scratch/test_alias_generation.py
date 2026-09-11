# scratch/test_alias_generation.py
"""Dry‑run version of the alias generator.

It reads the same database, computes the candidate aliases for each customer
(using initials, frequent ticket tokens, and email domains from conversation
bodies), but **does NOT modify the `customers.alias` column**.  Instead it prints
a JSON report of what *would* be written.

Usage:
    python scratch\test_alias_generation.py            # runs against the
                                                        # production DB (read‑only)
    python scratch\test_alias_generation.py copy.db    # run against a copy of
                                                        # the DB for safe testing
"""

import sys
import sqlite3
import json
import re
from collections import Counter
from pathlib import Path

# ---------------------------------------------------------------
# Configuration – adjust if you want to point at a different DB.
# ---------------------------------------------------------------
DEFAULT_DB = Path(r"c:/AI Project/SupportCopilot/storage/support_copilot.db")
MAX_ALIASES = 3
EXCLUDE_DOMAIN = "uplandsoftware"

_word_regex = re.compile(r"[a-z0-9]+")
_email_regex = re.compile(r"([A-Za-z0-9._%+-]+)@([A-Za-z0-9.-]+\.[A-Za-z]{2,})")


def _conn(db_path: Path):
    # read‑only connection – no timeout needed for dry run.
    conn = sqlite3.connect(str(db_path), timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


def _clean_name(name: str) -> str:
    return re.sub(r"\s*\(.*?\)\s*", "", name).strip()


def _initials(name: str) -> str:
    words = re.findall(r"[A-Z][a-zA-Z]*", name)
    return "".join(w[0] for w in words).lower() if words else ""


def _ticket_tokens(conn, customer_id: int) -> set:
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


def _email_domains(conn, customer_id: int) -> set:
    domains = set()
    ticket_ids = [r["id"] for r in conn.execute(
        "SELECT id FROM Freshdesk_tickets WHERE Customer_ID = ?",
        (customer_id,)
    ).fetchall()]
    if not ticket_ids:
        return domains
    placeholders = ",".join(["?"] * len(ticket_ids))
    query = f"SELECT body_text FROM Freshdesk_conversations WHERE ticket_id IN ({placeholders})"
    rows = conn.execute(query, ticket_ids).fetchall()
    for row in rows:
        body = row["body_text"]
        if not body:
            continue
        for match in _email_regex.finditer(body):
            _, domain = match.groups()
            domain = domain.lower()
            if EXCLUDE_DOMAIN in domain:
                continue
            domains.add(domain)
    return domains


def main():
    db_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DB
    if not db_path.exists():
        print(json.dumps({"error": f"Database not found: {db_path}"}, indent=2))
        return
    report = []
    with _conn(db_path) as conn:
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
            aliases.update(_ticket_tokens(conn, cid))
            aliases.update(_email_domains(conn, cid))
            if not aliases:
                continue
            # order: initials first, then any others, up to MAX_ALIASES
            ordered = []
            if ini and ini in aliases:
                ordered.append(ini)
                aliases.remove(ini)
            for a in list(aliases)[: MAX_ALIASES - len(ordered)]:
                ordered.append(a)
            alias_str = ",".join(ordered)
            report.append({
                "customer_id": cid,
                "customer_name": raw_name,
                "proposed_alias": alias_str,
            })
    print(json.dumps({"dry_run": True, "proposed": report}, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
