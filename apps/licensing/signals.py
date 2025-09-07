"""
Django signals for AccessRequest workflow notifications
"""

import logging

from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import AccessRequest

logger = logging.getLogger(__name__)


@receiver(post_save, sender=AccessRequest)
def access_request_post_save(sender, instance, created, **kwargs):
    """
    Send notifications when AccessRequest status changes
    """
    try:
        # Skip notifications if disabled
        if getattr(settings, "ACCESS_REQUEST_NOTIFICATIONS_ENABLED", True) is False:
            return

        # Skip notifications if notification already sent for this status
        if instance.notification_sent:
            return

        # Skip notifications if Celery is in eager mode (for testing)
        if getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False):
            logger.debug(
                f"Skipping notification for access request {instance.id} (Celery eager mode)",
            )
            return

        # Determine notification type based on status
        notification_type = None

        if created and instance.status == "pending":
            notification_type = "submitted"
        elif instance.status == "approved":
            notification_type = "approved"
        elif instance.status == "rejected":
            notification_type = "rejected"
        elif instance.status == "revoked":
            notification_type = "revoked"
        elif instance.status == "expired":
            notification_type = "expired"

        # Send notification asynchronously if notification type determined
        if notification_type:
            # Import here to avoid circular imports
            from .tasks import send_access_request_notification

            send_access_request_notification.delay(
                access_request_id=str(instance.id),
                notification_type=notification_type,
            )

            logger.info(
                f"Queued {notification_type} notification for access request {instance.id}",
            )

    except Exception as e:
        logger.error(
            f"Failed to queue notification for access request {instance.id}: {e}",
        )


def connect_signals():
    """
    Function to manually connect signals if needed
    """
    logger.info("AccessRequest notification signals connected")


def disconnect_signals():
    """
    Function to disconnect signals for testing
    """
    post_save.disconnect(access_request_post_save, sender=AccessRequest)
    logger.info("AccessRequest notification signals disconnected")
