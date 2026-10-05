"""Persistent corpus statistics and query anchor classification."""

from __future__ import annotations

import math
import re
from collections import defaultdict
from datetime import datetime, timezone

from storage.database import get_connection


GENERIC_TERMS = {
    "a", "an", "and", "are", "be", "for", "from", "in", "is", "issue",
    "issues", "problem", "process", "request", "setup", "the", "to", "with",
}


def normalize_terms(text: str) -> set[str]:
    return {
        token for token in re.findall(r"[a-z0-9]+", (text or "").lower())
        if len(token) >= 2
    }


def _known_entity_terms(connection) -> set[str]:
    rows = connection.execute(
        "SELECT Name, alias FROM customers"
    ).fetchall()
    entities = set()
    for name, alias in rows:
        for value in (name, alias):
            if value:
                entities.add(re.sub(r"[^a-z0-9]", "", value.lower()))
    return entities


def refresh_search_term_stats() -> None:
    """Rebuild document frequencies from the local Freshdesk corpus."""
    connection = get_connection()
    try:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS search_term_stats (
                term TEXT NOT NULL,
                field TEXT NOT NULL,
                document_frequency INTEGER NOT NULL,
                total_documents INTEGER NOT NULL,
                idf REAL NOT NULL,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (term, field)
            )
            """
        )
        ticket_rows = connection.execute(
            "SELECT id, subject, description_text FROM freshdesk_tickets"
        ).fetchall()
        conversation_rows = connection.execute(
            "SELECT ticket_id, body_text FROM freshdesk_conversations"
        ).fetchall()
        total_tickets = len(ticket_rows)
        frequencies = defaultdict(set)
        for ticket_id, subject, description in ticket_rows:
            frequencies[("subject",)].update(
                (term, ticket_id) for term in normalize_terms(subject)
            )
            frequencies[("description",)].update(
                (term, ticket_id) for term in normalize_terms(description)
            )
        for ticket_id, body in conversation_rows:
            frequencies[("conversation",)].update(
                (term, ticket_id) for term in normalize_terms(body)
            )

        now = datetime.now(timezone.utc).isoformat()
        connection.execute("DELETE FROM search_term_stats")
        for (field,), values in frequencies.items():
            by_term = defaultdict(set)
            for term, ticket_id in values:
                by_term[term].add(ticket_id)
            for term, ticket_ids in by_term.items():
                frequency = len(ticket_ids)
                idf = math.log((total_tickets + 1) / (frequency + 1)) + 1
                connection.execute(
                    """
                    INSERT INTO search_term_stats
                    (term, field, document_frequency, total_documents, idf, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (term, field, frequency, total_tickets, idf, now),
                )
        connection.commit()
    finally:
        connection.close()


def classify_query_terms(query: str) -> dict[str, str]:
    """Classify query terms using subject-level rarity and generic-term rules."""
    connection = get_connection()
    try:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS search_term_stats (
                term TEXT NOT NULL,
                field TEXT NOT NULL,
                document_frequency INTEGER NOT NULL,
                total_documents INTEGER NOT NULL,
                idf REAL NOT NULL,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (term, field)
            )
            """
        )
        rows = connection.execute(
            """
            SELECT term, field, document_frequency, total_documents, idf
            FROM search_term_stats
            WHERE field IN ('subject', 'description')
            """
        ).fetchall()
        known_entities = _known_entity_terms(connection)
    finally:
        connection.close()

    stats = defaultdict(dict)
    for term, field, frequency, total, idf in rows:
        stats[term][field] = {
            "frequency": frequency,
            "total": total,
            "idf": idf,
        }

    classifications = {}
    for term in normalize_terms(query):
        compact_term = term.replace(" ", "")
        if any(
            compact_term in entity or entity in compact_term
            for entity in known_entities
            if len(compact_term) >= 4
        ):
            classifications[term] = "strong"
            continue
        if term in GENERIC_TERMS:
            classifications[term] = "supporting"
            continue
        subject = stats.get(term, {}).get("subject")
        if subject and subject["frequency"] <= max(5, subject["total"] * 0.05):
            classifications[term] = "strong"
        elif subject and subject["frequency"] <= subject["total"] * 0.20:
            classifications[term] = "medium"
        else:
            classifications[term] = "supporting"
    return classifications
