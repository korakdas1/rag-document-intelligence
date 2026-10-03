"""SQLite document, chunk, vector-index registry, and research sessions. No vector columns."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Sequence
from pathlib import Path

from research_assistant.chunking.models import Chunk
from research_assistant.core.errors import DatabaseError
from research_assistant.core.types import ContentType, IndexStatus, ParseStatus
from research_assistant.storage.records import (
    DocumentIndexState,
    DocumentRecord,
    IndexMetadata,
    SessionRecord,
    SessionTurnRecord,
)

SCHEMA_VERSION = 5

_SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS documents (
    document_id TEXT PRIMARY KEY,
    source_path TEXT NOT NULL UNIQUE,
    filename TEXT NOT NULL,
    content_type TEXT NOT NULL,
    checksum_sha256 TEXT NOT NULL,
    byte_size INTEGER NOT NULL,
    ingested_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    parse_status TEXT NOT NULL,
    parser_id TEXT,
    warning_count INTEGER NOT NULL DEFAULT 0,
    page_count INTEGER,
    parsed_json TEXT,
    error_type TEXT,
    error_message TEXT
);

CREATE INDEX IF NOT EXISTS idx_documents_checksum
    ON documents (checksum_sha256);

CREATE TABLE IF NOT EXISTS chunks (
    chunk_id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    chunker_id TEXT NOT NULL,
    position INTEGER NOT NULL,
    text TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    char_count INTEGER NOT NULL,
    approx_token_count INTEGER NOT NULL,
    page_start INTEGER,
    page_end INTEGER,
    section_path TEXT NOT NULL,
    source_block_start INTEGER NOT NULL,
    source_block_end INTEGER NOT NULL,
    warnings TEXT NOT NULL,
    FOREIGN KEY (document_id) REFERENCES documents(document_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_chunks_document_chunker
    ON chunks (document_id, chunker_id, position);

CREATE UNIQUE INDEX IF NOT EXISTS idx_chunks_doc_chunker_pos
    ON chunks (document_id, chunker_id, position);

CREATE TABLE IF NOT EXISTS vector_indexes (
    index_id TEXT PRIMARY KEY,
    collection_name TEXT NOT NULL UNIQUE,
    embedding_model_id TEXT NOT NULL,
    chunker_id TEXT NOT NULL,
    dimension INTEGER NOT NULL,
    metric TEXT NOT NULL,
    normalized INTEGER NOT NULL,
    schema_version INTEGER NOT NULL,
    backend TEXT NOT NULL,
    status TEXT NOT NULL,
    chunk_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    error_message TEXT
);
"""

_SESSION_SCHEMA = """
CREATE TABLE IF NOT EXISTS research_sessions (
    session_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    all_documents INTEGER NOT NULL DEFAULT 1,
    selected_document_ids TEXT NOT NULL DEFAULT '[]'
);

CREATE INDEX IF NOT EXISTS idx_sessions_updated
    ON research_sessions (updated_at DESC);

CREATE TABLE IF NOT EXISTS conversation_turns (
    turn_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    sequence INTEGER NOT NULL,
    question TEXT NOT NULL,
    original_question TEXT,
    retrieval_query TEXT,
    generation_question TEXT,
    answer TEXT NOT NULL DEFAULT '',
    grounding_status TEXT NOT NULL,
    validation_status TEXT,
    insufficient_evidence INTEGER NOT NULL DEFAULT 0,
    error_message TEXT,
    sources_json TEXT NOT NULL DEFAULT '[]',
    citations_json TEXT NOT NULL DEFAULT '[]',
    diagnostics_json TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES research_sessions(session_id) ON DELETE CASCADE,
    UNIQUE (session_id, sequence)
);

CREATE INDEX IF NOT EXISTS idx_turns_session_sequence
    ON conversation_turns (session_id, sequence);
"""


_DOCUMENT_INDEX_SCHEMA = """
CREATE TABLE IF NOT EXISTS document_indexes (
    document_id TEXT NOT NULL REFERENCES documents(document_id) ON DELETE CASCADE,
    index_id TEXT NOT NULL,
    chunker_id TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('unverified', 'building', 'ready', 'failed')),
    attempt_id TEXT NOT NULL,
    source_checksum TEXT NOT NULL,
    chunk_ids TEXT NOT NULL,
    PRIMARY KEY (document_id, index_id)
)
"""


class SqliteDocumentStore:
    def __init__(self, database_path: Path, *, busy_timeout_ms: int = 5000) -> None:
        self._path = database_path
        self._busy_timeout_ms = busy_timeout_ms
        self._path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self._init_schema()
        except sqlite3.DatabaseError as exc:
            raise DatabaseError(
                "SQLite database cannot be opened. The existing file was not modified.",
                code="database_corrupt",
            ) from exc

    def _connect(self) -> sqlite3.Connection:
        timeout_s = max(self._busy_timeout_ms, 0) / 1000.0
        conn = sqlite3.connect(self._path, timeout=timeout_s)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute(f"PRAGMA busy_timeout = {int(self._busy_timeout_ms)}")
        try:
            conn.execute("PRAGMA journal_mode = WAL")
        except sqlite3.Error:
            pass
        return conn

    def ping(self) -> None:
        with self._connect() as conn:
            conn.execute("SELECT 1")

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(_SCHEMA)
            conn.executescript(_SESSION_SCHEMA)
            row = conn.execute("SELECT version FROM schema_version").fetchone()
            if row is not None and int(row["version"]) > SCHEMA_VERSION:
                raise RuntimeError(
                    f"Unsupported schema version {row['version']}; expected {SCHEMA_VERSION}"
                )
            # The additive migration and version advance commit together. Legacy
            # rows are candidates only: live vector identities must still match.
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(_DOCUMENT_INDEX_SCHEMA)
            if row is not None and int(row["version"]) < 5:
                self._migrate_document_indexes(conn)
            if row is None:
                conn.execute(
                    "INSERT INTO schema_version (version) VALUES (?)",
                    (SCHEMA_VERSION,),
                )
            elif int(row["version"]) < SCHEMA_VERSION:
                conn.execute("DELETE FROM schema_version")
                conn.execute(
                    "INSERT INTO schema_version (version) VALUES (?)",
                    (SCHEMA_VERSION,),
                )
            conn.commit()

    @staticmethod
    def _migrate_document_indexes(conn: sqlite3.Connection) -> None:
        indexes = conn.execute("SELECT * FROM vector_indexes").fetchall()
        for index in indexes:
            rows = conn.execute(
                """SELECT c.document_id, c.chunk_id, d.checksum_sha256
                   FROM chunks c JOIN documents d USING (document_id)
                   WHERE c.chunker_id = ? AND trim(c.text) != ''""",
                (index["chunker_id"],),
            ).fetchall()
            grouped: dict[str, list[str]] = {}
            checksums: dict[str, str] = {}
            for item in rows:
                grouped.setdefault(item["document_id"], []).append(item["chunk_id"])
                checksums[item["document_id"]] = item["checksum_sha256"]
            for document_id, chunk_ids in grouped.items():
                conn.execute(
                    """INSERT OR IGNORE INTO document_indexes
                       VALUES (?, ?, ?, ?, '', ?, ?)""",
                    (document_id, index["index_id"], index["chunker_id"],
                     "unverified" if index["status"] == "ready" else "failed",
                     checksums[document_id], json.dumps(sorted(chunk_ids))),
                )

    def list_document_indexes(
        self, index_id: str, *, document_id: str | None = None
    ) -> dict[str, DocumentIndexState]:
        sql = "SELECT * FROM document_indexes WHERE index_id = ?"
        params = (index_id,)
        if document_id is not None:
            sql += " AND document_id = ?"
            params = (index_id, document_id)
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return {
            row["document_id"]: DocumentIndexState(
                document_id=row["document_id"],
                index_id=row["index_id"],
                chunker_id=row["chunker_id"],
                status=row["status"],
                attempt_id=row["attempt_id"],
                source_checksum=row["source_checksum"],
                chunk_ids=frozenset(json.loads(row["chunk_ids"])),
            )
            for row in rows
        }

    def begin_document_indexes(self, states: Sequence[DocumentIndexState]) -> None:
        with self._connect() as conn:
            conn.executemany(
                """INSERT INTO document_indexes VALUES (?, ?, ?, 'building', ?, ?, ?)
                   ON CONFLICT(document_id, index_id) DO UPDATE SET
                     chunker_id = excluded.chunker_id, status = 'building',
                     attempt_id = excluded.attempt_id,
                     source_checksum = excluded.source_checksum, chunk_ids = excluded.chunk_ids""",
                [(s.document_id, s.index_id, s.chunker_id, s.attempt_id,
                  s.source_checksum, json.dumps(sorted(s.chunk_ids))) for s in states],
            )

    def finish_document_indexes(self, index_id: str, attempt_id: str, *, succeeded: bool) -> None:
        with self._connect() as conn:
            conn.execute(
                """UPDATE document_indexes SET status = ?
                   WHERE index_id = ? AND attempt_id = ?""",
                ("ready" if succeeded else "failed", index_id, attempt_id),
            )

    def schema_version(self) -> int:
        with self._connect() as conn:
            row = conn.execute("SELECT version FROM schema_version").fetchone()
        return int(row["version"]) if row else 0

    def get_by_id(self, document_id: str) -> DocumentRecord | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM documents WHERE document_id = ?",
                (document_id,),
            ).fetchone()
        return _row_to_record(row) if row else None

    def get_by_source_path(self, source_path: str) -> DocumentRecord | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM documents WHERE source_path = ?",
                (source_path,),
            ).fetchone()
        return _row_to_record(row) if row else None

    def upsert(self, record: DocumentRecord) -> None:
        values = (
            record.document_id,
            record.source_path,
            record.filename,
            record.content_type.value,
            record.checksum_sha256,
            record.byte_size,
            record.ingested_at,
            record.updated_at,
            record.parse_status.value,
            record.parser_id,
            record.warning_count,
            record.page_count,
            record.parsed_json,
            record.error_type,
            record.error_message,
        )
        sql = """
            INSERT INTO documents (
                document_id, source_path, filename, content_type,
                checksum_sha256, byte_size, ingested_at, updated_at,
                parse_status, parser_id, warning_count, page_count,
                parsed_json, error_type, error_message
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(document_id) DO UPDATE SET
                source_path = excluded.source_path,
                filename = excluded.filename,
                content_type = excluded.content_type,
                checksum_sha256 = excluded.checksum_sha256,
                byte_size = excluded.byte_size,
                ingested_at = excluded.ingested_at,
                updated_at = excluded.updated_at,
                parse_status = excluded.parse_status,
                parser_id = excluded.parser_id,
                warning_count = excluded.warning_count,
                page_count = excluded.page_count,
                parsed_json = excluded.parsed_json,
                error_type = excluded.error_type,
                error_message = excluded.error_message
            """
        with self._connect() as conn:
            existing = conn.execute(
                "SELECT checksum_sha256 FROM documents WHERE document_id = ?",
                (record.document_id,),
            ).fetchone()
            conn.execute(sql, values)
            if existing is not None and existing["checksum_sha256"] != record.checksum_sha256:
                conn.execute(
                    "UPDATE document_indexes SET status = 'failed' WHERE document_id = ?",
                    (record.document_id,),
                )
                conn.execute(
                    "DELETE FROM chunks WHERE document_id = ?",
                    (record.document_id,),
                )
            conn.commit()

    def replace_chunks(
        self, document_id: str, chunker_id: str, chunks: Sequence[Chunk]
    ) -> None:
        with self._connect() as conn:
            old_ids = {row[0] for row in conn.execute(
                "SELECT chunk_id FROM chunks WHERE document_id = ? AND chunker_id = ?",
                (document_id, chunker_id),
            )}
            if old_ids != {chunk.chunk_id for chunk in chunks}:
                conn.execute(
                    """UPDATE document_indexes SET status = 'failed'
                       WHERE document_id = ? AND chunker_id = ?""",
                    (document_id, chunker_id),
                )
            conn.execute(
                "DELETE FROM chunks WHERE document_id = ? AND chunker_id = ?",
                (document_id, chunker_id),
            )
            conn.executemany(
                """
                INSERT INTO chunks (
                    chunk_id, document_id, chunker_id, position, text,
                    content_hash, char_count, approx_token_count,
                    page_start, page_end, section_path,
                    source_block_start, source_block_end, warnings
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [_chunk_row(chunk) for chunk in chunks],
            )
            conn.commit()

    def list_chunks(
        self, document_id: str, chunker_id: str | None = None
    ) -> list[Chunk]:
        if chunker_id is None:
            sql = """
                SELECT * FROM chunks
                WHERE document_id = ?
                ORDER BY chunker_id, position
                """
            params: tuple[str, ...] = (document_id,)
        else:
            sql = """
                SELECT * FROM chunks
                WHERE document_id = ? AND chunker_id = ?
                ORDER BY position
                """
            params = (document_id, chunker_id)
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [_row_to_chunk(row) for row in rows]

    def count_chunks(
        self, document_id: str, chunker_id: str | None = None
    ) -> int:
        if chunker_id is None:
            sql = "SELECT COUNT(*) AS n FROM chunks WHERE document_id = ?"
            params: tuple[str, ...] = (document_id,)
        else:
            sql = (
                "SELECT COUNT(*) AS n FROM chunks "
                "WHERE document_id = ? AND chunker_id = ?"
            )
            params = (document_id, chunker_id)
        with self._connect() as conn:
            row = conn.execute(sql, params).fetchone()
        return int(row["n"]) if row else 0

    def list_chunks_for_chunker(self, chunker_id: str) -> list[Chunk]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM chunks
                WHERE chunker_id = ?
                ORDER BY document_id, position
                """,
                (chunker_id,),
            ).fetchall()
        return [_row_to_chunk(row) for row in rows]

    def get_chunk(self, chunk_id: str) -> Chunk | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM chunks WHERE chunk_id = ?",
                (chunk_id,),
            ).fetchone()
        return _row_to_chunk(row) if row else None

    def delete_chunks_for_document(
        self, document_id: str, chunker_id: str | None = None
    ) -> None:
        with self._connect() as conn:
            if chunker_id is None:
                conn.execute(
                    "DELETE FROM chunks WHERE document_id = ?",
                    (document_id,),
                )
            else:
                conn.execute(
                    "DELETE FROM chunks WHERE document_id = ? AND chunker_id = ?",
                    (document_id, chunker_id),
                )
            conn.commit()

    def delete_document(self, document_id: str) -> bool:
        """Remove the document row. Chunks follow via ON DELETE CASCADE.

        Does not touch the filesystem or vector store.
        """
        with self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM documents WHERE document_id = ?",
                (document_id,),
            )
            conn.commit()
            return cursor.rowcount > 0

    def list_documents(self) -> list[DocumentRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM documents ORDER BY updated_at DESC, filename, document_id"
            ).fetchall()
        return [_row_to_record(row) for row in rows]

    def get_vector_index(self, index_id: str) -> IndexMetadata | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM vector_indexes WHERE index_id = ?",
                (index_id,),
            ).fetchone()
        return _row_to_index(row) if row else None

    def list_vector_indexes(self) -> list[IndexMetadata]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM vector_indexes ORDER BY updated_at"
            ).fetchall()
        return [_row_to_index(row) for row in rows]

    def upsert_vector_index(self, meta: IndexMetadata) -> None:
        sql = """
            INSERT INTO vector_indexes (
                index_id, collection_name, embedding_model_id, chunker_id,
                dimension, metric, normalized, schema_version, backend,
                status, chunk_count, created_at, updated_at, error_message
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(index_id) DO UPDATE SET
                collection_name = excluded.collection_name,
                embedding_model_id = excluded.embedding_model_id,
                chunker_id = excluded.chunker_id,
                dimension = excluded.dimension,
                metric = excluded.metric,
                normalized = excluded.normalized,
                schema_version = excluded.schema_version,
                backend = excluded.backend,
                status = excluded.status,
                chunk_count = excluded.chunk_count,
                updated_at = excluded.updated_at,
                error_message = excluded.error_message
            """
        values = (
            meta.index_id,
            meta.collection_name,
            meta.embedding_model_id,
            meta.chunker_id,
            meta.dimension,
            meta.metric,
            1 if meta.normalized else 0,
            meta.schema_version,
            meta.backend,
            meta.status.value,
            meta.chunk_count,
            meta.created_at,
            meta.updated_at,
            meta.error_message,
        )
        with self._connect() as conn:
            conn.execute(sql, values)
            conn.commit()

    def update_vector_index_count(self, index_id: str, chunk_count: int) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE vector_indexes
                SET chunk_count = ?, updated_at = datetime('now')
                WHERE index_id = ?
                """,
                (chunk_count, index_id),
            )
            conn.commit()

    def mark_vector_index_failed(self, index_id: str, error_message: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE vector_indexes
                SET status = ?, error_message = ?, updated_at = datetime('now')
                WHERE index_id = ?
                """,
                (IndexStatus.FAILED.value, error_message[:2000], index_id),
            )
            conn.commit()

    def create_session(
        self,
        session_id: str,
        *,
        title: str,
        created_at: str,
        all_documents: bool = True,
        selected_document_ids: Sequence[str] = (),
    ) -> SessionRecord:
        ids = json.dumps(list(selected_document_ids), ensure_ascii=False)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO research_sessions (
                    session_id, title, created_at, updated_at,
                    all_documents, selected_document_ids
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    title,
                    created_at,
                    created_at,
                    1 if all_documents else 0,
                    ids,
                ),
            )
            conn.commit()
        record = self.get_session(session_id)
        assert record is not None
        return record

    def get_session(self, session_id: str) -> SessionRecord | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT s.*, COUNT(t.turn_id) AS turn_count
                FROM research_sessions s
                LEFT JOIN conversation_turns t ON t.session_id = s.session_id
                WHERE s.session_id = ?
                GROUP BY s.session_id
                """,
                (session_id,),
            ).fetchone()
        return _row_to_session(row) if row else None

    def list_sessions(self) -> list[SessionRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT s.*, COUNT(t.turn_id) AS turn_count
                FROM research_sessions s
                LEFT JOIN conversation_turns t ON t.session_id = s.session_id
                GROUP BY s.session_id
                ORDER BY s.updated_at DESC, s.session_id
                """
            ).fetchall()
        return [_row_to_session(row) for row in rows]

    def update_session(
        self,
        session_id: str,
        *,
        title: str | None = None,
        all_documents: bool | None = None,
        selected_document_ids: Sequence[str] | None = None,
        updated_at: str,
    ) -> SessionRecord | None:
        current = self.get_session(session_id)
        if current is None:
            return None
        next_title = current.title if title is None else title
        next_all = current.all_documents if all_documents is None else all_documents
        next_ids = (
            current.selected_document_ids
            if selected_document_ids is None
            else tuple(selected_document_ids)
        )
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE research_sessions
                SET title = ?, all_documents = ?, selected_document_ids = ?,
                    updated_at = ?
                WHERE session_id = ?
                """,
                (
                    next_title,
                    1 if next_all else 0,
                    json.dumps(list(next_ids), ensure_ascii=False),
                    updated_at,
                    session_id,
                ),
            )
            conn.commit()
        return self.get_session(session_id)

    def delete_session(self, session_id: str) -> bool:
        with self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM research_sessions WHERE session_id = ?",
                (session_id,),
            )
            conn.commit()
            return cursor.rowcount > 0

    def list_turns(self, session_id: str) -> list[SessionTurnRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM conversation_turns
                WHERE session_id = ?
                ORDER BY sequence ASC, turn_id ASC
                """,
                (session_id,),
            ).fetchall()
        return [_row_to_turn(row) for row in rows]

    def get_turn(self, turn_id: str) -> SessionTurnRecord | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM conversation_turns WHERE turn_id = ?",
                (turn_id,),
            ).fetchone()
        return _row_to_turn(row) if row else None

    def next_turn_sequence(self, session_id: str) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COALESCE(MAX(sequence), 0) AS max_seq FROM conversation_turns WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        return int(row["max_seq"]) + 1 if row else 1

    def upsert_turn(self, record: SessionTurnRecord, *, session_updated_at: str) -> None:
        """Insert or replace a turn and bump the parent session timestamp. One transaction."""
        fields = (
            record.question,
            record.original_question,
            record.retrieval_query,
            record.generation_question,
            record.answer,
            record.grounding_status,
            record.validation_status,
            1 if record.insufficient_evidence else 0,
            record.error_message,
            record.sources_json,
            record.citations_json,
            record.diagnostics_json,
        )
        with self._connect() as conn:
            found = conn.execute(
                """
                SELECT 1 FROM conversation_turns
                WHERE turn_id = ? AND session_id = ?
                """,
                (record.turn_id, record.session_id),
            ).fetchone()
            if found:
                conn.execute(
                    """
                    UPDATE conversation_turns SET
                        question = ?,
                        original_question = ?,
                        retrieval_query = ?,
                        generation_question = ?,
                        answer = ?,
                        grounding_status = ?,
                        validation_status = ?,
                        insufficient_evidence = ?,
                        error_message = ?,
                        sources_json = ?,
                        citations_json = ?,
                        diagnostics_json = ?
                    WHERE turn_id = ? AND session_id = ?
                    """,
                    (*fields, record.turn_id, record.session_id),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO conversation_turns (
                        turn_id, session_id, sequence, question, original_question,
                        retrieval_query, generation_question, answer, grounding_status,
                        validation_status, insufficient_evidence, error_message,
                        sources_json, citations_json, diagnostics_json, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record.turn_id,
                        record.session_id,
                        record.sequence,
                        *fields,
                        record.created_at,
                    ),
                )
            conn.execute(
                "UPDATE research_sessions SET updated_at = ? WHERE session_id = ?",
                (session_updated_at, record.session_id),
            )
            conn.commit()

    def close(self) -> None:
        """Flush WAL so a process restart reads the latest committed turns."""
        try:
            with self._connect() as conn:
                conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        except sqlite3.Error:
            pass

    def count_documents(self) -> int:
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) AS n FROM documents").fetchone()
        return int(row["n"]) if row else 0


def _row_to_record(row: sqlite3.Row) -> DocumentRecord:
    return DocumentRecord(
        document_id=row["document_id"],
        source_path=row["source_path"],
        filename=row["filename"],
        content_type=ContentType(row["content_type"]),
        checksum_sha256=row["checksum_sha256"],
        byte_size=int(row["byte_size"]),
        ingested_at=row["ingested_at"],
        updated_at=row["updated_at"],
        parse_status=ParseStatus(row["parse_status"]),
        parser_id=row["parser_id"],
        warning_count=int(row["warning_count"]),
        page_count=row["page_count"],
        parsed_json=row["parsed_json"],
        error_type=row["error_type"],
        error_message=row["error_message"],
    )


def _chunk_row(chunk: Chunk) -> tuple[object, ...]:
    return (
        chunk.chunk_id,
        chunk.document_id,
        chunk.chunker_id,
        chunk.position,
        chunk.text,
        chunk.content_hash,
        chunk.char_count,
        chunk.approx_token_count,
        chunk.page_start,
        chunk.page_end,
        json.dumps(list(chunk.section_path), ensure_ascii=False),
        chunk.source_block_start,
        chunk.source_block_end,
        json.dumps(list(chunk.warnings), ensure_ascii=False),
    )


def _row_to_chunk(row: sqlite3.Row) -> Chunk:
    return Chunk(
        chunk_id=row["chunk_id"],
        document_id=row["document_id"],
        chunker_id=row["chunker_id"],
        position=int(row["position"]),
        text=row["text"],
        content_hash=row["content_hash"],
        char_count=int(row["char_count"]),
        approx_token_count=int(row["approx_token_count"]),
        source_block_start=int(row["source_block_start"]),
        source_block_end=int(row["source_block_end"]),
        page_start=row["page_start"],
        page_end=row["page_end"],
        section_path=tuple(json.loads(row["section_path"])),
        warnings=tuple(json.loads(row["warnings"])),
    )


def _row_to_index(row: sqlite3.Row) -> IndexMetadata:
    return IndexMetadata(
        index_id=row["index_id"],
        collection_name=row["collection_name"],
        embedding_model_id=row["embedding_model_id"],
        chunker_id=row["chunker_id"],
        dimension=int(row["dimension"]),
        metric=row["metric"],
        normalized=bool(row["normalized"]),
        schema_version=int(row["schema_version"]),
        backend=row["backend"],
        status=IndexStatus(row["status"]),
        chunk_count=int(row["chunk_count"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        error_message=row["error_message"],
    )


def _row_to_session(row: sqlite3.Row) -> SessionRecord:
    raw_ids = json.loads(row["selected_document_ids"] or "[]")
    keys = row.keys()
    turn_count = int(row["turn_count"]) if "turn_count" in keys else 0
    return SessionRecord(
        session_id=row["session_id"],
        title=row["title"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        all_documents=bool(row["all_documents"]),
        selected_document_ids=tuple(str(item) for item in raw_ids),
        turn_count=turn_count,
    )


def _row_to_turn(row: sqlite3.Row) -> SessionTurnRecord:
    return SessionTurnRecord(
        turn_id=row["turn_id"],
        session_id=row["session_id"],
        sequence=int(row["sequence"]),
        question=row["question"],
        original_question=row["original_question"],
        retrieval_query=row["retrieval_query"],
        generation_question=row["generation_question"],
        answer=row["answer"] or "",
        grounding_status=row["grounding_status"],
        validation_status=row["validation_status"],
        insufficient_evidence=bool(row["insufficient_evidence"]),
        error_message=row["error_message"],
        sources_json=row["sources_json"] or "[]",
        citations_json=row["citations_json"] or "[]",
        diagnostics_json=row["diagnostics_json"],
        created_at=row["created_at"],
    )


def _row_to_session(row: sqlite3.Row) -> SessionRecord:
    raw_ids = json.loads(row["selected_document_ids"] or "[]")
    keys = row.keys()
    turn_count = int(row["turn_count"]) if "turn_count" in keys else 0
    return SessionRecord(
        session_id=row["session_id"],
        title=row["title"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        all_documents=bool(row["all_documents"]),
        selected_document_ids=tuple(str(item) for item in raw_ids),
        turn_count=turn_count,
    )


def _row_to_turn(row: sqlite3.Row) -> SessionTurnRecord:
    return SessionTurnRecord(
        turn_id=row["turn_id"],
        session_id=row["session_id"],
        sequence=int(row["sequence"]),
        question=row["question"],
        original_question=row["original_question"],
        retrieval_query=row["retrieval_query"],
        generation_question=row["generation_question"],
        answer=row["answer"] or "",
        grounding_status=row["grounding_status"],
        validation_status=row["validation_status"],
        insufficient_evidence=bool(row["insufficient_evidence"]),
        error_message=row["error_message"],
        sources_json=row["sources_json"] or "[]",
        citations_json=row["citations_json"] or "[]",
        diagnostics_json=row["diagnostics_json"],
        created_at=row["created_at"],
    )
