"""
Email notification system for AccessRequest workflow
"""
import logging
from typing import Dict, Any, List
from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from django.utils import timezone

from .models import AccessRequest

logger = logging.getLogger(__name__)


class AccessRequestNotificationService:
    """
    Service for sending email notifications for AccessRequest workflow events
    """
    
    def __init__(self):
        self.from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@itqan-cms.com')
        self.admin_emails = getattr(settings, 'ADMIN_NOTIFICATION_EMAILS', [])
        self.notification_enabled = getattr(settings, 'ACCESS_REQUEST_NOTIFICATIONS_ENABLED', True)
    
    def send_request_submitted_notification(self, access_request: AccessRequest) -> bool:
        """
        Send notification when a new access request is submitted
        
        Args:
            access_request: AccessRequest instance
            
        Returns:
            True if notification sent successfully
        """
        if not self.notification_enabled:
            return True
        
        try:
            # Notify admins about new request
            subject = f"New Access Request: {access_request.distribution.resource.title}"
            
            context = {
                'access_request': access_request,
                'resource': access_request.distribution.resource,
                'distribution': access_request.distribution,
                'requester': access_request.requester,
                'admin_url': self._get_admin_url(access_request)
            }
            
            # Send to admins
            if self.admin_emails:
                self._send_email(
                    subject=subject,
                    template_name='access_request_submitted_admin',
                    context=context,
                    recipient_list=self.admin_emails
                )
            
            # Send confirmation to requester
            requester_subject = f"Access Request Submitted: {access_request.distribution.resource.title}"
            self._send_email(
                subject=requester_subject,
                template_name='access_request_submitted_user',
                context=context,
                recipient_list=[access_request.requester.email]
            )
            
            access_request.mark_notification_sent()
            logger.info(f"Sent submission notification for access request {access_request.id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send submission notification for access request {access_request.id}: {e}")
            return False
    
    def send_request_approved_notification(self, access_request: AccessRequest) -> bool:
        """
        Send notification when access request is approved
        
        Args:
            access_request: AccessRequest instance
            
        Returns:
            True if notification sent successfully
        """
        if not self.notification_enabled:
            return True
        
        try:
            subject = f"Access Request Approved: {access_request.distribution.resource.title}"
            
            context = {
                'access_request': access_request,
                'resource': access_request.distribution.resource,
                'distribution': access_request.distribution,
                'requester': access_request.requester,
                'approved_by': access_request.approved_by,
                'api_endpoint': self._get_api_endpoint(access_request),
                'expires_at': access_request.expires_at
            }
            
            # Send to requester
            self._send_email(
                subject=subject,
                template_name='access_request_approved',
                context=context,
                recipient_list=[access_request.requester.email]
            )
            
            access_request.mark_notification_sent()
            logger.info(f"Sent approval notification for access request {access_request.id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send approval notification for access request {access_request.id}: {e}")
            return False
    
    def send_request_rejected_notification(self, access_request: AccessRequest) -> bool:
        """
        Send notification when access request is rejected
        
        Args:
            access_request: AccessRequest instance
            
        Returns:
            True if notification sent successfully
        """
        if not self.notification_enabled:
            return True
        
        try:
            subject = f"Access Request Rejected: {access_request.distribution.resource.title}"
            
            context = {
                'access_request': access_request,
                'resource': access_request.distribution.resource,
                'distribution': access_request.distribution,
                'requester': access_request.requester,
                'approved_by': access_request.approved_by,
                'rejection_reason': access_request.get_rejection_reason_display(),
                'admin_notes': access_request.admin_notes
            }
            
            # Send to requester
            self._send_email(
                subject=subject,
                template_name='access_request_rejected',
                context=context,
                recipient_list=[access_request.requester.email]
            )
            
            access_request.mark_notification_sent()
            logger.info(f"Sent rejection notification for access request {access_request.id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send rejection notification for access request {access_request.id}: {e}")
            return False
    
    def send_request_revoked_notification(self, access_request: AccessRequest) -> bool:
        """
        Send notification when access request is revoked
        
        Args:
            access_request: AccessRequest instance
            
        Returns:
            True if notification sent successfully
        """
        if not self.notification_enabled:
            return True
        
        try:
            subject = f"Access Revoked: {access_request.distribution.resource.title}"
            
            context = {
                'access_request': access_request,
                'resource': access_request.distribution.resource,
                'distribution': access_request.distribution,
                'requester': access_request.requester,
                'approved_by': access_request.approved_by,
                'admin_notes': access_request.admin_notes
            }
            
            # Send to requester
            self._send_email(
                subject=subject,
                template_name='access_request_revoked',
                context=context,
                recipient_list=[access_request.requester.email]
            )
            
            access_request.mark_notification_sent()
            logger.info(f"Sent revocation notification for access request {access_request.id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send revocation notification for access request {access_request.id}: {e}")
            return False
    
    def send_request_expired_notification(self, access_request: AccessRequest) -> bool:
        """
        Send notification when access expires
        
        Args:
            access_request: AccessRequest instance
            
        Returns:
            True if notification sent successfully
        """
        if not self.notification_enabled:
            return True
        
        try:
            subject = f"Access Expired: {access_request.distribution.resource.title}"
            
            context = {
                'access_request': access_request,
                'resource': access_request.distribution.resource,
                'distribution': access_request.distribution,
                'requester': access_request.requester,
                'expired_at': access_request.expires_at
            }
            
            # Send to requester
            self._send_email(
                subject=subject,
                template_name='access_request_expired',
                context=context,
                recipient_list=[access_request.requester.email]
            )
            
            access_request.mark_notification_sent()
            logger.info(f"Sent expiration notification for access request {access_request.id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send expiration notification for access request {access_request.id}: {e}")
            return False
    
    def send_expiry_reminder_notification(self, access_request: AccessRequest, days_until_expiry: int) -> bool:
        """
        Send reminder notification before access expires
        
        Args:
            access_request: AccessRequest instance
            days_until_expiry: Number of days until expiry
            
        Returns:
            True if notification sent successfully
        """
        if not self.notification_enabled:
            return True
        
        try:
            subject = f"Access Expiring Soon: {access_request.distribution.resource.title}"
            
            context = {
                'access_request': access_request,
                'resource': access_request.distribution.resource,
                'distribution': access_request.distribution,
                'requester': access_request.requester,
                'days_until_expiry': days_until_expiry,
                'expires_at': access_request.expires_at
            }
            
            # Send to requester
            self._send_email(
                subject=subject,
                template_name='access_request_expiry_reminder',
                context=context,
                recipient_list=[access_request.requester.email]
            )
            
            logger.info(f"Sent expiry reminder for access request {access_request.id} ({days_until_expiry} days)")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send expiry reminder for access request {access_request.id}: {e}")
            return False
    
    def _send_email(self, subject: str, template_name: str, context: Dict[str, Any], recipient_list: List[str]):
        """
        Send email using Django's email system
        
        Args:
            subject: Email subject
            template_name: Template name (without extension)
            context: Template context variables
            recipient_list: List of recipient email addresses
        """
        try:
            # Render HTML template
            html_content = render_to_string(f'emails/{template_name}.html', context)
            
            # Render text template (fallback)
            try:
                text_content = render_to_string(f'emails/{template_name}.txt', context)
            except:
                # If text template doesn't exist, create a simple version
                text_content = self._html_to_text(html_content)
            
            # Create email message
            msg = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=self.from_email,
                to=recipient_list
            )
            msg.attach_alternative(html_content, "text/html")
            
            # Send email
            msg.send()
            
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            # Fallback to simple text email
            send_mail(
                subject=subject,
                message=f"Access Request Notification\n\n{context.get('access_request', 'N/A')}",
                from_email=self.from_email,
                recipient_list=recipient_list,
                fail_silently=False
            )
    
    def _html_to_text(self, html_content: str) -> str:
        """
        Convert HTML content to plain text (simple implementation)
        """
        try:
            # Remove HTML tags (basic implementation)
            import re
            text = re.sub('<[^<]+?>', '', html_content)
            # Clean up whitespace
            text = re.sub(r'\s+', ' ', text).strip()
            return text
        except:
            return "Access Request Notification - Please check your email client for full details."
    
    def _get_admin_url(self, access_request: AccessRequest) -> str:
        """Get admin URL for access request"""
        try:
            base_url = getattr(settings, 'SITE_URL', 'http://localhost:8000')
            return f"{base_url}/admin/licensing/accessrequest/{access_request.id}/change/"
        except:
            return "#"
    
    def _get_api_endpoint(self, access_request: AccessRequest) -> str:
        """Get API endpoint for distribution access"""
        try:
            base_url = getattr(settings, 'API_BASE_URL', 'http://localhost:8000/api/v1')
            return f"{base_url}/distributions/{access_request.distribution.id}/"
        except:
            return "#"
    
    def send_bulk_notifications(self, access_requests: List[AccessRequest], notification_type: str) -> Dict[str, int]:
        """
        Send bulk notifications for multiple access requests
        
        Args:
            access_requests: List of AccessRequest instances
            notification_type: Type of notification ('approved', 'rejected', etc.)
            
        Returns:
            Dictionary with success and failure counts
        """
        results = {'success': 0, 'failed': 0}
        
        for access_request in access_requests:
            try:
                if notification_type == 'approved':
                    success = self.send_request_approved_notification(access_request)
                elif notification_type == 'rejected':
                    success = self.send_request_rejected_notification(access_request)
                elif notification_type == 'revoked':
                    success = self.send_request_revoked_notification(access_request)
                elif notification_type == 'expired':
                    success = self.send_request_expired_notification(access_request)
                else:
                    success = False
                
                if success:
                    results['success'] += 1
                else:
                    results['failed'] += 1
                    
            except Exception as e:
                logger.error(f"Failed to send {notification_type} notification for request {access_request.id}: {e}")
                results['failed'] += 1
        
        return results


# Global notification service instance
notification_service = AccessRequestNotificationService()


def send_workflow_notification(access_request: AccessRequest, event_type: str) -> bool:
    """
    Convenience function to send workflow notifications
    
    Args:
        access_request: AccessRequest instance
        event_type: Type of event ('submitted', 'approved', 'rejected', 'revoked', 'expired')
        
    Returns:
        True if notification sent successfully
    """
    try:
        if event_type == 'submitted':
            return notification_service.send_request_submitted_notification(access_request)
        elif event_type == 'approved':
            return notification_service.send_request_approved_notification(access_request)
        elif event_type == 'rejected':
            return notification_service.send_request_rejected_notification(access_request)
        elif event_type == 'revoked':
            return notification_service.send_request_revoked_notification(access_request)
        elif event_type == 'expired':
            return notification_service.send_request_expired_notification(access_request)
        else:
            logger.warning(f"Unknown notification event type: {event_type}")
            return False
    except Exception as e:
        logger.error(f"Failed to send workflow notification: {e}")
        return False
