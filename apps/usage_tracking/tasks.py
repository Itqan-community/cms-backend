"""Celery tasks for usage tracking."""

from __future__ import annotations

import logging

from celery import shared_task

from apps.usage_tracking.services.asset_download_sync import sync_asset_downloads
from apps.usage_tracking.services.django_foldin import fold_in_django_events
from apps.usage_tracking.services.logpush_import import import_logpush
from apps.usage_tracking.services.r2_reconciliation import reconcile_r2_reads
from apps.usage_tracking.services.traffic_maintenance import run_usage_maintenance

logger = logging.getLogger(__name__)


@shared_task(acks_late=True, soft_time_limit=900, time_limit=960, ignore_result=True)
def sync_asset_downloads_task() -> None:
    """Import asset download data from Cloudflare (see `asset_download_sync`).

    No autoretry: failures are recorded on the sync state and the next hourly run
    resumes from the watermark. Re-delivery is safe because each hour is replaced.
    """
    result = sync_asset_downloads()
    logger.info("sync_asset_downloads_task: synced %d hour(s); error=%r", result.hours_synced, result.error)


@shared_task(acks_late=True, soft_time_limit=1500, time_limit=1560, ignore_result=True)
def import_logpush_task() -> None:
    """Import new Cloudflare Logpush files (see `logpush_import`).

    No autoretry: unimported files stay pending and the next hourly run picks them up.
    """
    result = import_logpush()
    logger.info("import_logpush_task: files=%d events=%d error=%r", result.files_imported, result.events, result.error)


@shared_task(acks_late=True, soft_time_limit=900, time_limit=960, ignore_result=True)
def reconcile_r2_reads_task() -> None:
    """Record R2 reads per asset object (see `r2_reconciliation`)."""
    result = reconcile_r2_reads()
    logger.info("reconcile_r2_reads_task: hours=%d error=%r", result.hours, result.error)


@shared_task(acks_late=True, soft_time_limit=1500, time_limit=1560, ignore_result=True)
def usage_maintenance_task() -> None:
    """Rebuild monthly unique counts and purge expired traffic events."""
    run_usage_maintenance()


@shared_task(acks_late=True, soft_time_limit=900, time_limit=960, ignore_result=True)
def fold_in_django_events_task() -> None:
    """Copy Django usage events into traffic events and roll up their hours."""
    result = fold_in_django_events()
    logger.info("fold_in_django_events_task: events=%d hours=%d error=%r", result.events, result.hours, result.error)
