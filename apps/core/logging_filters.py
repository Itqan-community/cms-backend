"""Logging filters that enrich records with per-request context."""

from __future__ import annotations

import logging

from apps.core.middlewares.client_version import client_context


class ClientContextFilter(logging.Filter):
    """Annotate every record with the calling application's name and version.

    Attached to the console handler so that *any* log line emitted while handling a
    request -- including tracebacks raised deep in the stack -- says which client
    build triggered it, without adding a per-request log line of its own.

    ``record.client`` is always set (empty string when unknown) so the formatter can
    interpolate it unconditionally.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        name, version = client_context.get()
        if name or version:
            record.client = f" client={name or 'unknown'}/{version or 'unknown'}"
        else:
            record.client = ""
        return True
