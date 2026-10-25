"""Nightly upkeep: monthly unique counts (kept forever) and raw-event retention."""

from __future__ import annotations

from datetime import UTC, date, datetime, time
import logging

from django.conf import settings

from apps.usage_tracking.repositories.traffic import MAINTENANCE_JOB, TrafficRepository

logger = logging.getLogger(__name__)


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
