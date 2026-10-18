"""Hourly: copy Django usage events into traffic events and roll up hours with Django rows.

Copies gallery views and downloads served by presigned URLs (CDN downloads are counted from the
edge), and rebuilds every hour that received Django-sourced traffic events since the last run,
including CLI installs written at resolve time. `ray_id = django:<kind>:<pk>` keeps re-runs safe.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import logging

from django.conf import settings
from django.db.models import Max

from apps.content.models import UsageEvent
from apps.usage_tracking.models import TrafficChannel, TrafficEvent, TrafficKind, TrafficSource, TrafficStatusClass
from apps.usage_tracking.repositories.traffic import DJANGO_FOLDIN_JOB, TrafficRepository, floor_hour
from apps.usage_tracking.services.traffic_classify import is_bot_user_agent, platform_for, ua_family
from apps.usage_tracking.services.traffic_identity import listener_id_for

logger = logging.getLogger(__name__)

_BATCH = 5000
_EVENT_KINDS = {
    UsageEvent.UsageKindChoice.VIEW: ("view", TrafficKind.VIEW, TrafficChannel.WEB),
    UsageEvent.UsageKindChoice.FILE_DOWNLOAD: ("download", TrafficKind.GALLERY_DOWNLOAD, TrafficChannel.GALLERY),
}


@dataclass(frozen=True, slots=True)
class FoldInResult:
    events: int
    hours: int
    error: str


def _copy(event: UsageEvent) -> TrafficEvent | None:
    prefix, kind, channel = _EVENT_KINDS[event.usage_kind]
    if kind == TrafficKind.GALLERY_DOWNLOAD and (event.metadata or {}).get("delivery") == "cdn":
        return None  # the edge already counted this download
    ray_id = f"django:{prefix}:{event.pk}"
    user_agent = (event.user_agent or "")[:1024]
    family = ua_family(user_agent)
    return TrafficEvent(
        ray_id=ray_id,
        occurred_at=event.created_at,
        source=TrafficSource.DJANGO,
        kind=kind,
        asset_id=event.asset_id,
        language=str((event.metadata or {}).get("language") or "")[:10],
        country="XX",
        channel=channel,
        platform=platform_for(user_agent, family),
        status_class=TrafficStatusClass.FULL,
        listener_id=listener_id_for(event.ip_address or "", user_agent, ray_id),
        ua_family=family,
        is_bot=is_bot_user_agent(user_agent),
    )


def fold_in_django_events(now: datetime | None = None) -> FoldInResult:
    now = now or datetime.now(UTC)
    repo = TrafficRepository()
    if not repo.try_lock(DJANGO_FOLDIN_JOB):
        return FoldInResult(0, 0, "")
    copied = hours_rebuilt = 0
    error = ""
    try:
        state = repo.get_state(DJANGO_FOLDIN_JOB)
        if state.cursor is None:
            # First run: older UsageEvent rows carry the proxy IP, so start after them.
            start_id = UsageEvent.objects.aggregate(top=Max("id"))["top"] or 0
            last_traffic_id = TrafficEvent.objects.aggregate(top=Max("id"))["top"] or 0
            repo.set_cursor(DJANGO_FOLDIN_JOB, start_id, traffic_cursor=last_traffic_id)
            return FoldInResult(0, 0, "")
        # Copy the whole backlog in batches so a busy hour can never leave the fold-in behind.
        cursor = state.cursor
        while True:
            events = list(
                UsageEvent.objects.filter(id__gt=cursor, usage_kind__in=list(_EVENT_KINDS)).order_by("id")[:_BATCH]
            )
            rows = [row for row in (_copy(event) for event in events) if row is not None]
            TrafficEvent.objects.bulk_create(rows, ignore_conflicts=True)
            copied += len(rows)
            if events:
                cursor = events[-1].id
            if len(events) < _BATCH:
                break
        # Every hour that gained Django-sourced rows since the last run (fold-in and CLI installs).
        new_rows = TrafficEvent.objects.filter(source=TrafficSource.DJANGO, id__gt=state.traffic_cursor or 0)
        hours = {floor_hour(at) for at in new_rows.values_list("occurred_at", flat=True)}
        play_window = timedelta(minutes=settings.ASSET_DOWNLOAD_PLAY_WINDOW_MINUTES)
        for hour in sorted(hours):
            repo.rebuild_hour(hour, play_window)
        hours_rebuilt = len(hours)
        top_traffic = new_rows.aggregate(top=Max("id"))["top"] or state.traffic_cursor or 0
        repo.set_cursor(DJANGO_FOLDIN_JOB, cursor, traffic_cursor=top_traffic)
    except Exception as exc:  # noqa: BLE001 — record, alert, and let the next run resume
        error = f"{type(exc).__name__}: {exc}"
        logger.exception("fold_in_django_events: run failed")
    finally:
        try:
            repo.record_run(DJANGO_FOLDIN_JOB, now, error)
        finally:
            repo.unlock(DJANGO_FOLDIN_JOB)
    return FoldInResult(copied, hours_rebuilt, error)
