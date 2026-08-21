"""Map chunk_id (sha256 hex) to a Qdrant-compatible UUID point id."""

from __future__ import annotations

import uuid

_NAMESPACE = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")


def point_id_for(chunk_id: str) -> str:
    return str(uuid.uuid5(_NAMESPACE, chunk_id))
