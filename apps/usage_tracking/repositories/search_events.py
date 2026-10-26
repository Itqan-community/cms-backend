"""Gallery search events: writes from the search endpoints and the search-terms report queries."""

from __future__ import annotations

from datetime import datetime

from django.db.models import Count, Max, OuterRef, Q, Subquery

from apps.usage_tracking.models import SearchEvent


class SearchEventRepository:
    def record(self, event: SearchEvent, *, replaces_since: datetime) -> None:
        """Insert `event`, deleting the searcher's searches since `replaces_since` for a prefix of its term.

        No transaction: two racing searches can at worst leave one keystroke row behind.
        """
        prefixes = [event.term[:length] for length in range(1, len(event.term) + 1)]
        SearchEvent.objects.filter(
            listener_id=event.listener_id,
            surface=event.surface,
            occurred_at__gte=replaces_since,
            term__in=prefixes,
        ).delete()
        event.save()

    def terms(
        self, start: datetime, end: datetime, *, min_searchers: int, limit: int, zero_results_only: bool
    ) -> list[dict]:
        """Terms with at least `min_searchers` distinct searchers, most searchers first.

        Each row: term, searchers, searches, zero_results (searches that found nothing) and
        latest_results (results of the term's most recent search in the range).
        """
        events = SearchEvent.objects.filter(occurred_at__gte=start, occurred_at__lt=end)
        latest = events.filter(term=OuterRef("term")).order_by("-occurred_at", "-id").values("results")[:1]
        rows = (
            events.values("term")
            .annotate(
                searchers=Count("listener_id", distinct=True),
                searches=Count("id"),
                zero_results=Count("id", filter=Q(results=0)),
                latest_at=Max("occurred_at"),
                latest_results=Subquery(latest),
            )
            .filter(searchers__gte=min_searchers)
        )
        if zero_results_only:
            rows = rows.filter(latest_results=0)
        return list(rows.order_by("-searchers", "-searches", "term")[:limit])
