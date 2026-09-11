import sqlite3
import re
import json
from pathlib import Path
from typing import List, Dict

# ----------------------------------------------------------------------
# Configuration (paths)
# ----------------------------------------------------------------------
DB_PATH = Path(r"c:/AI Project/SupportCopilot/storage/support_copilot.db")

# ----------------------------------------------------------------------
# Helper: same alias‑generation logic used for the CSV script
# ----------------------------------------------------------------------
def _initials(name: str) -> str:
    words = re.findall(r"[A-Z][a-zA-Z]*", name)
    return "".join(w[0] for w in words if w).upper()

def _simple_alias(name: str) -> str:
    clean = re.sub(r"[()\[\]{}]", "", name).lower()
    clean = re.sub(r"\s+", "", clean)
    return clean

def _candidate_aliases(name: str) -> List[str]:
    cand = set()
    cand.add(_simple_alias(name))
    ini = _initials(name)
    if 2 <= len(ini) <= 6:
        cand.add(ini.lower())
    m = re.search(r"^(.*?)\s*\(.*?\)\s*$", name)
    if m:
        cand.add(_simple_alias(m.group(1)))
    return list(cand)

# ----------------------------------------------------------------------
# Minimal DB helpers (reuse the same connection logic as the project)
# ----------------------------------------------------------------------
def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def query_database(sql: str) -> List[Dict]:
    """
    Lightweight version of the project's query_database.
    It already contains the alias‑rewrite logic, but we duplicate it here
    to keep this script independent.
    """
    # ---- alias rewrite (copy‑paste of the project's helper) ----
    import re
    pattern = re.compile(
        r"(Customer_Name|Name)\s+LIKE\s+('.*?%[^']+%')",
        flags=re.IGNORECASE,
    )
    def repl(m):
        col, like_expr = m.groups()
        return f"({col} LIKE {like_expr} OR alias LIKE {like_expr})"
    sql = pattern.sub(repl, sql)

    # ---- basic read‑only check (same as project) ----
    sql_clean = sql.strip().lower()
    if not (sql_clean.startswith("select") or sql_clean.startswith("with")):
        raise ValueError("Only SELECT/WITH allowed")

    # ---- execute ----
    with _conn() as conn:
        cur = conn.execute(sql)
        rows = cur.fetchmany(200)  # safe limit
        return [dict(r) for r in rows]

# ----------------------------------------------------------------------
# Core logic: walk through every customer, compare name vs. alias hits
# ----------------------------------------------------------------------
def sync_aliases():
    report = []

    with _conn() as conn:
        customers = conn.execute("SELECT rowid AS id, Name, alias FROM customers").fetchall()

    for cust in customers:
        cid = cust["id"]
        name = cust["Name"]
        current_alias = cust["alias"] or ""

        # ---- tickets found by *exact* name search ----
        name_sql = f"""
            SELECT id FROM Freshdesk_tickets
            WHERE Customer_Name LIKE '%{name.replace("'", "''")}%'
        """
        tickets_by_name = {row["id"] for row in query_database(name_sql)}

        # ---- generate alias candidates ----
        candidates = _candidate_aliases(name)

        # ---- tickets found by each candidate (using the project's alias‑aware query) ----
        tickets_by_alias = set()
        matched_candidate = None
        for cand in candidates:
            alias_sql = f"""
                SELECT id FROM Freshdesk_tickets
                WHERE Customer_Name LIKE '%{cand}%'
            """
            rows = query_database(alias_sql)
            ids = {r["id"] for r in rows}
            if ids:
                matched_candidate = cand
                tickets_by_alias.update(ids)

        # If the alias search yields **more** tickets than the name search,
        # we consider the candidate a useful alias and store it.
        if tickets_by_alias - tickets_by_name:
            new_alias = matched_candidate or candidates[0]
            if new_alias != current_alias:
                # Update the DB
                with _conn() as conn:
                    conn.execute(
                        "UPDATE customers SET alias = ? WHERE rowid = ?",
                        (new_alias, cid)
                    )
                    conn.commit()
                report.append({
                    "customer_id": cid,
                    "customer_name": name,
                    "old_alias": current_alias,
                    "new_alias": new_alias,
                    "added_tickets": list(tickets_by_alias - tickets_by_name),
                })

    # ------------------------------------------------------------------
    # Pretty‑print the report (JSON is easy to read)
    # ------------------------------------------------------------------
    if report:
        print("=== Alias sync report ===")
        print(json.dumps(report, indent=2))
    else:
        print("No new aliases were needed – all customers already had useful aliases.")

if __name__ == "__main__":
    sync_aliases()