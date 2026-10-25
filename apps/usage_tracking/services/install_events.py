"""Records one `cli_install` traffic event per package a client resolves (Django side)."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
import uuid

from apps.core.utils.client_ip import client_ip
from apps.usage_tracking.models import TrafficEvent, TrafficKind, TrafficSource, TrafficStatusClass
from apps.usage_tracking.services.download_paths import normalize_country
from apps.usage_tracking.services.traffic_classify import channel_for, is_bot_user_agent, platform_for, ua_family
from apps.usage_tracking.services.traffic_identity import install_id_for, listener_id_for
from apps.usage_tracking.services.usage_apps import app_for_key
from apps.users.models import APIKey

# Resolves made only to check for newer versions (`itqan outdated`) are not installs.
_NON_INSTALL_COMMANDS = frozenset({"outdated"})


def record_installs(request, results: Iterable) -> int:
    if request.headers.get("X-Itqan-Command", "").strip().lower() in _NON_INSTALL_COMMANDS:
        return 0
    user_agent = request.headers.get("User-Agent", "")[:1024]
    family = ua_family(user_agent)
    raw_install = request.headers.get("X-Itqan-Install-Id", "")[:64]
    api_key = getattr(request, "auth", None)
    app_id = app_for_key(api_key).id if isinstance(api_key, APIKey) else None
    ip = client_ip(request) or ""
    now = datetime.now(UTC)
    events = []
    for result in results:
        ray_id = f"django:install:{uuid.uuid4().hex}"
        events.append(
            TrafficEvent(
                ray_id=ray_id,
                occurred_at=now,
                source=TrafficSource.DJANGO,
                kind=TrafficKind.CLI_INSTALL,
                asset_id=result.asset.id,
                asset_version_id=result.asset_version.pk,
                language=result.asset_language.language if result.asset_language else "",
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
                install_id=install_id_for(raw_install),
                ua_family=family,
                is_bot=is_bot_user_agent(user_agent),
            )
        )
    TrafficEvent.objects.bulk_create(events)
    return len(events)
