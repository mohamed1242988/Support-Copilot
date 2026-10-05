"""SQLite-backed persistent storage for semantic-search chunks."""

from __future__ import annotations

import sqlite3


EMBEDDING_DIMENSION = 768


def load_sqlite_vec(connection: sqlite3.Connection) -> None:
    """Load the sqlite-vec extension into one SQLite connection."""
    try:
        import sqlite_vec
    except ImportError as exc:
        raise RuntimeError(
            "sqlite-vec is required for persistent vector search. "
            "Install the project dependencies before initializing the database."
        ) from exc

    connection.enable_load_extension(True)
    try:
        sqlite_vec.load(connection)
    finally:
        connection.enable_load_extension(False)


def initialize_vector_schema(connection: sqlite3.Connection) -> None:
    """Create chunk metadata and the persistent sqlite-vec index."""
    load_sqlite_vec(connection)

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS document_chunks (
            id INTEGER PRIMARY KEY,
            source TEXT NOT NULL,
            source_id TEXT NOT NULL,
            parent_type TEXT NOT NULL,
            parent_id TEXT NOT NULL,
            chunk_index INTEGER NOT NULL,
            content TEXT NOT NULL,
            content_hash TEXT NOT NULL,
            embedding_model TEXT NOT NULL,
            embedding_dimension INTEGER NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(source, source_id, chunk_index, content_hash)
        )
        """
    )
    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_document_chunks_parent
        ON document_chunks(source, parent_type, parent_id)
        """
    )
    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_document_chunks_source
        ON document_chunks(source, source_id)
        """
    )

    # sqlite-vec uses the virtual-table rowid as the stable link to metadata.
    connection.execute(
        f"""
        CREATE VIRTUAL TABLE IF NOT EXISTS document_chunk_vectors
        USING vec0(embedding float[{EMBEDDING_DIMENSION}])
        """
    )


def initialize_vector_database(database_path) -> None:
    """Initialize only the vector portion of an existing SQLite database."""
    connection = sqlite3.connect(database_path)
    try:
        initialize_vector_schema(connection)
        connection.commit()
    finally:
        connection.close()
