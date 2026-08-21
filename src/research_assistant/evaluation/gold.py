"""Resolve filename+passage gold to chunk_ids for a specific chunker."""

from __future__ import annotations

from research_assistant.core.errors import EvaluationError
from research_assistant.evaluation.models import EvaluationExample, ResolvedGold
from research_assistant.storage.sqlite import SqliteDocumentStore


def resolve_gold(
    example: EvaluationExample,
    store: SqliteDocumentStore,
    chunker_id: str,
    *,
    require_match: bool = True,
) -> ResolvedGold:
    chunks = store.list_chunks_for_chunker(chunker_id)
    filename_by_document = {
        record.document_id: record.filename for record in store.list_documents()
    }
    if example.relevant_chunk_ids:
        known = set(example.relevant_chunk_ids)
        docs = {
            chunk.document_id
            for chunk in chunks
            if chunk.chunk_id in known
        }
        return ResolvedGold(
            example_id=example.example_id,
            chunk_ids=known,
            document_ids=docs,
        )

    wanted_files = set(example.relevant_filenames) | {
        passage.filename for passage in example.gold_passages
    }
    document_ids = {
        document_id
        for document_id, name in filename_by_document.items()
        if name in wanted_files
    }
    matched: set[str] = set()
    unmatched: list[str] = []
    for passage in example.gold_passages:
        needle = _normalize(passage.text)
        found = False
        for chunk in chunks:
            if filename_by_document.get(chunk.document_id) != passage.filename:
                continue
            if needle in _normalize(chunk.text):
                matched.add(chunk.chunk_id)
                found = True
        if not found:
            unmatched.append(f"{passage.filename}: {passage.text[:80]}")
    if require_match and example.answerable and unmatched:
        raise EvaluationError(
            f"{example.example_id}: gold passages matched no chunks for {chunker_id}: "
            + "; ".join(unmatched),
            code="gold_not_in_chunks",
        )
    if not matched and document_ids:
        # document-level fallback is recorded separately; chunk gold stays empty
        pass
    return ResolvedGold(
        example_id=example.example_id,
        chunk_ids=matched,
        document_ids=document_ids,
        unmatched_passages=tuple(unmatched),
    )


def contribution_label(
    gold_chunk_ids: set[str],
    dense_ids: list[str],
    lexical_ids: list[str],
) -> str | None:
    if not gold_chunk_ids:
        return None
    dense_hit = bool(gold_chunk_ids & set(dense_ids))
    lexical_hit = bool(gold_chunk_ids & set(lexical_ids))
    if dense_hit and lexical_hit:
        return "both"
    if dense_hit:
        return "dense_only"
    if lexical_hit:
        return "lexical_only"
    return "neither"


def _normalize(text: str) -> str:
    return " ".join(text.split())
