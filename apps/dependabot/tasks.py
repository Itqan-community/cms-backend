"""Celery background tasks for Itqan Dependabot PR automation (ITQ-28 / #427).

Handles fan-out across opted-in repositories, batching, rate-limiting backoff,
and retry mechanisms for version-bump PRs.
"""

from __future__ import annotations

import logging
from typing import Any

from celery import shared_task

from apps.content.models import AssetVersion, VersionStateChoice
from apps.core.ninja_utils.errors import ItqanError
from apps.dependabot.models import WatchedRepository
from apps.dependabot.services.github_token import load_github_app_config
from apps.dependabot.services.pr_updater import PrUpdaterService
from apps.package_manager.services.package_registry import _parse_candidate_version

logger = logging.getLogger(__name__)

DEFAULT_BATCH_SIZE = 10
BATCH_STAGGER_SECONDS = 2


@shared_task
def dispatch_dependabot_updates_for_version(asset_version_id: int) -> dict[str, Any]:
    """Scan all opted-in repositories and dispatch version bump updates for a published asset version."""
    if not load_github_app_config().enabled:
        logger.info(
            "dispatch_dependabot_updates: skipped because Dependabot is disabled [asset_version_id=%d]",
            asset_version_id,
        )
        return {"status": "skipped", "reason": "dependabot_disabled", "dispatched_count": 0}

    try:
        asset_version = AssetVersion.objects.select_related("asset").get(pk=asset_version_id)
    except AssetVersion.DoesNotExist:
        logger.warning(
            "dispatch_dependabot_updates: asset version not found [asset_version_id=%d]",
            asset_version_id,
        )
        return {"status": "skipped", "reason": "version_not_found", "dispatched_count": 0}

    if asset_version.state != VersionStateChoice.PUBLISHED:
        logger.info(
            "dispatch_dependabot_updates: version not published [asset_version_id=%d, state=%s]",
            asset_version_id,
            asset_version.state,
        )
        return {"status": "skipped", "reason": "not_published", "dispatched_count": 0}

    if not asset_version.asset.slug:
        logger.warning(
            "dispatch_dependabot_updates: asset has no slug [asset_version_id=%d, asset_id=%d]",
            asset_version_id,
            asset_version.asset_id,
        )
        return {"status": "skipped", "reason": "missing_slug", "dispatched_count": 0}

    parsed = _parse_candidate_version(asset_version.name)
    if parsed is None:
        logger.info(
            "dispatch_dependabot_updates: asset version name is not a valid canonical SemVer [asset_version_id=%d, name=%s]",
            asset_version_id,
            asset_version.name,
        )
        return {"status": "skipped", "reason": "invalid_semver", "dispatched_count": 0}

    watched_repo_ids = list(
        WatchedRepository.objects.filter(
            status=WatchedRepository.StatusChoice.OPTED_IN,
            host=WatchedRepository.HostChoice.GITHUB,
        )
        .order_by("id")
        .values_list("id", flat=True)
    )

    if not watched_repo_ids:
        logger.info(
            "dispatch_dependabot_updates: no opted-in repositories found [asset_version_id=%d]",
            asset_version_id,
        )
        return {"status": "success", "dispatched_count": 0}

    # Fan out in batches with staggered countdown to prevent GitHub API rate-limit spikes
    for idx, repo_id in enumerate(watched_repo_ids):
        countdown = (idx // DEFAULT_BATCH_SIZE) * BATCH_STAGGER_SECONDS
        process_repository_dependabot_update.apply_async(
            args=[repo_id, asset_version_id],
            countdown=countdown,
        )

    logger.info(
        "dispatch_dependabot_updates: dispatched updates across repositories [asset_version_id=%d, count=%d]",
        asset_version_id,
        len(watched_repo_ids),
    )
    return {
        "status": "success",
        "dispatched_count": len(watched_repo_ids),
        "asset_slug": asset_version.asset.slug,
        "version": asset_version.name,
    }


@shared_task(bind=True, max_retries=5)
def process_repository_dependabot_update(self, watched_repo_id: int, asset_version_id: int) -> dict[str, Any]:
    """Process a single repository for an asset version bump with automatic rate-limit backoff."""
    try:
        watched_repo = WatchedRepository.objects.get(pk=watched_repo_id)
        asset_version = AssetVersion.objects.select_related("asset").get(pk=asset_version_id)
    except (WatchedRepository.DoesNotExist, AssetVersion.DoesNotExist) as exc:
        logger.warning(
            "process_repository_dependabot_update: entity not found [repo_id=%d, version_id=%d, error=%s]",
            watched_repo_id,
            asset_version_id,
            exc,
        )
        return {"status": "skipped", "reason": "entity_not_found"}

    updater = PrUpdaterService()
    try:
        result = updater.process_repository(watched_repo, asset_version)
        return {
            "status": "success",
            "action": result.action,
            "reason": result.reason,
            "pr_number": result.pr.number if result.pr else None,
            "old_version": result.old_version,
            "new_version": result.new_version,
        }
    except ItqanError as exc:
        if exc.error_name == "github_rate_limited":
            retry_after = 60
            if isinstance(exc.extra, dict) and "retry_after_seconds" in exc.extra:
                retry_after = exc.extra["retry_after_seconds"]
            logger.warning(
                "process_repository_dependabot_update: rate limited by GitHub, backing off [repo_id=%d, countdown=%d]",
                watched_repo_id,
                retry_after,
            )
            raise self.retry(exc=exc, countdown=retry_after) from exc

        if exc.error_name in ("github_upstream_error",):
            retry_delay = 15 * (self.request.retries + 1)
            logger.warning(
                "process_repository_dependabot_update: transient GitHub error, retrying [repo_id=%d, retry=%d, delay=%d]",
                watched_repo_id,
                self.request.retries,
                retry_delay,
            )
            raise self.retry(exc=exc, countdown=retry_delay) from exc

        logger.error(
            "process_repository_dependabot_update: permanent failure [repo_id=%d, version_id=%d, error=%s]",
            watched_repo_id,
            asset_version_id,
            exc.error_name,
        )
        return {"status": "error", "error_name": exc.error_name, "message": exc.message}
