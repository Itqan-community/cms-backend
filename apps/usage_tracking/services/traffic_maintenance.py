"""Nightly upkeep: monthly unique counts (kept forever) and raw-event retention."""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
import logging

from django.conf import settings

from apps.usage_tracking.repositories.traffic import (
    DJANGO_FOLDIN_JOB,
    LOGPUSH_JOB,
    MAINTENANCE_JOB,
    TrafficRepository,
)

logger = logging.getLogger(__name__)

# Every job that rebuilds hours (Logpush import, Django fold-in) or purges events (maintenance).
_REBUILD_LOCKS = (LOGPUSH_JOB, DJANGO_FOLDIN_JOB, MAINTENANCE_JOB)


def add_months(month: date, months: int) -> date:
    """First day of the month `months` away from `month`'s month."""
    years, index = divmod(month.month - 1 + months, 12)
    return date(month.year + years, index + 1, 1)


def run_usage_maintenance(now: datetime | None = None) -> int:
    now = now or datetime.now(UTC)
    repo = TrafficRepository()
    if not repo.try_lock(MAINTENANCE_JOB):
        return 0
    try:
        this_month = now.date().replace(day=1)
        # The previous month too: late Logpush files can still land in it during the first days.
        for month in (add_months(this_month, -1), this_month):
            repo.rebuild_month_uniques(month)
        cutoff = datetime.combine(add_months(this_month, -settings.USAGE_EVENT_RETENTION_MONTHS), time.min, tzinfo=UTC)
        deleted = repo.purge_events_before(cutoff)
        logger.info("usage_maintenance: rebuilt monthly uniques; purged %d event(s) before %s", deleted, cutoff)
        return deleted
    finally:
        repo.unlock(MAINTENANCE_JOB)


def rebuild_rollups(since: date) -> int | None:
    """Rebuild the hourly and daily rollups of every hour since `since` that still has events.

    Hours whose events were purged are left alone (rebuilding them would erase their rollups).
    Holds the Logpush, fold-in and maintenance locks, so it never races a job that rebuilds the
    same hours or purges their events; returns None when any of them is busy.
    """
    repo = TrafficRepository()
    held: list[str] = []
    try:
        for job in _REBUILD_LOCKS:
            if not repo.try_lock(job):
                return None
            held.append(job)
        play_window = timedelta(minutes=settings.ASSET_DOWNLOAD_PLAY_WINDOW_MINUTES)
        hours = repo.event_hours_since(datetime.combine(since, time.min, tzinfo=UTC))
        for hour in hours:
            repo.rebuild_hour(hour, play_window)
        logger.info("rebuild_rollups: rebuilt %d hour(s) since %s", len(hours), since)
        return len(hours)
    finally:
        for job in reversed(held):
            repo.unlock(job)
