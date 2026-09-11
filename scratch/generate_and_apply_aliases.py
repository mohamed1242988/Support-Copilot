# scratch/generate_and_apply_aliases.py
"""Generate and apply alias strings for customers.

The script:
1. Ensures the `alias` column (and index) exist on the `customers` table.
2. For every customer, gathers words from:
   - Freshdesk_tickets.subject
   - Freshdesk_tickets.description_text
   - Freshdesk_conversations.body_text (conversation text)
3. Removes stop‑words, punctuation and any word that already appears in the official
   customer name.
4. Counts word frequencies and selects the top 3 most frequent words as candidate
   aliases.
5. Stores a comma‑separated list of these aliases in `customers.alias`.
6. Prints a JSON summary of updates.

Run it from the project root (c:/AI Project/SupportCopilot):
    python scratch/generate_and_apply_aliases.py
"""

import sqlite3
import json
import re
import collections
from pathlib import Path

# ----------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------
DB_PATH = Path(r"c:/AI Project/SupportCopilot/storage/support_copilot.db")
STOP_WORDS = {
    "the", "and", "or", "a", "an", "of", "for", "to", "in", "on",
    "with", "by", "at", "from", "as", "is", "are", "was", "were",
    "it", "its", "this", "that", "these", "those", "i", "you", "we",
    "they", "them", "us", "our", "your", "their", "customer", "inc",
    "psa", "company", "corp", "ltd",
}
MAX_ALIASES_PER_CUSTOMER = 3

# ----------------------------------------------------------------------
# Helper utilities
# ----------------------------------------------------------------------
def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def _ensure_alias_column():
    """Create the alias column and an index if they do not already exist."""
    with _conn() as conn:
        cols = [c["name"] for c in conn.execute("PRAGMA table_info(customers)")]
        if "alias" not in cols:
            conn.execute("ALTER TABLE customers ADD COLUMN alias TEXT")
            conn.commit()
        conn.execute("CREATE INDEX IF NOT EXISTS idx_customers_alias ON customers(alias)")
        conn.commit()

_word_regex = re.compile(r"[A-Za-z0-9]+")

def _tokenize(text: str):
    return [tok.lower() for tok in _word_regex.findall(text or "")]

def _clean_name(name: str):
    # Return a set of lower‑cased words that belong to the formal name
    return set(_tokenize(name))

def _extract_candidate_aliases(customer_id: int, name_words: set):
    """Collect frequent words from tickets & conversations for a given customer.
    Returns a list of up to MAX_ALIASES_PER_CUSTOMER strings.
    """
    with _conn() as conn:
        # Gather ticket subject & description_text for this customer
        tickets = conn.execute(
            """
            SELECT subject, description_text
            FROM Freshdesk_tickets
            WHERE Customer_ID = ?
            """,
            (customer_id,),
        ).fetchall()

        # Gather conversation body_text linked via ticket_id
        convos = conn.execute(
            """
            SELECT fc.body_text
            FROM Freshdesk_conversations fc
            JOIN Freshdesk_tickets ft ON ft.id = fc.ticket_id
            WHERE ft.Customer_ID = ?
            """,
            (customer_id,),
        ).fetchall()

    # Count words across all collected text
    counter = collections.Counter()
    for row in tickets:
        for field in (row["subject"], row["description_text"]):
            for tok in _tokenize(field or ""):
                if tok not in STOP_WORDS and tok not in name_words:
                    counter[tok] += 1
    for row in convos:
        for tok in _tokenize(row["body_text"] or ""):
            if tok not in STOP_WORDS and tok not in name_words:
                counter[tok] += 1

    # Pick the most common words (up to MAX_ALIASES_PER_CUSTOMER)
    aliases = [word for word, _ in counter.most_common(MAX_ALIASES_PER_CUSTOMER)]
    return aliases

def main():
    _ensure_alias_column()
    report = []
    with _conn() as conn:
        customers = conn.execute("SELECT rowid AS id, Name FROM customers").fetchall()
        for cust in customers:
            cid = cust["id"]
            name = cust["Name"]
            name_words = _clean_name(name)
            aliases = _extract_candidate_aliases(cid, name_words)
            if not aliases:
                continue
            alias_str = ",".join(aliases)  # comma‑separated list stored in DB
            # Update only if the value changed (avoid unnecessary writes)
            cur_val = conn.execute(
                "SELECT alias FROM customers WHERE rowid = ?", (cid,)
            ).fetchone()["alias"]
            if cur_val != alias_str:
                conn.execute(
                    "UPDATE customers SET alias = ? WHERE rowid = ?",
                    (alias_str, cid),
                )
                report.append({
                    "customer_id": cid,
                    "customer_name": name,
                    "new_alias": alias_str,
                })
        conn.commit()
    # ------------------------------------------------------------------
    # Output the summary JSON for the user to review
    # ------------------------------------------------------------------
    if report:
        print(json.dumps({"updated": report}, indent=2, ensure_ascii=False))
    else:
        print(json.dumps({"updated": []}, indent=2))

if __name__ == "__main__":
    main()
