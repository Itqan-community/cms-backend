"""Capture public API requests and dispatch a Celery tracking task."""

from __future__ import annotations

import json
import logging
import re
import time
from urllib.parse import parse_qs
import uuid

from apps.usage_tracking.services.entity_extractor import extract_entities
from apps.usage_tracking.services.publisher_resolver import resolve_publisher_from_request
from apps.usage_tracking.tasks import track_api_request_task

logger = logging.getLogger(__name__)

EXCLUDED_PREFIXES = (
    "/portal",
    "/cms-api",
    "/tenant",
    "/accounts",
    "/django-admin",
    "/o",
    "/health",
    "/developers-api",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/favicon.ico",
    "/robots.txt",
    "/static",
    "/media",
)

EVENT_NAME = "public_api_request"

_PATH_CLASSIFIERS = [
    (re.compile(r"/recitations/(\d+)/?$"), "recitation"),
    (re.compile(r"/recitations/?$"), "recitation"),
    (re.compile(r"/reciters/(\d+)/?$"), "reciter"),
    (re.compile(r"/reciters/?$"), "reciter"),
    (re.compile(r"/riwayahs/(\d+)/?$"), "riwayah"),
    (re.compile(r"/riwayahs/?$"), "riwayah"),
]


def _classify_path(path: str) -> tuple[str | None, int | None]:
    for pattern, entity_type in _PATH_CLASSIFIERS:
        m = pattern.search(path)
        if m:
            accessed_id = int(m.group(1)) if m.lastindex else None
            return entity_type, accessed_id
    return None, None


def _resolve_application(request) -> tuple[int | None, str | None]:
    """Return (application_id, application_name) for OAuth2-authed requests."""
    token = getattr(request, "access_token", None)
    if token is None:
        return None, None
    application = getattr(token, "application", None)
    if application is None:
        return None, None
    return getattr(application, "id", None), getattr(application, "name", None)


def _detect_auth_method(request) -> str:
    """One of: 'oauth2', 'jwt', 'session', 'anonymous'."""
    if getattr(request, "access_token", None) is not None:
        return "oauth2"
    user = getattr(request, "user", None)
    if user is None or not getattr(user, "is_authenticated", False):
        return "anonymous"
    auth_header = request.headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
        return "jwt"
    return "session"


def _client_ip(request) -> str | None:
    """Resolve real client IP behind nginx/cloudflare. Used for Mixpanel $ip."""
    xff = request.headers.get("x-forwarded-for", "")
    if xff:
        # X-Forwarded-For: client, proxy1, proxy2 — first entry is the real client.
        return xff.split(",")[0].strip() or None
    return request.META.get("REMOTE_ADDR") or None


_KNOWN_FILTER_KEYS = ("reciter_id", "riwayah_id", "qiraah_id")


def _parse_query_params(query_string: str) -> dict:
    """Extract first-class properties from the query string.

    NOTE: query_string itself is also captured raw on the event. The public
    API filter schema does not accept any PII fields (see
    apps/content/api/public/*.py — only IDs, page, search, ordering). If a
    future endpoint adds a PII-bearing query param, sanitize here first.
    """
    if not query_string:
        return {}
    parsed = parse_qs(query_string, keep_blank_values=False)
    result: dict = {}

    page_raw = parsed.get("page", [None])[0]
    if page_raw:
        try:
            result["page"] = int(page_raw)
        except (TypeError, ValueError):
            pass

    search = parsed.get("search", [None])[0]
    if search:
        result["search"] = search

    for key in _KNOWN_FILTER_KEYS:
        value = parsed.get(key, [None])[0]
        if value:
            try:
                result[f"filter_{key}"] = int(value)
            except (TypeError, ValueError):
                result[f"filter_{key}"] = value

    ordering = parsed.get("ordering", [None])[0]
    if ordering:
        result["ordering"] = ordering

    return result


def _extract_error_code(response) -> str | None:
    """Pull the error_name from an ItqanError response body, if present."""
    if response.status_code < 400:
        return None
    if getattr(response, "streaming", False):
        return None
    body = getattr(response, "content", None)
    if not body:
        return None
    try:
        payload = json.loads(body)
    except (ValueError, TypeError):
        return None
    if isinstance(payload, dict):
        code = payload.get("error_name")
        if isinstance(code, str):
            return code
    return None


class UsageTrackingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if self._is_excluded(request.path):
            return self.get_response(request)

        start = time.monotonic()
        response = self.get_response(request)
        latency_ms = int((time.monotonic() - start) * 1000)

        try:
            self._dispatch(request, response, latency_ms)
        except Exception:
            logger.exception("usage_tracking middleware dispatch failed")

        return response

    @staticmethod
    def _is_excluded(path: str) -> bool:
        return any(path == p or path.startswith(p + "/") for p in EXCLUDED_PREFIXES)

    def _dispatch(self, request, response, latency_ms: int) -> None:
        publisher_id, publisher_slug, publisher_name = resolve_publisher_from_request(request)
        application_id, application_name = _resolve_application(request)
        distinct_id = self._distinct_id(request)
        entity_ids, entity_names = extract_entities(self._response_body(response))
        entity_type, accessed_entity_id = _classify_path(request.path)
        query_string = request.META.get("QUERY_STRING") or None
        parsed_qs = _parse_query_params(query_string or "")
        error_code = _extract_error_code(response)
        user_agent = request.headers.get("user-agent") or None
        ip = _client_ip(request)
        auth_method = _detect_auth_method(request)

        properties = {
            "method": request.method,
            "path": request.path,
            "endpoint": f"{request.method} {request.path}",
            "status_code": response.status_code,
            "latency_ms": latency_ms,
            "publisher_id": publisher_id,
            "publisher_slug": publisher_slug,
            "publisher_name": publisher_name,
            "application_id": application_id,
            "application_name": application_name,
            "auth_method": auth_method,
            "user_agent": user_agent,
            "entity_ids": entity_ids,
            "entity_names": entity_names,
            "entity_type": entity_type,
            "accessed_entity_id": accessed_entity_id,
            "query_string": query_string,
            "error_code": error_code,
            **parsed_qs,
        }
        if ip:
            # Mixpanel resolves geo from $ip on ingest and does not store the raw IP.
            properties["$ip"] = ip

        track_api_request_task.delay(
            distinct_id=distinct_id,
            event=EVENT_NAME,
            properties=properties,
        )

    @staticmethod
    def _response_body(response) -> bytes | None:
        if getattr(response, "streaming", False):
            return None
        return getattr(response, "content", None)

    @staticmethod
    def _distinct_id(request) -> str:
        # OAuth2 client_credentials: request.user is anonymous but the OAuth2
        # application is the stable identity for that downstream client.
        token = getattr(request, "access_token", None)
        if token is not None:
            application = getattr(token, "application", None)
            if application is not None:
                return f"app-{application.id}"

        user = getattr(request, "user", None)
        if user is not None and getattr(user, "is_authenticated", False):
            return f"user-{user.pk}"

        # True anonymous — every request gets a fresh ID. Acceptable; we have
        # no better signal. Most public-API traffic should hit one of the
        # branches above.
        return f"anon-{uuid.uuid4().hex[:12]}"
