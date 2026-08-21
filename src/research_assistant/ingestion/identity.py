"""Document identity derived from canonical filesystem path.

Logical identity (document_id) is independent of content checksum.
"""

from __future__ import annotations

import hashlib
from pathlib import Path


def canonical_path(path: Path) -> Path:
    return path.expanduser().resolve(strict=True)


def document_id_for_path(path: Path) -> str:
    canonical = path.expanduser().resolve()
    key = f"local-file:{canonical.as_posix()}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()
