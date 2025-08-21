"""
Celery tasks for AccessRequest workflow notifications and maintenance
"""
import logging
from celery import shared_task
from django.apps import apps
from django.utils import timezone
from datetime import timedelta

from .notifications import send_workflow_notification

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_access_request_notification(self, access_request_id: str, notification_type: str):
    """
    Send notification for access request status change
    
    Args:
        access_request_id: UUID of the access request
        notification_type: Type of notification ('submitted', 'approved', 'rejected', etc.)
    """
    try:
        AccessRequest = apps.get_model('licensing', 'AccessRequest')
        
        try:
            access_request = AccessRequest.objects.get(id=access_request_id)
        except AccessRequest.DoesNotExist:
            logger.warning(f"AccessRequest {access_request_id} not found for notification")
            return {'status': 'not_found', 'access_request_id': access_request_id}
        
        # Send notification
        success = send_workflow_notification(access_request, notification_type)
        
        if success:
            logger.info(f"Sent {notification_type} notification for access request {access_request_id}")
            return {
                'status': 'sent',
                'access_request_id': access_request_id,
                'notification_type': notification_type
            }
        else:
            logger.error(f"Failed to send {notification_type} notification for access request {access_request_id}")
            return {
                'status': 'failed',
                'access_request_id': access_request_id,
                'notification_type': notification_type
            }
        
    except Exception as exc:
        logger.error(f"Error sending notification for access request {access_request_id}: {exc}")
        
        # Retry the task
        if self.request.retries < self.max_retries:
            raise self.retry(countdown=60 * (2 ** self.request.retries))
        
        return {
            'status': 'failed',
            'access_request_id': access_request_id,
            'notification_type': notification_type,
            'error': str(exc)
        }


@shared_task
def check_expiring_access_requests():
    """
    Check for access requests that are expiring soon and send reminders
    """
    try:
        AccessRequest = apps.get_model('licensing', 'AccessRequest')
        
        # Get approved requests expiring in 7, 3, and 1 days
        now = timezone.now()
        reminder_days = [7, 3, 1]
        
        total_reminders = 0
        
        for days in reminder_days:
            expiry_date = now + timedelta(days=days)
            
            # Find requests expiring on this specific day (within 1 hour window)
            expiring_requests = AccessRequest.objects.filter(
                status='approved',
                is_active=True,
                expires_at__gte=expiry_date,
                expires_at__lt=expiry_date + timedelta(hours=1)
            )
            
            for access_request in expiring_requests:
                try:
                    from .notifications import notification_service
                    success = notification_service.send_expiry_reminder_notification(
                        access_request, days
                    )
                    
                    if success:
                        total_reminders += 1
                        logger.info(f"Sent {days}-day expiry reminder for access request {access_request.id}")
                    else:
                        logger.error(f"Failed to send {days}-day expiry reminder for access request {access_request.id}")
                        
                except Exception as e:
                    logger.error(f"Error sending expiry reminder for access request {access_request.id}: {e}")
        
        return {
            'status': 'completed',
            'reminders_sent': total_reminders
        }
        
    except Exception as e:
        logger.error(f"Error checking expiring access requests: {e}")
        return {
            'status': 'failed',
            'error': str(e)
        }


@shared_task
def mark_expired_access_requests():
    """
    Mark access requests as expired when their expiry date passes
    """
    try:
        AccessRequest = apps.get_model('licensing', 'AccessRequest')
        
        # Find approved requests that have expired
        now = timezone.now()
        expired_requests = AccessRequest.objects.filter(
            status='approved',
            is_active=True,
            expires_at__lt=now
        )
        
        expired_count = 0
        
        for access_request in expired_requests:
            try:
                access_request.mark_expired()
                expired_count += 1
                
                # Send expiration notification
                send_access_request_notification.delay(
                    access_request_id=str(access_request.id),
                    notification_type='expired'
                )
                
                logger.info(f"Marked access request {access_request.id} as expired")
                
            except Exception as e:
                logger.error(f"Error marking access request {access_request.id} as expired: {e}")
        
        return {
            'status': 'completed',
            'expired_count': expired_count
        }
        
    except Exception as e:
        logger.error(f"Error marking expired access requests: {e}")
        return {
            'status': 'failed',
            'error': str(e)
        }


@shared_task
def cleanup_old_access_requests():
    """
    Clean up old access requests (soft delete inactive ones older than 1 year)
    """
    try:
        AccessRequest = apps.get_model('licensing', 'AccessRequest')
        
        # Find inactive access requests older than 1 year
        cutoff_date = timezone.now() - timedelta(days=365)
        old_requests = AccessRequest.objects.filter(
            is_active=False,
            created_at__lt=cutoff_date
        )
        
        cleanup_count = old_requests.count()
        
        # Soft delete by marking as inactive (they're already inactive, so this is mainly for logging)
        for access_request in old_requests:
            access_request.delete()  # This will be soft delete due to BaseModel
        
        logger.info(f"Cleaned up {cleanup_count} old access requests")
        
        return {
            'status': 'completed',
            'cleanup_count': cleanup_count
        }
        
    except Exception as e:
        logger.error(f"Error cleaning up old access requests: {e}")
        return {
            'status': 'failed',
            'error': str(e)
        }


@shared_task
def send_admin_summary_report():
    """
    Send daily summary report to admins about access request activity
    """
    try:
        AccessRequest = apps.get_model('licensing', 'AccessRequest')
        
        # Get stats for the last 24 hours
        yesterday = timezone.now() - timedelta(days=1)
        
        stats = {
            'new_requests': AccessRequest.objects.filter(
                requested_at__gte=yesterday,
                is_active=True
            ).count(),
            'approved_requests': AccessRequest.objects.filter(
                reviewed_at__gte=yesterday,
                status='approved',
                is_active=True
            ).count(),
            'rejected_requests': AccessRequest.objects.filter(
                reviewed_at__gte=yesterday,
                status='rejected',
                is_active=True
            ).count(),
            'pending_requests': AccessRequest.objects.filter(
                status__in=['pending', 'under_review'],
                is_active=True
            ).count(),
        }
        
        # Only send report if there's activity
        if any(stats.values()):
            from django.core.mail import send_mail
            from django.conf import settings
            
            admin_emails = getattr(settings, 'ADMIN_NOTIFICATION_EMAILS', [])
            if admin_emails:
                subject = f"Itqan CMS Daily Access Request Summary - {timezone.now().strftime('%Y-%m-%d')}"
                message = f"""
Daily Access Request Summary

New Requests: {stats['new_requests']}
Approved: {stats['approved_requests']}
Rejected: {stats['rejected_requests']}
Pending Review: {stats['pending_requests']}

Please review pending requests in the admin panel.
                """
                
                send_mail(
                    subject=subject,
                    message=message,
                    from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@itqan-cms.com'),
                    recipient_list=admin_emails
                )
                
                logger.info("Sent daily admin summary report")
        
        return {
            'status': 'completed',
            'stats': stats
        }
        
    except Exception as e:
        logger.error(f"Error sending admin summary report: {e}")
        return {
            'status': 'failed',
            'error': str(e)
        }


@shared_task
def resend_failed_notifications():
    """
    Resend notifications for access requests where notification_sent is False
    """
    try:
        AccessRequest = apps.get_model('licensing', 'AccessRequest')
        
        # Find requests with status changes but no notification sent
        requests_needing_notification = AccessRequest.objects.filter(
            notification_sent=False,
            status__in=['approved', 'rejected', 'revoked', 'expired'],
            is_active=True
        )
        
        resent_count = 0
        
        for access_request in requests_needing_notification:
            try:
                # Determine notification type from status
                notification_type = access_request.status
                if notification_type == 'approved':
                    notification_type = 'approved'
                elif notification_type == 'rejected':
                    notification_type = 'rejected'
                elif notification_type == 'revoked':
                    notification_type = 'revoked'
                elif notification_type == 'expired':
                    notification_type = 'expired'
                
                # Send notification
                send_access_request_notification.delay(
                    access_request_id=str(access_request.id),
                    notification_type=notification_type
                )
                
                resent_count += 1
                logger.info(f"Queued retry notification for access request {access_request.id}")
                
            except Exception as e:
                logger.error(f"Error queuing retry notification for access request {access_request.id}: {e}")
        
        return {
            'status': 'completed',
            'resent_count': resent_count
        }
        
    except Exception as e:
        logger.error(f"Error resending failed notifications: {e}")
        return {
            'status': 'failed',
            'error': str(e)
        }
