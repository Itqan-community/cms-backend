"""Capture public API requests and dispatch a Celery tracking task."""

from __future__ import annotations

import logging
import time
import uuid

from apps.usage_tracking.services.entity_extractor import extract_entity_ids
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
)

EVENT_NAME = "public_api_request"


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
        publisher_id, publisher_slug = resolve_publisher_from_request(request)
        distinct_id = self._distinct_id(request)
        entity_ids = extract_entity_ids(self._response_body(response))

        properties = {
            "method": request.method,
            "path": request.path,
            "endpoint": f"{request.method} {request.path}",
            "status_code": response.status_code,
            "latency_ms": latency_ms,
            "publisher_id": publisher_id,
            "publisher_slug": publisher_slug,
            "entity_ids": entity_ids,
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
