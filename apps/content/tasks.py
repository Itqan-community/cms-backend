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
    subject_kind: UsageEvent.SubjectKindChoice
    asset_id: int | None
    resource_id: int | None
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
            - subject_kind: What was accessed (asset, resource, publisher)
            - asset_id: Asset ID (optional)
            - resource_id: Resource ID (optional)
            - metadata: Additional event metadata
            - ip_address: Client IP address
            - user_agent: Client user agent
    """
    try:
        from .models import Asset, Resource, UsageEvent

        # Validate required fields
        required_fields = ["developer_user_id", "usage_kind", "subject_kind"]
        for field in required_fields:
            if field not in event_data:
                logger.error(f"Missing required field '{field}' in usage event data")
                return False

        # Get user
        from apps.users.models import User

        try:
            user = User.objects.get(id=event_data["developer_user_id"])
        except User.DoesNotExist:
            logger.error(f"User {event_data['developer_user_id']} not found for usage event")
            return False

        # Validate subject references
        asset_id = event_data.get("asset_id")
        resource_id = event_data.get("resource_id")

        if event_data["subject_kind"] == "asset" and asset_id:
            try:
                Asset.objects.get(id=asset_id)
            except Asset.DoesNotExist:
                logger.error(f"Asset {asset_id} not found for usage event")
                return False
        elif event_data["subject_kind"] == "resource" and resource_id:
            try:
                Resource.objects.get(id=resource_id)
            except Resource.DoesNotExist:
                logger.error(f"Resource {resource_id} not found for usage event")
                return False

        # Create usage event
        with transaction.atomic():
            usage_event = UsageEvent.objects.create(
                developer_user=user,
                usage_kind=event_data["usage_kind"],
                subject_kind=event_data["subject_kind"],
                asset_id=asset_id,
                resource_id=resource_id,
                metadata=event_data.get("metadata", {}),
                ip_address=event_data.get("ip_address"),
                user_agent=event_data.get("user_agent", ""),
                effective_license=event_data.get("effective_license", ""),
            )

            logger.info(f"Created usage event {usage_event.id} for user {user.id}")
            return True

    except Exception as exc:
        logger.error(f"Failed to create usage event: {exc}")
        # Retry the task with explicit exception chaining
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
def send_resource_update_email(resource_version_id: int) -> None:
    """
    Task to send email notifications for a new ResourceVersion.
    """
    from apps.content.models import AssetAccess, ResourceVersion

    try:
        resource_version = ResourceVersion.objects.select_related("resource").get(pk=resource_version_id)
    except ResourceVersion.DoesNotExist:
        return

    # Find users with active access to any asset of this resource
    users = (
        AssetAccess.objects.filter(asset__resource=resource_version.resource)
        .select_related("user")
        .values_list("user__email", flat=True)
        .distinct()
    )

    if not users:
        return

    subject = f"New Update for {resource_version.resource.name}"
    context = {
        "resource_name": resource_version.resource.name,
        "version": resource_version.semvar,
        "summary": resource_version.summary,
    }

    email_service.send_email(
        subject=subject,
        recipients=list(users),
        template="emails/resource_update.html",
        context=context,
    )


@shared_task
def send_asset_update_email(asset_version_id: int) -> None:
    """
    Task to send email notifications for a new AssetVersion.
    """
    from apps.content.models import AssetAccess, AssetVersion

    try:
        asset_version = AssetVersion.objects.select_related("asset", "resource_version").get(pk=asset_version_id)
    except AssetVersion.DoesNotExist:
        return

    # Find users with active access to this asset
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
        "version": asset_version.resource_version.semvar,
        "summary": asset_version.summary,
    }

    email_service.send_email(
        subject=subject,
        recipients=list(users),
        template="emails/asset_update.html",
        context=context,
    )
