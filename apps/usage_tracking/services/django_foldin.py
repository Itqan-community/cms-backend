"""Hourly: copy Django usage events into traffic events and roll up hours with Django rows.

Copies gallery views and downloads served by presigned URLs (CDN downloads are counted from the
edge), and rebuilds every hour that received Django-sourced traffic events since the last run,
including CLI installs written at resolve time. `ray_id = django:<kind>:<pk>` keeps re-runs safe.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import ipaddress
import logging
from time import monotonic

from django.conf import settings
from django.db.models import Max

from apps.content.models import UsageEvent
from apps.usage_tracking.models import TrafficChannel, TrafficEvent, TrafficKind, TrafficSource, TrafficStatusClass
from apps.usage_tracking.repositories.traffic import DJANGO_FOLDIN_JOB, TrafficRepository, floor_hour
from apps.usage_tracking.services.traffic_classify import is_bot_user_agent, platform_for, ua_family
from apps.usage_tracking.services.traffic_identity import listener_id_for

logger = logging.getLogger(__name__)

_BATCH = 5000
# Traffic rows whose hours are rolled up before the cursor is saved.
_TRAFFIC_BATCH = 1000
# Stop starting new days well before the task's 900s soft limit: a limit that fires inside a
# transaction can leave the worker's database connection unusable for every later task.
_TIME_BUDGET_SECONDS = 600
# Private ranges only: `ipaddress.is_private` also covers documentation and other public-looking blocks.
_PROXY_NETWORKS = tuple(
    ipaddress.ip_network(net) for net in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "fc00::/7")
)
_EVENT_KINDS = {
    UsageEvent.UsageKindChoice.VIEW: ("view", TrafficKind.VIEW, TrafficChannel.WEB),
    UsageEvent.UsageKindChoice.FILE_DOWNLOAD: ("download", TrafficKind.GALLERY_DOWNLOAD, TrafficChannel.GALLERY),
}


@dataclass(frozen=True, slots=True)
class FoldInResult:
    events: int
    hours: int
    error: str


def _is_proxy_ip(value: str | None) -> bool:
    """Caddy's container address: what events recorded before the client-IP fix (or by old workers
    still running mid-deploy) carry instead of the visitor's. Visitors via Cloudflare never have one."""
    try:
        address = ipaddress.ip_address(value or "")
    except ValueError:
        return False
    return address.is_loopback or address.is_link_local or any(address in net for net in _PROXY_NETWORKS)


def _copy(event: UsageEvent) -> TrafficEvent | None:
    prefix, kind, channel = _EVENT_KINDS[event.usage_kind]
    if kind == TrafficKind.GALLERY_DOWNLOAD and (event.metadata or {}).get("delivery") == "cdn":
        return None  # the edge already counted this download
    if _is_proxy_ip(event.ip_address):
        return None  # one shared address would merge every visitor into one listener
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


def fold_in_django_events(
    now: datetime | None = None, time_budget_seconds: float = _TIME_BUDGET_SECONDS
) -> FoldInResult:
    now = now or datetime.now(UTC)
    repo = TrafficRepository()
    if not repo.try_lock(DJANGO_FOLDIN_JOB):
        return FoldInResult(0, 0, "")
    copied = hours_rebuilt = 0
    error = ""
    try:
        state = repo.get_state(DJANGO_FOLDIN_JOB)
        if state.cursor is None:
            # No cutover recorded (migration 0005 sets it at deploy): older UsageEvent rows carry
            # the proxy IP, so start after them.
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
        traffic_cursor = state.traffic_cursor or 0
        repo.set_cursor(DJANGO_FOLDIN_JOB, cursor, traffic_cursor=traffic_cursor)
        # Every hour that gained Django-sourced rows since the last run (fold-in and CLI installs),
        # up to a fixed id: rows written while hours rebuild stay for the next run. Rolled up a
        # batch of rows at a time, saving the cursor after each, so a backlog bigger than one run
        # (a long outage, a data import) is worked off over several runs instead of never.
        top_traffic = TrafficEvent.objects.aggregate(top=Max("id"))["top"] or 0
        play_window = timedelta(minutes=settings.ASSET_DOWNLOAD_PLAY_WINDOW_MINUTES)
        deadline = monotonic() + time_budget_seconds
        while traffic_cursor < top_traffic:
            batch = list(
                TrafficEvent.objects.filter(source=TrafficSource.DJANGO, id__gt=traffic_cursor, id__lte=top_traffic)
                .order_by("id")
                .values_list("id", "occurred_at")[:_TRAFFIC_BATCH]
            )
            hours: set[datetime] = set()
            for _, at in batch:
                hours.add(floor_hour(at))
                # An event near the end of an hour is context for the next hour's sessions.
                hours.add(floor_hour(at + play_window))
            rebuilt = repo.rebuild_hours(hours, play_window, deadline)
            hours_rebuilt += len(rebuilt)
            if len(rebuilt) < len(hours):
                logger.info(
                    "fold_in_django_events: time budget spent; the next run resumes after id %d", traffic_cursor
                )
                break
            traffic_cursor = batch[-1][0] if len(batch) == _TRAFFIC_BATCH else top_traffic
            repo.set_cursor(DJANGO_FOLDIN_JOB, cursor, traffic_cursor=traffic_cursor)
    except Exception as exc:  # noqa: BLE001 — record, alert, and let the next run resume
        error = f"{type(exc).__name__}: {exc}"
        logger.exception("fold_in_django_events: run failed")
    finally:
        try:
            repo.record_run(DJANGO_FOLDIN_JOB, now, error)
        finally:
            repo.unlock(DJANGO_FOLDIN_JOB)
    return FoldInResult(copied, hours_rebuilt, error)
