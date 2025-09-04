"""
License and access management models for Itqan CMS
"""
from django.db import models
from django.conf import settings
from django.utils import timezone
from apps.core.models import BaseModel, ActiveObjectsManager, AllObjectsManager


class LegacyLicense(BaseModel):
    """
    License model defining legal terms and conditions for resource usage.
    Each resource can have multiple licenses for different use cases.
    """
    LICENSE_TYPE_CHOICES = [
        ('open', 'Open License'),
        ('restricted', 'Restricted License'),
        ('commercial', 'Commercial License'),
    ]
    
    resource = models.ForeignKey(
        'content.Resource',
        on_delete=models.CASCADE,
        related_name='licenses',
        help_text="Resource that this license applies to"
    )
    
    license_type = models.CharField(
        max_length=20,
        choices=LICENSE_TYPE_CHOICES,
        help_text="Type of license (open, restricted, commercial)"
    )
    
    terms = models.TextField(
        help_text="Legal terms and conditions for using the resource"
    )
    
    geographic_restrictions = models.JSONField(
        default=dict,
        help_text="Geographic restrictions (allowed/restricted countries/regions)"
    )
    
    usage_restrictions = models.JSONField(
        default=dict,
        help_text="Usage restrictions (rate limits, attribution requirements, etc.)"
    )
    
    requires_approval = models.BooleanField(
        default=True,
        help_text="Whether admin approval is required for access requests"
    )
    
    effective_from = models.DateTimeField(
        default=timezone.now,
        help_text="When this license becomes effective"
    )
    
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this license expires (null = never expires)"
    )

    # Managers
    objects = ActiveObjectsManager()
    all_objects = AllObjectsManager()

    class Meta:
        db_table = 'legacy_license'
        verbose_name = 'License'
        verbose_name_plural = 'Licenses'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['resource']),
            models.Index(fields=['license_type']),
            models.Index(fields=['requires_approval']),
            models.Index(fields=['effective_from']),
            models.Index(fields=['expires_at']),
        ]

    def __str__(self):
        return f"{self.resource.title} - {self.get_license_type_display()}"

    def is_effective(self):
        """Check if license is currently effective"""
        now = timezone.now()
        return (
            self.effective_from <= now and
            (self.expires_at is None or self.expires_at > now)
        )

    def is_expired(self):
        """Check if license has expired"""
        return self.expires_at and self.expires_at <= timezone.now()

    def days_until_expiry(self):
        """Get number of days until license expires"""
        if not self.expires_at:
            return None
        delta = self.expires_at - timezone.now()
        return delta.days if delta.days > 0 else 0

    def get_allowed_countries(self):
        """Get list of allowed countries"""
        return self.geographic_restrictions.get('allowed_countries', [])

    def get_restricted_countries(self):
        """Get list of restricted countries"""
        return self.geographic_restrictions.get('restricted_countries', [])

    def is_country_allowed(self, country_code):
        """Check if a specific country is allowed"""
        allowed = self.get_allowed_countries()
        restricted = self.get_restricted_countries()
        
        # If there's an allowed list, country must be in it
        if allowed:
            return country_code in allowed
        
        # If there's a restricted list, country must not be in it
        if restricted:
            return country_code not in restricted
        
        # No restrictions = all countries allowed
        return True

    def get_rate_limits(self):
        """Get rate limit configuration"""
        return self.usage_restrictions.get('rate_limits', {})

    def requires_attribution(self):
        """Check if attribution is required"""
        return self.usage_restrictions.get('requires_attribution', False)

    def get_attribution_text(self):
        """Get required attribution text"""
        return self.usage_restrictions.get('attribution_text', '')


class AccessRequest(BaseModel):
    """
    Model for tracking developer requests to access specific distributions.
    Implements the approval workflow for controlled content access.
    """
    STATUS_CHOICES = [
        ('pending', 'Pending Review'),
        ('under_review', 'Under Review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('expired', 'Expired'),
        ('revoked', 'Revoked'),
    ]
    
    PRIORITY_CHOICES = [
        ('low', 'Low Priority'),
        ('normal', 'Normal Priority'),
        ('high', 'High Priority'),
        ('urgent', 'Urgent'),
    ]
    
    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='access_requests',
        help_text="Developer requesting access (must have Developer role)"
    )
    
    distribution = models.ForeignKey(
        'content.Distribution',
        on_delete=models.CASCADE,
        related_name='access_requests',
        help_text="Distribution being requested"
    )
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        help_text="Current status of the access request"
    )
    
    justification = models.TextField(
        help_text="Developer's use case description and justification"
    )
    
    priority = models.CharField(
        max_length=10,
        choices=PRIORITY_CHOICES,
        default='normal',
        help_text="Request priority level"
    )
    
    admin_notes = models.TextField(
        blank=True,
        help_text="Admin review notes and feedback"
    )
    
    rejection_reason = models.CharField(
        max_length=100,
        blank=True,
        choices=[
            ('insufficient_justification', 'Insufficient Justification'),
            ('license_violation', 'License Terms Violation'),
            ('incomplete_information', 'Incomplete Information'),
            ('policy_violation', 'Policy Violation'),
            ('resource_unavailable', 'Resource Unavailable'),
            ('other', 'Other'),
        ],
        help_text="Reason for rejection if applicable"
    )
    
    notification_sent = models.BooleanField(
        default=False,
        help_text="Whether notification email has been sent for status change"
    )
    
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_access_requests',
        help_text="Admin user who approved/rejected the request"
    )
    
    requested_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When the request was submitted"
    )
    
    reviewed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the request was reviewed by admin"
    )
    
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the approved access expires"
    )

    # Managers
    objects = ActiveObjectsManager()
    all_objects = AllObjectsManager()

    class Meta:
        db_table = 'access_request'
        verbose_name = 'Access Request'
        verbose_name_plural = 'Access Requests'
        ordering = ['-requested_at']
        indexes = [
            models.Index(fields=['requester']),
            models.Index(fields=['distribution']),
            models.Index(fields=['status']),
            models.Index(fields=['priority']),
            models.Index(fields=['requested_at']),
            models.Index(fields=['reviewed_at']),
            models.Index(fields=['notification_sent']),
            models.Index(fields=['status', 'requested_at']),
            models.Index(fields=['priority', 'requested_at']),
        ]
        unique_together = [['requester', 'distribution']]

    def __str__(self):
        return f"{self.requester.email} -> {self.distribution} ({self.status})"

    def is_pending(self):
        """Check if request is pending review"""
        return self.status == 'pending'

    def is_approved(self):
        """Check if request is approved"""
        return self.status == 'approved'

    def is_rejected(self):
        """Check if request is rejected"""
        return self.status == 'rejected'

    def is_under_review(self):
        """Check if request is under review"""
        return self.status == 'under_review'

    def is_expired(self):
        """Check if approved access has expired"""
        return (
            self.is_approved() and 
            self.expires_at and 
            self.expires_at <= timezone.now()
        )

    def is_revoked(self):
        """Check if access has been revoked"""
        return self.status == 'revoked'

    def can_be_reviewed(self):
        """Check if request can be reviewed (is in reviewable state)"""
        return self.status in ['pending', 'under_review']

    def can_be_revoked(self):
        """Check if approved access can be revoked"""
        return self.status == 'approved'

    def is_access_valid(self):
        """Check if access is currently valid (approved and not expired)"""
        return self.is_approved() and not self.is_expired()

    def start_review(self, admin_user, admin_notes=''):
        """Mark request as under review"""
        if not self.can_be_reviewed():
            raise ValueError(f"Cannot start review for request in {self.status} status")
        
        self.status = 'under_review'
        self.approved_by = admin_user
        self.reviewed_at = timezone.now()
        if admin_notes:
            self.admin_notes = admin_notes
        self.notification_sent = False
        self.save()

    def approve(self, admin_user, expires_at=None, admin_notes=''):
        """Approve the access request"""
        if not self.can_be_reviewed():
            raise ValueError(f"Cannot approve request in {self.status} status")
        
        self.status = 'approved'
        self.approved_by = admin_user
        self.reviewed_at = timezone.now()
        self.expires_at = expires_at
        if admin_notes:
            self.admin_notes = admin_notes
        self.notification_sent = False
        self.save()

    def reject(self, admin_user, rejection_reason='', admin_notes=''):
        """Reject the access request"""
        if not self.can_be_reviewed():
            raise ValueError(f"Cannot reject request in {self.status} status")
        
        self.status = 'rejected'
        self.approved_by = admin_user
        self.reviewed_at = timezone.now()
        if rejection_reason:
            self.rejection_reason = rejection_reason
        if admin_notes:
            self.admin_notes = admin_notes
        self.notification_sent = False
        self.save()

    def revoke(self, admin_user, admin_notes=''):
        """Revoke approved access"""
        if not self.can_be_revoked():
            raise ValueError(f"Cannot revoke request in {self.status} status")
        
        self.status = 'revoked'
        self.approved_by = admin_user
        self.reviewed_at = timezone.now()
        if admin_notes:
            self.admin_notes = admin_notes
        self.notification_sent = False
        self.save()

    def mark_expired(self):
        """Mark access as expired (called by background task)"""
        if self.is_approved() and self.is_expired():
            self.status = 'expired'
            self.notification_sent = False
            self.save()

    def mark_notification_sent(self):
        """Mark that notification email has been sent"""
        self.notification_sent = True
        self.save(update_fields=['notification_sent'])

    def days_until_expiry(self):
        """Get number of days until access expires"""
        if not self.expires_at:
            return None
        delta = self.expires_at - timezone.now()
        return delta.days if delta.days > 0 else 0

    def get_resource(self):
        """Get the resource associated with this request"""
        return self.distribution.resource

    def get_license(self):
        """Get the active license for the resource"""
        return self.get_resource().licenses.filter(
            is_active=True,
            effective_from__lte=timezone.now()
        ).filter(
            models.Q(expires_at__isnull=True) | 
            models.Q(expires_at__gt=timezone.now())
        ).first()