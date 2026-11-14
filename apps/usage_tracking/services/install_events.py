"""Records one CLI install or update traffic event per package a client resolves (Django side).

An update is a resolve of another version than the one this installation (`X-Itqan-Install-Id`)
last got for the same asset and language. Everything else is an install: first installs, repeats
of the same version, and clients that send no install id. Only events still kept count as "before"
(`USAGE_EVENT_RETENTION_MONTHS`), so an update after a longer gap counts as an install.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
import uuid

from apps.core.utils.client_ip import client_ip
from apps.usage_tracking.models import INSTALL_KINDS, TrafficEvent, TrafficKind, TrafficSource, TrafficStatusClass
from apps.usage_tracking.services.download_paths import normalize_country
from apps.usage_tracking.services.traffic_classify import channel_for, is_bot_user_agent, platform_for, ua_family
from apps.usage_tracking.services.traffic_identity import install_id_for, listener_id_for
from apps.usage_tracking.services.usage_apps import app_for_key
from apps.users.models import APIKey

# Resolves made only to check for newer versions (`itqan outdated`) are not installs.
_NON_INSTALL_COMMANDS = frozenset({"outdated"})


def _last_versions(install_id: str, asset_ids: set[int]) -> dict[tuple[int, str], int | None]:
    """(asset, language) -> the version this installation got last, from `traffic_event_install_idx`."""
    if not install_id or not asset_ids:
        return {}
    rows = (
        TrafficEvent.objects.filter(install_id=install_id, asset_id__in=asset_ids, kind__in=INSTALL_KINDS)
        .order_by("asset_id", "language", "-occurred_at", "-id")
        .distinct("asset_id", "language")
        .values_list("asset_id", "language", "asset_version_id")
    )
    return {(asset_id, language): version_id for asset_id, language, version_id in rows}


def record_installs(request, results: Iterable) -> int:
    if request.headers.get("X-Itqan-Command", "").strip().lower() in _NON_INSTALL_COMMANDS:
        return 0
    user_agent = request.headers.get("User-Agent", "")[:1024]
    family = ua_family(user_agent)
    raw_install = request.headers.get("X-Itqan-Install-Id", "")[:64]
    api_key = getattr(request, "auth", None)
    app_id = app_for_key(api_key).id if isinstance(api_key, APIKey) else None
    ip = client_ip(request) or ""
    install_id = install_id_for(raw_install)
    results = list(results)
    last_versions = _last_versions(install_id, {result.asset.id for result in results})
    now = datetime.now(UTC)
    events = []
    for result in results:
        ray_id = f"django:install:{uuid.uuid4().hex}"
        language = result.asset_language.language if result.asset_language else ""
        last_version = last_versions.get((result.asset.id, language), result.asset_version.pk)
        kind = TrafficKind.CLI_INSTALL if last_version == result.asset_version.pk else TrafficKind.CLI_UPDATE
        events.append(
            TrafficEvent(
                ray_id=ray_id,
                occurred_at=now,
                source=TrafficSource.DJANGO,
                kind=kind,
                asset_id=result.asset.id,
                asset_version_id=result.asset_version.pk,
                language=language,
                country=normalize_country(request.headers.get("CF-IPCountry")),
                channel=channel_for(
                    TrafficKind.CLI_INSTALL, family, has_install_id=bool(raw_install), app_identified=app_id is not None
                ),
                platform=platform_for(user_agent, family),
                app_id=app_id,
                endpoint=request.path[:128],
                path=request.path[:512],
                status_class=TrafficStatusClass.FULL,
                listener_id=listener_id_for(ip, user_agent, ray_id),
                install_id=install_id,
                ua_family=family,
                is_bot=is_bot_user_agent(user_agent),
            )
        )
    TrafficEvent.objects.bulk_create(events)
    return len(events)
