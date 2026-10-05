"""Persistent semantic and hybrid search over indexed Freshdesk chunks."""

from __future__ import annotations

import struct
import sqlite3

from knowledge.embeddings import create_embedding
from knowledge.search_statistics import classify_query_terms, normalize_terms
from knowledge.sqlite_vector import load_sqlite_vec
from storage.database import get_connection, search_local_tickets


RRF_K = 60


def _serialize_embedding(values) -> bytes:
    values = [float(value) for value in values]
    return struct.pack(f"{len(values)}f", *values)


def _ticket_metadata(ticket_ids: set[int]) -> dict[int, dict]:
    if not ticket_ids:
        return {}
    connection = get_connection()
    connection.row_factory = sqlite3.Row
    try:
        placeholders = ",".join("?" for _ in ticket_ids)
        rows = connection.execute(
            f"SELECT * FROM freshdesk_tickets WHERE id IN ({placeholders})",
            tuple(ticket_ids),
        ).fetchall()
        return {int(row["id"]): dict(row) for row in rows}
    finally:
        connection.close()


def _load_complete_tickets(ticket_ids: list[int]) -> dict[int, dict]:
    """Load selected tickets and all their conversations with two queries."""
    if not ticket_ids:
        return {}
    connection = get_connection()
    connection.row_factory = sqlite3.Row
    try:
        placeholders = ",".join("?" for _ in ticket_ids)
        tickets = {
            int(row["id"]): dict(row)
            for row in connection.execute(
                f"SELECT * FROM freshdesk_tickets WHERE id IN ({placeholders})",
                tuple(ticket_ids),
            ).fetchall()
        }
        conversations = connection.execute(
            f"""
            SELECT *
            FROM freshdesk_conversations
            WHERE ticket_id IN ({placeholders})
            ORDER BY ticket_id, created_at
            """,
            tuple(ticket_ids),
        ).fetchall()
        for ticket in tickets.values():
            ticket["conversations"] = []
        for row in conversations:
            ticket = tickets.get(int(row["ticket_id"]))
            if ticket is not None:
                ticket["conversations"].append(dict(row))
        return tickets
    finally:
        connection.close()


def semantic_ticket_ranks(query: str, top_k: int = 100) -> list[dict]:
    """Return ticket-level semantic ranks from the persistent chunk index."""
    connection = get_connection()
    try:
        load_sqlite_vec(connection)
        query_vector = _serialize_embedding(create_embedding(query, is_query=True))
        rows = connection.execute(
            """
            SELECT c.parent_id, c.parent_type, v.distance
            FROM document_chunk_vectors v
            JOIN document_chunks c ON c.id = v.rowid
            WHERE c.source = 'freshdesk'
              AND v.embedding MATCH ?
              AND v.k = ?
            ORDER BY v.distance
            """,
            (query_vector, top_k),
        ).fetchall()
    finally:
        connection.close()

    best_score = {}
    for parent_id, parent_type, distance in rows:
        chunk_weight = 1.0 if parent_type == "ticket" else 0.6
        chunk_score = chunk_weight / (1.0 + float(distance))
        best_score[parent_id] = max(chunk_score, best_score.get(parent_id, 0.0))

    ranked = sorted(best_score.items(), key=lambda item: item[1], reverse=True)
    return [
        {
            "ticket_id": int(ticket_id),
            "semantic_rank": rank,
            "semantic_score": float(score),
        }
        for rank, (ticket_id, score) in enumerate(ranked, start=1)
    ]


def _anchor_candidates(query: str, exclude_ticket_id: int | None = None) -> list[dict]:
    classifications = classify_query_terms(query)
    strong = [term for term, tier in classifications.items() if tier == "strong"]
    medium = [term for term, tier in classifications.items() if tier == "medium"]
    anchor_terms = strong + medium
    if not strong and not medium:
        return []

    connection = get_connection()
    try:
        rows = connection.execute(
            "SELECT id, subject, description_text FROM freshdesk_tickets"
        ).fetchall()
    finally:
        connection.close()

    candidates = []
    for ticket_id, subject, description in rows:
        if ticket_id == exclude_ticket_id:
            continue
        subject_terms = normalize_terms(subject)
        description_terms = normalize_terms(description)
        strong_subject = sum(term in subject_terms for term in strong)
        medium_subject = sum(term in subject_terms for term in medium)
        strong_description = sum(term in description_terms for term in strong)
        medium_description = sum(term in description_terms for term in medium)
        if strong and strong_subject < len(strong) and not (
            strong_subject or strong_description
        ):
            continue
        if not strong and medium_subject == 0 and medium_description == 0:
            continue
        anchor_subject_count = sum(term in subject_terms for term in anchor_terms)
        tier = 2 if anchor_terms and anchor_subject_count == len(anchor_terms) else 1
        match_score = (
            (4 * strong_subject) + (2 * medium_subject) +
            (1.5 * strong_description) + (0.75 * medium_description)
        )
        candidates.append({
            "ticket_id": ticket_id,
            "anchor_tier": tier,
            "anchor_match_score": match_score,
        })
    return candidates


def hybrid_search_freshdesk(
    query: str,
    limit: int = 50,
    exclude_ticket_id: int | None = None,
) -> list[dict]:
    """Fuse local FTS5 and persistent semantic Freshdesk rankings with RRF."""
    candidate_limit = max(limit * 10, 500)
    lexical_results = search_local_tickets(
        query,
        limit=candidate_limit,
        exclude_ticket_id=exclude_ticket_id,
    )
    lexical_by_id = {
        int(result["id"]): {"rank": rank, "result": result}
        for rank, result in enumerate(lexical_results, start=1)
    }

    semantic_results = semantic_ticket_ranks(query, top_k=candidate_limit)
    semantic_by_id = {
        item["ticket_id"]: item
        for item in semantic_results
        if item["ticket_id"] != exclude_ticket_id
    }

    anchor_results = {
        item["ticket_id"]: item
        for item in _anchor_candidates(query, exclude_ticket_id)
    }
    ticket_ids = set(lexical_by_id) | set(semantic_by_id) | set(anchor_results)
    metadata_by_id = _ticket_metadata(ticket_ids)
    ranked = []
    for ticket_id in ticket_ids:
        lexical_rank = lexical_by_id.get(ticket_id, {}).get("rank")
        semantic_rank = semantic_by_id.get(ticket_id, {}).get("semantic_rank")
        lexical = lexical_by_id.get(ticket_id, {}).get("result", {})
        term_statistics = lexical.get("term_statistics", {})
        selected_anchors = lexical.get("selected_anchors", [])
        total_idf = sum(item.get("idf", 1.0) for item in term_statistics.values())
        anchor_idf = sum(
            term_statistics.get(term, {}).get("idf", 1.0)
            for term in selected_anchors
        )
        anchor_score = min(1.0, anchor_idf / total_idf) if total_idf else 0.0
        lexical_rrf = 1 / (RRF_K + lexical_rank) if lexical_rank else 0.0
        lexical_rrf *= 1.0 + (0.25 * anchor_score)
        semantic_rrf = 1 / (RRF_K + semantic_rank) if semantic_rank else 0.0
        ticket = metadata_by_id.get(ticket_id)
        if ticket is None:
            continue
        ticket["lexical_rank"] = lexical_rank
        ticket["semantic_rank"] = semantic_rank
        ticket["lexical_score"] = 2 * lexical_rrf
        ticket["semantic_score"] = 2 * semantic_rrf
        ticket["anchor_score"] = anchor_score
        anchor = anchor_results.get(ticket_id, {})
        ticket["anchor_tier"] = anchor.get("anchor_tier", 0)
        ticket["anchor_match_score"] = anchor.get("anchor_match_score", 0.0)
        ticket["rrf_score"] = lexical_rrf + semantic_rrf
        if lexical_rank:
            for key in (
                "bm25_rank", "retrieval_stage", "retrieval_query",
                "selected_anchors", "term_statistics",
            ):
                ticket[key] = lexical.get(key)
        ranked.append(ticket)

    ranked.sort(
        key=lambda ticket: (
            ticket["anchor_tier"],
            ticket["anchor_match_score"],
            ticket["rrf_score"],
        ),
        reverse=True,
    )
    selected = ranked[:limit]
    complete_by_id = _load_complete_tickets(
        [ticket["id"] for ticket in selected]
    )
    complete = []
    for ranked_ticket in selected:
        ticket = complete_by_id.get(ranked_ticket["id"])
        if ticket is None:
            continue
        ticket.update({
            key: ranked_ticket[key]
            for key in (
                "lexical_rank", "semantic_rank", "lexical_score",
                "semantic_score", "anchor_score", "anchor_tier",
                "anchor_match_score", "rrf_score", "bm25_rank",
                "retrieval_stage", "retrieval_query", "selected_anchors",
                "term_statistics",
            )
            if key in ranked_ticket
        })
        complete.append(ticket)
    return complete
