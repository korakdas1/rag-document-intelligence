"""Stdlib logging helpers."""

from __future__ import annotations

import logging
import sys

from research_assistant.core.request_context import get_request_id

_CONFIGURED = False
_RECORD_FACTORY_INSTALLED = False

_FORMAT = "%(asctime)s %(levelname)s [%(name)s] request_id=%(request_id)s %(message)s"


def _install_record_factory() -> None:
    global _RECORD_FACTORY_INSTALLED
    if _RECORD_FACTORY_INSTALLED:
        return
    previous = logging.getLogRecordFactory()

    def factory(*args: object, **kwargs: object) -> logging.LogRecord:
        record = previous(*args, **kwargs)
        record.request_id = get_request_id() or "-"  # type: ignore[attr-defined]
        return record

    logging.setLogRecordFactory(factory)
    _RECORD_FACTORY_INSTALLED = True


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if not getattr(record, "request_id", None):
            record.request_id = get_request_id() or "-"
        return True


def configure_logging(level: str = "INFO") -> None:
    global _CONFIGURED
    numeric = getattr(logging, level.upper(), logging.INFO)
    _install_record_factory()
    if _CONFIGURED:
        logging.getLogger("research_assistant").setLevel(numeric)
        logging.getLogger().setLevel(numeric)
        return
    logging.basicConfig(
        level=numeric,
        format=_FORMAT,
        stream=sys.stderr,
    )
    handler_filter = RequestIdFilter()
    for handler in logging.getLogger().handlers:
        handler.addFilter(handler_filter)
    logging.getLogger("research_assistant").addFilter(handler_filter)
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
