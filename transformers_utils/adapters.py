from knowledge.models.document import Document


def ticket_to_document(ticket: dict) -> Document:
    """
    Convert a complete Freshdesk ticket dictionary into a normalized Document.
    """

    content_parts = []

    if ticket.get("description_text"):
        content_parts.append(
            f"Description:\n{ticket['description_text']}"
        )

    conversations = ticket.get("conversations", [])

    if conversations:
        conversation_text = []

        for conversation in conversations:

            if conversation.get("private"):
                message_type = "Internal Note"
            else:
                message_type = "Public reply"

            conversation_text.append(
                f"""
[{message_type}]
Date:
{conversation.get('created_at')}

Message:
{conversation.get('body_text')}
"""
            )

        content_parts.append(
            "Conversation History:\n"
            + "\n".join(conversation_text)
        )

    metadata = {
        "status": ticket.get("status"),
        "priority": ticket.get("priority"),
        "customer": ticket.get("customer"),
        "product": ticket.get("product"),
        "tags": ticket.get("tags"),
        "created_at": ticket.get("created_at"),
        "updated_at": ticket.get("updated_at"),
        "url": ticket.get("url"),
        "primary_content": ticket.get("description_text", ""),
        "lexical_score": ticket.get("lexical_score", 0.0),
        "bm25_rank": ticket.get("bm25_rank"),
        "lexical_rank": ticket.get("lexical_rank"),
        "retrieval_stage": ticket.get("retrieval_stage"),
        "retrieval_query": ticket.get("retrieval_query"),
        "selected_anchors": ticket.get("selected_anchors", []),
        "term_statistics": ticket.get("term_statistics", {}),
    }

    return Document(
        id=str(ticket.get("id")),
        source="freshdesk",
        title=ticket.get("subject", ""),
        content="\n\n".join(content_parts),
        metadata=metadata,
    )

def jira_to_document(issue: dict) -> Document:
    """
    Convert a Jira issue dictionary into a normalized Document.
    """

    content_parts = []

    if issue.get("description"):
        content_parts.append(
            f"Description:\n{issue['description']}"
        )

    comments = issue.get("comments", [])

    if comments:
        content_parts.append(
            "Comments:\n" + "\n\n".join(comments)
        )

    metadata = {
        "status": issue.get("status"),
        "resolution": issue.get("resolution"),
        "primary_content": issue.get("description", ""),
        "lexical_score": issue.get("lexical_score", 0.0),
        "bm25_rank": issue.get("bm25_rank"),
        "lexical_rank": issue.get("lexical_rank"),
        "retrieval_stage": issue.get("retrieval_stage"),
        "retrieval_query": issue.get("retrieval_query"),
        "selected_anchors": issue.get("selected_anchors", []),
        "term_statistics": issue.get("term_statistics", {}),
    }

    return Document(
        id=issue.get("key", ""),
        source="jira",
        title=issue.get("summary", ""),
        content="\n\n".join(content_parts),
        metadata=metadata,
    )
