"""Capture the calling application's name and version from request headers.

Consumers of the public developers API may identify their build by sending
``X-Client-Name`` and ``X-Client-Version``. Both are optional and purely
diagnostic: they let us (and them) tell which release of a client produced a
given error or usage pattern, so a regression can be traced to the version that
introduced it.

The values are attached to the request, published on a context variable for
logging (see :mod:`apps.core.logging_filters`), and tagged onto the Sentry
scope. ``apps.usage_tracking`` reads them off the request for Mixpanel.

Neither header can ever fail a request. A value that does not match the
expected shape is dropped and the response carries an ``X-Itqan-Warning``
telling the developer their header was ignored -- a debugging aid must not
break a working integration.
"""

from __future__ import annotations

from contextvars import ContextVar
import re

from django.http import HttpRequest, HttpResponse

try:
    import sentry_sdk
except ImportError:  # pragma: no cover - sentry_sdk is a declared dependency
    sentry_sdk = None

CLIENT_NAME_HEADER = "X-Client-Name"
CLIENT_VERSION_HEADER = "X-Client-Version"

# RFC 9111 deprecated the standard ``Warning`` header and intermediaries may strip it,
# so advisory notices ride on our own header instead.
WARNING_HEADER = "X-Itqan-Warning"

MAX_CLIENT_NAME_LENGTH = 64
MAX_CLIENT_VERSION_LENGTH = 32

# Deliberately narrow: these values become Sentry tags and Mixpanel properties, so the
# charset is restricted to keep cardinality and log/header injection under control.
CLIENT_NAME_PATTERN = re.compile(rf"\A[A-Za-z0-9._-]{{1,{MAX_CLIENT_NAME_LENGTH}}}\Z")
# ``+`` and ``-`` allow semver pre-release and build metadata, e.g. 2.4.1-beta.3+build.77.
CLIENT_VERSION_PATTERN = re.compile(rf"\A[A-Za-z0-9._+-]{{1,{MAX_CLIENT_VERSION_LENGTH}}}\Z")

_ALLOWED_NAME_CHARS = "A-Z a-z 0-9 . _ -"
_ALLOWED_VERSION_CHARS = "A-Z a-z 0-9 . _ + -"

# (name, version) of the client for the request being handled on this thread/task.
client_context: ContextVar[tuple[str | None, str | None]] = ContextVar("client_context", default=(None, None))


class ClientVersionMiddleware:
    """Read, validate and publish the client identity headers for one request."""

    def __init__(self, get_response) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        name, name_warning = _read_header(
            request, CLIENT_NAME_HEADER, CLIENT_NAME_PATTERN, MAX_CLIENT_NAME_LENGTH, _ALLOWED_NAME_CHARS
        )
        version, version_warning = _read_header(
            request, CLIENT_VERSION_HEADER, CLIENT_VERSION_PATTERN, MAX_CLIENT_VERSION_LENGTH, _ALLOWED_VERSION_CHARS
        )

        request.client_name = name
        request.client_version = version
        _tag_sentry(name, version)

        token = client_context.set((name, version))
        try:
            response = self.get_response(request)
        finally:
            client_context.reset(token)

        warnings = [warning for warning in (name_warning, version_warning) if warning]
        if warnings:
            response[WARNING_HEADER] = ", ".join(warnings)
        return response


def _read_header(
    request: HttpRequest, header: str, pattern: re.Pattern[str], max_length: int, allowed_chars: str
) -> tuple[str | None, str | None]:
    """Return the validated header value, plus a warning when it was rejected.

    A missing or blank header yields ``(None, None)``: not sending the header is
    the normal case and never warrants a warning.
    """
    raw = (request.headers.get(header) or "").strip()
    if not raw:
        return None, None
    if pattern.match(raw):
        return raw, None
    return None, f"ignored malformed {header} header; expected at most {max_length} characters of {allowed_chars}"


def _tag_sentry(name: str | None, version: str | None) -> None:
    """Tag the Sentry scope so errors can be filtered by the client that caused them."""
    if sentry_sdk is None:
        return
    if name:
        sentry_sdk.set_tag("client.name", name)
    if version:
        sentry_sdk.set_tag("client.version", version)
