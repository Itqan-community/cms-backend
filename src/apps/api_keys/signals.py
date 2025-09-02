"""
Django signals for API key management
"""
import logging
from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver
from django.core.mail import send_mail
from django.conf import settings
from .models import APIKey, RateLimitEvent

logger = logging.getLogger('itqan.api_keys')


@receiver(post_save, sender=APIKey)
def api_key_created(sender, instance, created, **kwargs):
    """
    Handle API key creation
    """
    if created:
        logger.info(
            f'API key created: {instance.name} for user {instance.user.email}'
        )
        
        # Send notification email to user (optional)
        if hasattr(settings, 'SEND_API_KEY_NOTIFICATIONS') and settings.SEND_API_KEY_NOTIFICATIONS:
            try:
                send_mail(
                    subject='New API Key Created',
                    message=f'A new API key "{instance.name}" has been created for your account.',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[instance.user.email],
                    fail_silently=True
                )
            except Exception as e:
                logger.error(f'Failed to send API key creation email: {e}')


@receiver(post_save, sender=APIKey)
def api_key_revoked(sender, instance, **kwargs):
    """
    Handle API key revocation
    """
    if instance.revoked_at and instance.tracker.has_changed('revoked_at'):
        logger.warning(
            f'API key revoked: {instance.name} for user {instance.user.email} '
            f'by {instance.revoked_by.email if instance.revoked_by else "system"}'
        )
        
        # Send notification email to user (optional)
        if hasattr(settings, 'SEND_API_KEY_NOTIFICATIONS') and settings.SEND_API_KEY_NOTIFICATIONS:
            try:
                send_mail(
                    subject='API Key Revoked',
                    message=f'Your API key "{instance.name}" has been revoked. '
                           f'Reason: {instance.revoked_reason or "Not specified"}',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[instance.user.email],
                    fail_silently=True
                )
            except Exception as e:
                logger.error(f'Failed to send API key revocation email: {e}')


@receiver(post_save, sender=RateLimitEvent)
def rate_limit_violation(sender, instance, created, **kwargs):
    """
    Handle rate limit violations
    """
    if created:
        api_key_name = instance.api_key.name if instance.api_key else 'Anonymous'
        logger.warning(
            f'Rate limit violation: {api_key_name} at {instance.endpoint} '
            f'from {instance.ip_address} ({instance.current_count}/{instance.limit_value})'
        )
        
        # If this is a repeated violation, consider additional action
        if instance.api_key:
            recent_violations = RateLimitEvent.objects.filter(
                api_key=instance.api_key,
                created_at__gte=instance.created_at.replace(hour=0, minute=0, second=0)
            ).count()
            
            # If more than 10 violations in a day, log as critical
            if recent_violations > 10:
                logger.critical(
                    f'Excessive rate limit violations: {api_key_name} has '
                    f'{recent_violations} violations today'
                )


@receiver(pre_delete, sender=APIKey)
def api_key_deleted(sender, instance, **kwargs):
    """
    Handle API key deletion
    """
    logger.info(
        f'API key deleted: {instance.name} for user {instance.user.email}'
    )
