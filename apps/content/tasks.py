"""
Celery tasks for async analytics processing
Handles usage event tracking and analytics computations
"""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import TYPE_CHECKING, TypedDict

from celery import shared_task
from django.db import transaction

if TYPE_CHECKING:
    from apps.content.models import UsageEvent

logger = logging.getLogger(__name__)


class EventData(TypedDict):
    developer_user_id: int
    usage_kind: UsageEvent.UsageKindChoice
    asset_id: int
    metadata: dict | None
    ip_address: str | None
    user_agent: str | None


@shared_task(bind=True, max_retries=3)
def create_usage_event_task(self, event_data):
    """
    Async task to create usage events without blocking API requests

    Args:
        event_data: Dictionary containing:
            - developer_user_id: User ID
            - usage_kind: Type of usage (view, file_download, api_access)
            - asset_id: Asset ID
            - metadata: Additional event metadata
            - ip_address: Client IP address
            - user_agent: Client user agent
    """
    logger.info(
        f"Task started [task=create_usage_event_task, task_id={self.request.id}, user_id={event_data.get('developer_user_id')}]"
    )
    try:
        from .models import Asset, UsageEvent

        required_fields = ["developer_user_id", "usage_kind", "asset_id"]
        for field in required_fields:
            if field not in event_data:
                logger.error(f"Missing required field '{field}' in usage event data")
                return False

        from apps.users.models import User

        try:
            user = User.objects.get(id=event_data["developer_user_id"])
        except User.DoesNotExist:
            logger.error(f"User {event_data['developer_user_id']} not found for usage event")
            return False

        asset_id = event_data["asset_id"]
        try:
            Asset.objects.get(id=asset_id)
        except Asset.DoesNotExist:
            logger.error(f"Asset {asset_id} not found for usage event")
            return False

        with transaction.atomic():
            usage_event = UsageEvent.objects.create(
                developer_user=user,
                usage_kind=event_data["usage_kind"],
                asset_id=asset_id,
                metadata=event_data.get("metadata", {}),
                ip_address=event_data.get("ip_address"),
                user_agent=event_data.get("user_agent", ""),
                effective_license=event_data.get("effective_license", ""),
            )

            logger.info(
                f"Task completed [task=create_usage_event_task, task_id={self.request.id}, usage_event_id={usage_event.id}, user_id={user.id}]"
            )
            return True

    except Exception as exc:
        logger.error(f"Failed to create usage event: {exc}")
        logger.warning(
            f"Retrying create_usage_event_task [task_id={self.request.id}, retry={self.request.retries + 1}/{self.max_retries}, exc={exc}]"
        )
        raise self.retry(exc=exc, countdown=60 * (self.request.retries + 1)) from exc


@shared_task
def cleanup_stuck_multipart_uploads_task(older_than_hours: int = 2):
    """
    Periodic task to cleanup stuck recitations multipart uploads to R2

    This task should run every 4 hours to catch uploads that:
    - Were started but never completed (browser closed, network failure, etc.)
    - Failed but weren't properly aborted by the client
    - Have been stuck for more than the threshold

    Args:
        older_than_hours: Cleanup uploads older than this many hours (default: 2)

    Returns:
        Dictionary with cleanup statistics
    """
    logger.info(f"Task started [task=cleanup_stuck_multipart_uploads_task, older_than_hours={older_than_hours}]")
    try:
        from apps.content.services.admin.asset_recitation_audio_tracks_direct_upload_service import (
            AssetRecitationAudioTracksDirectUploadService,
        )

        service = AssetRecitationAudioTracksDirectUploadService()
        result = service.cleanup_stuck_uploads(older_than_hours=older_than_hours)

        logger.info(f"Cleanup stuck uploads completed. aborted={result.get('abortedUploads', 0)}")

        return result

    except Exception as exc:
        message = f"Failed to cleanup stuck multipart uploads: {exc}"
        logger.error(message)
        return {"abortedUploads": 0, "message": message}


@shared_task
def notify_asset_version_created(asset_version_id: int) -> None:
    logger.info(f"Task started [task=notify_asset_version_created, asset_version_id={asset_version_id}]")
    from apps.content.services.asset_version_notifier import AssetVersionNotifier

    AssetVersionNotifier().notify_new_version(asset_version_id)
    logger.info(f"Task completed [task=notify_asset_version_created, asset_version_id={asset_version_id}]")


@shared_task(bind=True, max_retries=3)
def send_issue_status_update_email(self, report_id: int, old_status: str, new_status: str) -> None:
    """
    Async wrapper that delegates to IssueReportNotificationService.
    Retries up to 3 times on transient failures with linear back-off.
    """
    logger.info(
        f"Task started [task=send_issue_status_update_email, report_id={report_id}, {old_status!r} -> {new_status!r}]"
    )
    try:
        from apps.content.services.issue_report_notifications import IssueReportNotificationService

        IssueReportNotificationService().notify_status_changed(report_id, old_status, new_status)
        logger.info(f"Task completed [task=send_issue_status_update_email, report_id={report_id}]")
    except Exception as exc:
        logger.error(f"Task failed [task=send_issue_status_update_email, report_id={report_id}]: {exc}")
        raise self.retry(exc=exc, countdown=60 * (self.request.retries + 1)) from exc


@shared_task
def send_access_request_outcome_email(request_id: int) -> None:
    logger.info(f"Task started [task=send_access_request_outcome_email, request_id={request_id}]")
    from apps.content.services.access_request_notification_service import AccessRequestNotificationService

    AccessRequestNotificationService().send_developer_outcome_email(request_id)
    logger.info(f"Task completed [task=send_access_request_outcome_email, request_id={request_id}]")


@shared_task
def notify_publishers_pending_access_requests() -> None:
    logger.info("Task started [task=notify_publishers_pending_access_requests]")
    from apps.content.services.access_request_notification_service import AccessRequestNotificationService

    AccessRequestNotificationService().notify_publishers_of_pending_requests()
    logger.info("Task completed [task=notify_publishers_pending_access_requests]")


@shared_task(
    bind=True,
    max_retries=3,
    soft_time_limit=1500,
    time_limit=1800,
)
def slice_recitation_track_task(self, track_id: int) -> dict:
    """
    Slice one recitation surah track into per-ayah audio files.

    Delegates to RecitationAudioSlicingService.slice_track and invalidates the
    asset's recitation caches only after a fully successful service run.

    Retries are limited to transient storage failures (ItqanError
    "storage_error"): validation, missing-track and ffmpeg failures are
    permanent and never retried. Backoff follows the linear pattern used by
    send_issue_status_update_email (countdown=60s * (retries + 1)).

    Time limits: slicing runs ffmpeg once per ayah with its own 30s timeout,
    so the repository-wide 60s soft limit does not apply. The longest surah
    (Al-Baqarah, 286 ayahs) at a generous ~5s per slice takes ~24 minutes;
    soft_time_limit=1500 (25 min) / time_limit=1800 (30 min) keep the same
    20% headroom convention as sync_audio_usage_task (300/360).

    Args:
        track_id: RecitationSurahTrack primary key.

    Returns:
        The slicing service result: track_id, asset_id, sliced count and keys.
    """
    logger.info(f"Task started [task=slice_recitation_track_task, task_id={self.request.id}, track_id={track_id}]")
    from apps.content.cache import invalidate_recitation_tracks_cache
    from apps.content.services.admin.recitation_audio_slicing_service import RecitationAudioSlicingService
    from apps.core.ninja_utils.errors import ItqanError

    try:
        result = RecitationAudioSlicingService().slice_track(track_id)
    except ItqanError as exc:
        if exc.error_name == "storage_error" and self.request.retries < self.max_retries:
            logger.warning(
                f"Retrying slice_recitation_track_task [task_id={self.request.id}, track_id={track_id}, "
                f"retry={self.request.retries + 1}/{self.max_retries}]"
            )
            raise self.retry(exc=exc, countdown=60 * (self.request.retries + 1)) from exc
        logger.error(
            f"Task failed [task=slice_recitation_track_task, task_id={self.request.id}, track_id={track_id}, "
            f"error_name={exc.error_name}]"
        )
        raise

    invalidate_recitation_tracks_cache(asset_id=result["asset_id"])
    logger.info(
        f"Task completed [task=slice_recitation_track_task, task_id={self.request.id}, track_id={track_id}, "
        f"sliced={result['sliced']}]"
    )
    return result


@shared_task(
    soft_time_limit=300,
    time_limit=360,
)
def compute_similar_recommendations_task() -> dict:
    """
    Nightly recompute of "similar content" recommendation scores.

    Delegates to RecommendationsService.compute_similar_recommendations, which scores
    every READY, publicly-visible asset against others sharing reciter/riwayah/qiraah/
    category and writes the top matches per asset to Redis as sorted sets. See
    apps.content.services.recommendations for the scoring design.

    Runs nightly at 2:00 via Celery beat (config/celery.py). Catalog-sized workloads
    are expected to finish well within the 5-minute soft limit; the limits mirror
    sync_audio_usage_task's 20%-headroom convention (300s soft / 360s hard).
    """
    logger.info("Task started [task=compute_similar_recommendations_task]")
    from apps.content.services.recommendations import compute_similar_recommendations

    result = compute_similar_recommendations()
    logger.info(f"Task completed [task=compute_similar_recommendations_task, result={result}]")
    return result


@shared_task(
    soft_time_limit=120,
    time_limit=180,
)
def compute_trending_recommendations_task() -> dict:
    """
    Recompute "trending" recommendation scores from recent usage events.

    Delegates to RecommendationsService.compute_trending_recommendations, which
    aggregates recent UsageEvent rows (weighted by event kind) into a global and a
    per-category Redis leaderboard. See apps.content.services.recommendations for the
    scoring design.

    Runs every 15 minutes via Celery beat (config/celery.py) -- much more often than
    similar/personalized, since "trending" is meant to track recent activity rather
    than a nightly snapshot. The 2-minute soft limit reflects that this only scans a
    trailing usage-event window, not the whole catalog.
    """
    logger.info("Task started [task=compute_trending_recommendations_task]")
    from apps.content.services.recommendations import compute_trending_recommendations

    result = compute_trending_recommendations()
    logger.info(f"Task completed [task=compute_trending_recommendations_task, result={result}]")
    return result


@shared_task(
    soft_time_limit=300,
    time_limit=360,
)
def compute_personalized_recommendations_task() -> dict:
    """
    Nightly recompute of personalized recommendation scores for recently active users.

    Delegates to RecommendationsService.compute_personalized_recommendations, which
    builds each active user's facet profile from their recent usage history and scores
    the catalog against it, writing the top matches per user to Redis. See
    apps.content.services.recommendations for the scoring design.

    Runs nightly at 2:15 (config/celery.py), just after compute_similar_recommendations
    at 2:00 -- both draw on the same catalog snapshot without racing each other. Limits
    mirror compute_similar_recommendations' convention (300s soft / 360s hard).
    """
    logger.info("Task started [task=compute_personalized_recommendations_task]")
    from apps.content.services.recommendations import compute_personalized_recommendations

    result = compute_personalized_recommendations()
    logger.info(f"Task completed [task=compute_personalized_recommendations_task, result={result}]")
    return result


@shared_task(
    soft_time_limit=300,
    time_limit=360,
)
def slice_all_recitation_tracks_task() -> dict:
    """
    Enqueue slice_recitation_track_task for every existing recitation track.

    Only track IDs are loaded (values_list) and each track is scheduled as its
    own child task; no slicing happens inside this task. Intended for manual or
    one-off invocations; no beat schedule is attached.

    Returns:
        Dictionary with the number of scheduled child tasks.
    """
    from apps.content.models import RecitationSurahTrack

    track_ids = list(RecitationSurahTrack.objects.values_list("id", flat=True))
    for track_id in track_ids:
        slice_recitation_track_task.delay(track_id)
    logger.info(f"Task completed [task=slice_all_recitation_tracks_task, scheduled={len(track_ids)}]")
    return {"scheduled_count": len(track_ids)}


@shared_task
def cleanup_abandoned_content_drafts_task(older_than_hours: int = 24) -> dict[str, int]:
    """
    Periodic task to delete abandoned per-ayah content draft versions.

    A draft is abandoned when it has not been touched (``updated_at``) for
    longer than the threshold and was never published. Active editing bumps
    ``updated_at`` via autosave, so in-progress drafts are preserved.

    Args:
        older_than_hours: Delete drafts not updated within this many hours.

    Returns:
        Dictionary with the number of drafts deleted.
    """
    logger.info(f"Task started [task=cleanup_abandoned_content_drafts_task, older_than_hours={older_than_hours}]")
    from django.utils import timezone

    from apps.content.models import AssetVersion, VersionStateChoice

    cutoff = timezone.now() - timedelta(hours=older_than_hours)
    stale = AssetVersion.objects.filter(state=VersionStateChoice.DRAFT, updated_at__lt=cutoff)
    _, deleted_by_model = stale.delete()
    # delete() returns the total incl. cascaded AssetVersionEntry rows; report the
    # number of draft versions only.
    deleted = deleted_by_model.get(AssetVersion._meta.label, 0)
    logger.info(f"Task completed [task=cleanup_abandoned_content_drafts_task, deleted={deleted}]")
    return {"deleted": deleted}
