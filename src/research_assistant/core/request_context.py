"""Per-request correlation. Never store secrets here."""

from __future__ import annotations

import re
from contextvars import ContextVar, Token

_REQUEST_ID: ContextVar[str] = ContextVar("request_id", default="")
_SAFE_ID = re.compile(r"^[A-Za-z0-9._-]{8,64}$")


def set_request_id(value: str) -> Token[str]:
    return _REQUEST_ID.set(value)


def reset_request_id(token: Token[str]) -> None:
    _REQUEST_ID.reset(token)


def get_request_id() -> str:
    return _REQUEST_ID.get() or ""


def sanitize_request_id(incoming: str | None) -> str | None:
    text = (incoming or "").strip()
    if _SAFE_ID.fullmatch(text):
        return text
    return None
