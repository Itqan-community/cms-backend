"""
Celery tasks for async analytics processing
Handles usage event tracking and analytics computations
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, TypedDict

from celery import shared_task
from django.db import transaction

from apps.core.services.email import email_service

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

            logger.info(f"Created usage event {usage_event.id} for user {user.id}")
            return True

    except Exception as exc:
        logger.error(f"Failed to create usage event: {exc}")
        raise self.retry(exc=exc, countdown=60 * (self.request.retries + 1)) from exc


def track_event_async(event_data):
    """
    Helper function to queue usage event tracking

    Args:
        event_data: Event data dictionary
    """
    try:
        # Queue the task for async processing
        create_usage_event_task.delay(event_data)
        return True
    except Exception as e:
        logger.error(f"Failed to queue usage event: {e}")
        # Fallback to synchronous creation if Celery is unavailable
        try:
            from .models import UsageEvent

            UsageEvent.objects.create(**event_data)
            return True
        except Exception as sync_e:
            logger.error(f"Failed to create usage event synchronously: {sync_e}")
            return False


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
def send_asset_update_email(asset_version_id: int) -> None:
    """
    Task to send email notifications for a new AssetVersion.
    """
    from apps.content.models import AssetAccess, AssetVersion

    try:
        asset_version = AssetVersion.objects.select_related("asset").get(pk=asset_version_id)
    except AssetVersion.DoesNotExist:
        return

    users = (
        AssetAccess.objects.filter(asset=asset_version.asset)
        .select_related("user")
        .values_list("user__email", flat=True)
        .distinct()
    )

    if not users:
        return

    subject = f"New Update for {asset_version.asset.name}"
    context = {
        "asset_name": asset_version.asset.name,
        "version": asset_version.name,
        "summary": asset_version.summary,
    }

    email_service.send_email(
        subject=subject,
        recipients=list(users),
        template="emails/asset_update.html",
        context=context,
    )
