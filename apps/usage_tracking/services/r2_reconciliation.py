"""Hourly R2 read counts per asset object, beside the edge requests seen for the same object.

R2 counts reads from every route (custom domain, presigned URLs, r2.dev); the difference to the
edge count is traffic the Logpush import cannot see. The last 24 hours are re-done every run,
because Logpush files and R2 analytics both arrive with some delay.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import logging

from django.conf import settings

from apps.usage_tracking.models import R2ObjectReadsHourly
from apps.usage_tracking.repositories.traffic import R2_RECONCILIATION_JOB, TrafficRepository, floor_hour
from apps.usage_tracking.services.download_paths import parse_download_path
from apps.usage_tracking.services.r2_reads_client import R2ReadsClient

logger = logging.getLogger(__name__)

_HOUR = timedelta(hours=1)
_LAG = timedelta(hours=3)  # leave time for the hourly Logpush import to cover the hour
_REFRESH = timedelta(hours=24)
_MAX_HOURS_PER_RUN = 48


@dataclass(frozen=True, slots=True)
class ReconcileResult:
    hours: int
    error: str


def _build_client() -> R2ReadsClient:
    return R2ReadsClient(account_tag=settings.CF_ACCOUNT_ID, api_token=settings.USAGE_ANALYTICS_API_TOKEN)


def reconcile_r2_reads(now: datetime | None = None) -> ReconcileResult:
    if not settings.ENABLE_USAGE_R2_RECONCILIATION:
        logger.info("reconcile_r2_reads: disabled via ENABLE_USAGE_R2_RECONCILIATION; skipping")
        return ReconcileResult(0, "")
    if not (settings.CF_ACCOUNT_ID and settings.USAGE_ANALYTICS_API_TOKEN and settings.CLOUDFLARE_R2_BUCKET):
        logger.warning(
            "reconcile_r2_reads: missing CF_ACCOUNT_ID/USAGE_ANALYTICS_API_TOKEN/CLOUDFLARE_R2_BUCKET; skipping"
        )
        return ReconcileResult(0, "")

    now = now or datetime.now(UTC)
    repo = TrafficRepository()
    if not repo.try_lock(R2_RECONCILIATION_JOB):
        return ReconcileResult(0, "")

    hours = 0
    error = ""
    try:
        client = _build_client()
        end = floor_hour(now - _LAG)
        watermark = repo.get_watermark(R2_RECONCILIATION_JOB)
        hour = min(watermark, end - _REFRESH) if watermark else end - _REFRESH
        while hour < end and hours < _MAX_HOURS_PER_RUN:
            reads, truncated = client.fetch_reads(settings.CLOUDFLARE_R2_BUCKET, hour, hour + _HOUR)
            if truncated:
                logger.error("reconcile_r2_reads: hour %s hit the page limit; counts are partial", hour)
            edge = repo.edge_requests_by_object(hour)
            rows = []
            for key, count in reads.items():
                file = parse_download_path("/" + key)
                if file is None:
                    continue
                rows.append(
                    R2ObjectReadsHourly(
                        hour=hour,
                        object_key=key[:512],
                        asset_id=file.asset_id,
                        reads=count,
                        edge_requests=edge.get("/" + key, 0),
                    )
                )
            repo.replace_r2_reads(hour, rows)
            hour += _HOUR
            hours += 1
    except Exception as exc:  # noqa: BLE001 — record, alert, and let the next run resume
        error = f"{type(exc).__name__}: {exc}"
        logger.exception("reconcile_r2_reads: run failed after %d hour(s)", hours)
    finally:
        try:
            repo.record_run(R2_RECONCILIATION_JOB, now, error)
        finally:
            repo.unlock(R2_RECONCILIATION_JOB)
    return ReconcileResult(hours, error)
