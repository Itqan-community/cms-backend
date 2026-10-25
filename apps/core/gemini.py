"""Minimal Gemini API (generateContent) client used for admin-side AI helpers.

Free tier only: limits are per Google Cloud project, so callers must treat
every call as optional and handle ``GeminiError``.
"""

import json
import logging
from typing import Any

from django.conf import settings
import httpx

logger = logging.getLogger(__name__)

API_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"


class GeminiError(Exception):
    """Gemini returned something unusable."""


class GeminiRateLimited(GeminiError):
    """Free-tier per-minute limit reached (HTTP 429); retrying shortly works."""


class GeminiQuotaExceeded(GeminiRateLimited):
    """Free-tier daily limit reached (HTTP 429 on a per-day quota); resets at midnight Pacific time."""


class GeminiUnavailable(GeminiError):
    """Not configured, timed out, or Gemini is erroring."""


class GeminiClient:
    """Args:
    http_client: Optional ``httpx.Client``. Tests inject
        ``httpx.Client(transport=httpx.MockTransport(...))``.
    """

    def __init__(self, http_client: httpx.Client | None = None) -> None:
        self._http_client = http_client

    @staticmethod
    def is_configured() -> bool:
        return bool(settings.GEMINI_API_KEY)

    def generate_json(self, *, system: str, prompt: str, schema: dict, model: str | None = None) -> dict:
        body = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.2, "responseMimeType": "application/json", "responseSchema": schema},
        }
        text = self._text(self._post(model or settings.GEMINI_FAST_MODEL, body))
        try:
            parsed = json.loads(text)
        except ValueError:
            raise GeminiError("Gemini returned non-JSON output.") from None
        if not isinstance(parsed, dict):
            raise GeminiError("Gemini returned a non-object JSON value.")
        return parsed

    def _post(self, model: str, body: dict) -> dict[str, Any]:
        timeout = settings.GEMINI_TIMEOUT_SECONDS
        if not self.is_configured():
            raise GeminiUnavailable("GEMINI_API_KEY is not set.")
        url = f"{API_BASE_URL}/models/{model}:generateContent"
        headers = {"x-goog-api-key": settings.GEMINI_API_KEY}
        try:
            if self._http_client is not None:
                response = self._http_client.post(url, json=body, headers=headers, timeout=timeout)
            else:
                with httpx.Client(timeout=timeout) as client:
                    response = client.post(url, json=body, headers=headers)
        except httpx.HTTPError as exc:
            logger.warning("gemini: request failed [model=%s, error=%s]", model, type(exc).__name__)
            raise GeminiUnavailable(str(exc)) from None
        if response.status_code == 429:
            if self._is_daily_quota(response):
                logger.warning("gemini: daily quota exceeded [model=%s]", model)
                raise GeminiQuotaExceeded("Gemini free-tier daily limit reached.")
            logger.warning("gemini: rate limited [model=%s]", model)
            raise GeminiRateLimited("Gemini free-tier rate limit reached.")
        if response.status_code >= 400:
            logger.warning("gemini: error response [model=%s, status=%s]", model, response.status_code)
            raise GeminiUnavailable(f"Gemini returned HTTP {response.status_code}.")
        try:
            payload = response.json()
        except ValueError:
            raise GeminiError("Gemini returned an unreadable response.") from None
        if not isinstance(payload, dict):
            raise GeminiError("Gemini returned an unexpected response.")
        return payload

    @staticmethod
    def _is_daily_quota(response: httpx.Response) -> bool:
        """True when a 429 names a per-day quota (``quotaId`` like ``GenerateRequestsPerDay...``)."""
        try:
            details = response.json()["error"]["details"]
        except (ValueError, KeyError, TypeError):
            return False
        if not isinstance(details, list):
            return False
        for detail in details:
            violations = detail.get("violations") if isinstance(detail, dict) else None
            for violation in violations if isinstance(violations, list) else []:
                if isinstance(violation, dict) and "PerDay" in str(violation.get("quotaId", "")):
                    return True
        return False

    @staticmethod
    def _text(payload: dict[str, Any]) -> str:
        try:
            parts = payload["candidates"][0]["content"]["parts"]
        except (KeyError, IndexError, TypeError):
            raise GeminiError("Gemini response has no content.") from None
        if not isinstance(parts, list):
            raise GeminiError("Gemini response has no content.")
        text = "".join(str(p.get("text", "")) for p in parts if isinstance(p, dict)).strip()
        if not text:
            raise GeminiError("Gemini response is empty.")
        return text
