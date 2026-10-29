"""Records gallery searches for the search-terms report (spec §21.4)."""

from __future__ import annotations

from collections.abc import Callable
from functools import wraps
import logging
from typing import Any

from apps.usage_tracking.services.search_terms import record_search

logger = logging.getLogger(__name__)


def track_search(surface: str) -> Callable:
    """Record the `search` query of a paginated list endpoint, on its first page only.

    Place directly under ``@router.get(...)`` and above ``@paginate`` so the result carries
    the total ``count``. Recording never fails the request.
    """

    def wrapper(view: Callable) -> Callable:
        @wraps(view)
        def tracked(request, *args: Any, **kwargs: Any) -> Any:
            result = view(request, *args, **kwargs)
            term = request.GET.get("search", "")
            if term.strip() and request.GET.get("page", "1") in ("", "1") and isinstance(result, dict):
                try:
                    record_search(request, surface, term, int(result.get("count") or 0))
                except Exception:
                    logger.exception("track_search: recording failed")
            return result

        return tracked

    return wrapper
