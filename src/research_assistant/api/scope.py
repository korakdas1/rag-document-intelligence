"""Canonical configured scope and fail-closed request scope resolution."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum

from research_assistant.api.errors import ApiError
from research_assistant.core.logging import get_logger
from research_assistant.indexing.health import DocumentIndexHealth

logger = get_logger("research_assistant.api.scope")


class ScopeMode(StrEnum):
    ALL = "all"
    SUBSET = "subset"
    NONE = "none"


@dataclass(frozen=True)
class DocumentScope:
    mode: ScopeMode
    document_ids: tuple[str, ...] = ()

    @classmethod
    def from_selection(cls, all_documents: bool, document_ids: Sequence[str]) -> "DocumentScope":
        if all_documents:
            return cls(ScopeMode.ALL)
        ids = tuple(dict.fromkeys(document_ids))
        return cls(ScopeMode.SUBSET if ids else ScopeMode.NONE, ids)

    @property
    def all_documents(self) -> bool:
        return self.mode is ScopeMode.ALL

    def validate_known(self, known_ids: set[str]) -> None:
        if set(self.document_ids) - known_ids:
            raise ApiError(
                code="not_found",
                message="One or more selected documents were not found. Update the selection.",
                status_code=404,
            )


def resolve_scope(
    scope: DocumentScope,
    health: Mapping[str, DocumentIndexHealth],
    *,
    session_id: str | None = None,
    legacy_document_ids: Sequence[str] | None = None,
) -> tuple[str, ...]:
    """Return a nonempty immutable filter, or stop before any RAG work.

    Legacy IDs on a session-backed ask are assertions, never scope overrides.
    An explicit empty list therefore mismatches any searchable saved scope.
    """
    selected = set(scope.document_ids)
    missing = selected - health.keys()
    checked = health.keys() if scope.mode is ScopeMode.ALL else selected & health.keys()
    unavailable = {doc_id for doc_id in checked if not health[doc_id].ready}
    effective: tuple[str, ...] = ()
    try:
        if scope.mode is ScopeMode.NONE:
            raise ApiError(
                code="no_documents_selected",
                message="Select at least one document before asking a question.",
                status_code=409,
            )
        if scope.mode is ScopeMode.SUBSET:
            if missing or unavailable:
                raise ApiError(
                    code="selected_documents_unavailable",
                    message=(
                        "Some selected documents are missing or not ready. "
                        "Update the selection or re-index them before asking."
                    ),
                    status_code=409,
                )
            effective = scope.document_ids
        else:
            effective = tuple(sorted(doc_id for doc_id, item in health.items() if item.ready))
        if not effective:
            raise ApiError(
                code="no_ready_documents",
                message="No searchable documents are available. Add or re-index a document first.",
                status_code=409,
            )
        if legacy_document_ids is not None and set(legacy_document_ids) != set(effective):
            raise ApiError(
                code="scope_mismatch",
                message=(
                    "The requested documents do not match the saved session scope. "
                    "Save the selection before asking."
                ),
                status_code=409,
            )
        return effective
    finally:
        logger.info(
            "scope_resolved session_id=%s mode=%s configured_count=%s "
            "effective_count=%s missing_count=%s unavailable_count=%s",
            session_id or "-",
            scope.mode.value,
            len(selected),
            len(effective),
            len(missing),
            len(unavailable),
        )
