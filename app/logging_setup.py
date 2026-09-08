"""Structured logging setup with per-request correlation IDs.

A ``ContextVar`` carries the current request's ID so any log line emitted
anywhere in that request's call stack (DB, router, background task thread)
is automatically tagged with ``request_id``. ``setup_logging`` is called once
during app startup.
"""

import logging
from contextvars import ContextVar

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)


class RequestIdFilter(logging.Filter):
    """Adds ``request_id`` to every log record (''-' when unset)."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get() or "-"
        return True


def setup_logging(level: str) -> None:
    """Configures the root logger once; safe to call repeatedly."""
    root_logger = logging.getLogger()
    if root_logger.handlers:
        return

    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)-7s %(name)s [req=%(request_id)s] %(message)s"
        )
    )
    handler.addFilter(RequestIdFilter())

    root_logger.addHandler(handler)
    root_logger.setLevel(level.upper())