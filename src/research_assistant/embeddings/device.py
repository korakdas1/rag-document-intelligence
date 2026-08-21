"""Device selection. Default is auto; tests should pass cpu or use HashingEmbeddingModel."""

from __future__ import annotations


def resolve_device(requested: str) -> str:
    choice = requested.strip().lower()
    if choice in {"cpu", "cuda"}:
        return choice
    if choice not in {"auto", ""}:
        raise ValueError(f"Unknown embedding device {requested!r}; use auto, cpu, or cuda")
    try:
        import torch

        if torch.cuda.is_available():
            return "cuda"
    except ImportError:
        pass
    return "cpu"
