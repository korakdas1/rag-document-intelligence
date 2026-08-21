"""Chunk identity vs content hash.

chunk_id names a (document, chunker+config, source span, position, text) tuple.
content_hash fingerprints the chunk text alone and is not an identifier.
"""

from __future__ import annotations

import hashlib


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def chunk_id_for(
    *,
    document_id: str,
    chunker_id: str,
    source_block_start: int,
    source_block_end: int,
    position: int,
    content_hash: str,
) -> str:
    key = (
        f"{document_id}|{chunker_id}|{source_block_start}:{source_block_end}|"
        f"{position}|{content_hash}"
    )
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def approx_token_count(char_count: int) -> int:
    """Descriptive ~4 characters per token. Not a real tokenizer; not used for splits."""
    if char_count <= 0:
        return 0
    return (char_count + 3) // 4
