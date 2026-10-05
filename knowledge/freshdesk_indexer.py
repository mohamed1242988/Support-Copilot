"""Persistent Freshdesk chunking and embedding pipeline."""

from __future__ import annotations

import hashlib
import struct
from datetime import datetime, timezone

from knowledge.chunker import chunk_text
from knowledge.embeddings import MODEL_NAME, create_embeddings
from knowledge.sqlite_vector import (
    EMBEDDING_DIMENSION,
    initialize_vector_schema,
)
from storage.database import get_connection, get_ticket


def _serialize_embedding(values) -> bytes:
    values = [float(value) for value in values]
    if len(values) != EMBEDDING_DIMENSION:
        raise ValueError(
            f"Expected {EMBEDDING_DIMENSION}-dimensional embedding, got {len(values)}"
        )
    return struct.pack(f"{len(values)}f", *values)


def _ticket_records(ticket: dict) -> list[dict]:
    ticket_id = str(ticket["id"])
    fields = [
        f"Subject: {ticket.get('subject') or ''}",
        f"Description:\n{ticket.get('description_text') or ''}",
        f"Resolution:\n{ticket.get('resolution_summary') or ''}",
        f"Tags: {ticket.get('tags') or ''}",
    ]
    records = [{
        "source_id": f"ticket:{ticket_id}",
        "parent_type": "ticket",
        "parent_id": ticket_id,
        "text": "\n\n".join(fields),
    }]

    for conversation in ticket.get("conversations", []):
        visibility = "Internal note" if conversation.get("private") else "Public reply"
        records.append({
            "source_id": f"conversation:{conversation['id']}",
            "parent_type": "conversation",
            "parent_id": ticket_id,
            "text": (
                f"Ticket {ticket_id}\n{visibility}\n"
                f"Date: {conversation.get('created_at') or ''}\n\n"
                f"{conversation.get('body_text') or ''}"
            ),
        })
    return records


def index_freshdesk_ticket(ticket_id: int, batch_size: int = 64) -> int:
    """Replace all indexed chunks for one Freshdesk ticket."""
    ticket = get_ticket(ticket_id)
    if ticket is None:
        raise ValueError(f"Freshdesk ticket {ticket_id} was not found")

    records = []
    for record in _ticket_records(ticket):
        for index, text in enumerate(chunk_text(record["text"])):
            records.append({
                **record,
                "chunk_index": index,
                "content": text,
                "content_hash": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            })

    connection = get_connection()
    try:
        initialize_vector_schema(connection)
        now = datetime.now(timezone.utc).isoformat()
        existing = {
            (row[1], row[2]): {"id": row[0], "content_hash": row[3]}
            for row in connection.execute(
                """
                SELECT id, source_id, chunk_index, content_hash
                FROM document_chunks
                WHERE source = 'freshdesk' AND parent_id = ?
                """,
                (str(ticket_id),),
            )
        }
        desired_keys = {(item["source_id"], item["chunk_index"]) for item in records}
        desired_hashes = {
            (item["source_id"], item["chunk_index"]): item["content_hash"]
            for item in records
        }
        stale_ids = [
            value["id"]
            for key, value in existing.items()
            if key not in desired_keys
            or value["content_hash"] != desired_hashes[key]
        ]
        pending = []
        for item in records:
            key = (item["source_id"], item["chunk_index"])
            old_item = existing.get(key)
            if old_item is None or old_item["content_hash"] != item["content_hash"]:
                pending.append(item)
        embeddings = create_embeddings(
            [item["content"] for item in pending],
            batch_size=batch_size,
        )
        for item, embedding in zip(pending, embeddings):
            item["embedding"] = _serialize_embedding(embedding)

        if stale_ids:
            placeholders = ",".join("?" for _ in stale_ids)
            connection.execute(
                f"DELETE FROM document_chunk_vectors WHERE rowid IN ({placeholders})",
                stale_ids,
            )
            connection.execute(
                f"DELETE FROM document_chunks WHERE id IN ({placeholders})",
                stale_ids,
            )

        for item in pending:
            cursor = connection.execute(
                """
                INSERT INTO document_chunks (
                    source, source_id, parent_type, parent_id, chunk_index,
                    content, content_hash, embedding_model, embedding_dimension,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "freshdesk", item["source_id"], item["parent_type"],
                    item["parent_id"], item["chunk_index"], item["content"],
                    item["content_hash"], MODEL_NAME, EMBEDDING_DIMENSION, now, now,
                ),
            )
            connection.execute(
                "INSERT INTO document_chunk_vectors(rowid, embedding) VALUES (?, ?)",
                (cursor.lastrowid, item["embedding"]),
            )

        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
    return len(pending)


def reindex_all_freshdesk() -> int:
    """Backfill vectors for every locally stored Freshdesk ticket."""
    connection = get_connection()
    try:
        ticket_ids = [row[0] for row in connection.execute(
            "SELECT id FROM freshdesk_tickets ORDER BY id"
        )]
    finally:
        connection.close()
    return sum(index_freshdesk_ticket(ticket_id) for ticket_id in ticket_ids)


if __name__ == "__main__":
    print(f"Indexed {reindex_all_freshdesk()} Freshdesk chunks.")
