"""Capture public API requests and dispatch a Celery tracking task."""

from __future__ import annotations

import logging
import re
import time
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
    (re.compile(r"/reciters/?$"), "reciter"),
    (re.compile(r"/riwayahs/?$"), "riwayah"),
]


def _classify_path(path: str) -> tuple[str | None, int | None]:
    for pattern, entity_type in _PATH_CLASSIFIERS:
        m = pattern.search(path)
        if m:
            accessed_id = int(m.group(1)) if m.lastindex else None
            return entity_type, accessed_id
    return None, None


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
        distinct_id = self._distinct_id(request)
        entity_ids, entity_names = extract_entities(self._response_body(response))
        entity_type, accessed_entity_id = _classify_path(request.path)
        query_string = request.META.get("QUERY_STRING") or None

        properties = {
            "method": request.method,
            "path": request.path,
            "endpoint": f"{request.method} {request.path}",
            "status_code": response.status_code,
            "latency_ms": latency_ms,
            "publisher_id": publisher_id,
            "publisher_slug": publisher_slug,
            "publisher_name": publisher_name,
            "entity_ids": entity_ids,
            "entity_names": entity_names,
            "entity_type": entity_type,
            "accessed_entity_id": accessed_entity_id,
            "query_string": query_string,
        }

        track_api_request_task.delay(
            distinct_id=distinct_id,
            event=EVENT_NAME,
            properties=properties,
        )

    @staticmethod
    def _response_body(response) -> bytes | None:
        # Never touch .content on a streaming/file response — it would force
        # the full body into memory and break the stream.
        if getattr(response, "streaming", False):
            return None
        return getattr(response, "content", None)

    @staticmethod
    def _distinct_id(request) -> str:
        user = getattr(request, "user", None)
        if user is not None and getattr(user, "is_authenticated", False):
            return f"user-{user.pk}"
        return f"anon-{uuid.uuid4().hex[:12]}"
