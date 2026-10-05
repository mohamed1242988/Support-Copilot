"""Interactive smoke test for Freshdesk hybrid retrieval."""

from __future__ import annotations

import argparse
import sqlite3

from knowledge.vector_search import hybrid_search_freshdesk
from knowledge.search_statistics import classify_query_terms
from services.retriever import build_context


def print_search(query: str, limit: int) -> None:
    classifications = classify_query_terms(query)
    print(f"Query terms: {classifications}")
    connection = sqlite3.connect("storage/support_copilot.db")
    try:
        terms = tuple(classifications)
        placeholders = ",".join("?" for _ in terms)
        rows = connection.execute(
            f"""
            SELECT term, field, document_frequency, total_documents, idf
            FROM search_term_stats
            WHERE term IN ({placeholders})
            ORDER BY term, field
            """,
            terms,
        ).fetchall()
    finally:
        connection.close()
    print("Term statistics:")
    for term, field, frequency, total, idf in rows:
        print(f"  {term} [{field}]: {frequency}/{total} documents, IDF={idf:.3f}")
    results = hybrid_search_freshdesk(query, limit=limit)
    print(f"\nHybrid results: {len(results)}")
    for rank, ticket in enumerate(results, start=1):
        print(
            f"{rank}. Ticket {ticket['id']} | {ticket.get('subject') or '(no subject)'}\n"
            f"   RRF={ticket['rrf_score']:.6f} "
            f"lexical_rank={ticket.get('lexical_rank')} "
            f"semantic_rank={ticket.get('semantic_rank')} "
            f"anchor_tier={ticket.get('anchor_tier')} "
            f"anchor_score={ticket.get('anchor_match_score', 0):.2f}\n"
            f"   Customer={ticket.get('Customer_Name')} "
            f"Status={ticket.get('status')}"
        )


def print_context(query: str) -> None:
    context = build_context(issue_description=query)
    print(f"\nFreshdesk evidence: {len(context.freshdesk_ranked_evidence)}")
    for rank, evidence in enumerate(context.freshdesk_ranked_evidence, start=1):
        document = evidence.document
        print(
            f"{rank}. Ticket {document.id} | {document.title}\n"
            f"   final={evidence.score:.4f} "
            f"lexical={evidence.score_breakdown.get('lexical_score', 0):.6f} "
            f"semantic={evidence.score_breakdown.get('semantic_score', 0):.6f}"
        )

    print(f"Jira evidence: {len(context.jira_ranked_evidence)}")
    for rank, evidence in enumerate(context.jira_ranked_evidence, start=1):
        print(f"{rank}. {evidence.document.id} | {evidence.document.title}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("search", "context"), default="search")
    parser.add_argument("--query", help="Search text; prompts when omitted")
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()

    query = args.query or input("Search query: ").strip()
    if not query:
        raise SystemExit("A search query is required.")

    if args.mode == "search":
        print_search(query, args.limit)
    else:
        print_context(query)


if __name__ == "__main__":
    main()
