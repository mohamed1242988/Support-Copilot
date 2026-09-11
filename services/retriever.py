from storage.database import (
    get_ticket,
    search_local_tickets,
    search_local_jira,
    get_jira_comments,
    save_jira_comment
)

from integrations.jira import fetch_jira_comments
import transformers_utils.adapters as adapters
import knowledge.models.evidence as evidence
from knowledge.models.investigation_context import InvestigationContext
from knowledge.vector_store import VectorStore
from knowledge.embeddings import create_embedding


evidence_builder = evidence.EvidenceBuilder()


def assign_lexical_scores(results):
    """Normalize FTS5 BM25 scores within one source and one query."""

    if not results:
        return

    bm25_scores = [result["bm25_rank"] for result in results]

    best_score = min(bm25_scores)   # FTS5: more negative = better
    worst_score = max(bm25_scores)

    for index, result in enumerate(results, start=1):
        if best_score == worst_score:
            lexical_score = 1.0
        else:
            lexical_score = (
                worst_score - result["bm25_rank"]
            ) / (
                worst_score - best_score
            )

        result["lexical_score"] = lexical_score
        result["lexical_rank"] = index


def assign_semantic_scores(query: str, documents: list):
    """
    Computes semantic similarity scores for all candidate documents 
    using FAISS and updates their metadata.
    """
    if not documents:
        return

    # 1. Generate query embedding
    query_embedding = create_embedding(query, is_query=True)

    # 2. Initialize a temporary FAISS store (BGE-base dimension is 768)
    store = VectorStore(dimension=768)

    # 3. Embed each document's text representation
    doc_embeddings = []
    for doc in documents:
        # We embed the combination of Title and Content
        doc_text = f"{doc.title}\n{doc.content}"
        doc_embeddings.append(create_embedding(doc_text, is_query=False))

    # 4. Add embeddings to FAISS
    store.add(doc_embeddings, documents)

    # 5. Retrieve similarity scores for all candidates
    results = store.search(query_embedding, top_k=len(documents))

    # 6. Map the scores back to document metadata
    for res in results:
        doc = res["document"]
        doc.metadata["semantic_score"] = res["score"]

def ensure_jira_comments(issue):
    """
    Ensures Jira comments exist locally.
    """

    comments = get_jira_comments(
        issue["key"]
    )

    if comments:
        return comments

    comments = fetch_jira_comments(
        issue["key"]
    )

    for comment in comments:
        save_jira_comment(comment)

    return comments

def format_conversations(conversations):
    """
    Formats ticket conversations chronologically.
    """

    sorted_conversations = sorted(
        conversations,
        key=lambda x: x["created_at"]
    )

    formatted = []

    for conversation in sorted_conversations:

        if conversation["private"]:
            message_type = "Internal Note"
        else:
            message_type = "Public reply"

        formatted.append(
            f"""
[{message_type}]
Date:
{conversation["created_at"]}

Message:
{conversation["body_text"]}
"""
        )

    return "\n".join(formatted)


def build_context(ticket_id=None, issue_description=None):
    """
    Builds unified Freshdesk and Jira context.
    
    """

    if ticket_id:

        incoming_ticket = get_ticket(ticket_id)

        if not incoming_ticket:
            raise ValueError(
                f"Ticket {ticket_id} was not found in SQLite."
            )

        query = incoming_ticket["subject"]


        exclude_ticket_id = ticket_id

    else:

        incoming_ticket = {
            "id": "N/A",
            "subject": issue_description,
            "status": "N/A",
            "priority": "N/A",
            "description_text": issue_description,
            "conversations": []
        }

        query = issue_description

        exclude_ticket_id = None

    incoming_ticket["conversations"] = format_conversations(
        incoming_ticket.get("conversations", [])
    )

    freshdesk_results = search_local_tickets(
        query,
        limit=50,
        exclude_ticket_id=exclude_ticket_id
    )
    assign_lexical_scores(freshdesk_results)

    freshdesk_complete_results = []
    for result in freshdesk_results:
        ticket = get_ticket(result["id"])
        if ticket is not None:
            ticket["bm25_rank"] = result["bm25_rank"]
            ticket["lexical_rank"] = result["lexical_rank"]
            ticket["lexical_score"] = result["lexical_score"]
            ticket["retrieval_stage"] = result["retrieval_stage"]
            ticket["retrieval_query"] = result["retrieval_query"]
            ticket["selected_anchors"] = result["selected_anchors"]
            ticket["term_statistics"] = result["term_statistics"]
            freshdesk_complete_results.append(ticket)


    freshdesk_documents = [
    adapters.ticket_to_document(ticket)
    for ticket in freshdesk_complete_results
    ]

    assign_semantic_scores(query, freshdesk_documents)


    #
    # Search Jira
    #
    jira_results = search_local_jira(query)
    assign_lexical_scores(jira_results)
    for issue in jira_results:
        ensure_jira_comments(issue)

    jira_documents = [
    adapters.jira_to_document(issue)
    for issue in jira_results
    ]

    assign_semantic_scores(query, jira_documents)

    documents = (
    freshdesk_documents +
    jira_documents
    )

    freshdesk_ranked_evidence = evidence_builder.rank(
        query=query,
        documents=freshdesk_documents
    )
    freshdesk_evidence = freshdesk_ranked_evidence[:3]

    jira_ranked_evidence = evidence_builder.rank(
        query=query,
        documents=jira_documents
    )
    jira_evidence = jira_ranked_evidence[:3]

    evidence_list = freshdesk_evidence + jira_evidence

    print(f"Freshdesk candidates: {len(freshdesk_results)}")
    print(f"Jira candidates: {len(jira_results)}")
    print(f"Final evidence: {len(evidence_list)}")

    return InvestigationContext(
    query=query,
    incoming_ticket=incoming_ticket,

    freshdesk=freshdesk_results,
    jira=jira_results,

    freshdesk_documents=freshdesk_documents,
    jira_documents=jira_documents,

    documents=documents,
    freshdesk_ranked_evidence=freshdesk_ranked_evidence,
    jira_ranked_evidence=jira_ranked_evidence,
    evidence=evidence_list
)