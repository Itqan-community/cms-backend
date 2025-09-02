"""
Quranic content management models for Itqan CMS
"""
from django.db import models
from django.conf import settings
from django.core.validators import URLValidator
from apps.core.models import BaseModel, ActiveObjectsManager, AllObjectsManager


class Resource(BaseModel):
    """
    Core model representing Quranic content (text, audio, translations, tafsir).
    Published by users with Publisher role.
    """
    RESOURCE_TYPE_CHOICES = [
        ('text', 'Text'),
        ('audio', 'Audio'),
        ('translation', 'Translation'),
        ('tafsir', 'Tafsir'),
    ]
    
    title = models.CharField(
        max_length=255,
        help_text="Title of the Quranic resource"
    )
    
    description = models.TextField(
        help_text="Detailed description of the resource content"
    )
    
    resource_type = models.CharField(
        max_length=20,
        choices=RESOURCE_TYPE_CHOICES,
        help_text="Type of Quranic content"
    )
    
    language = models.CharField(
        max_length=10,
        help_text="Language code (en, ar, ur, etc.)"
    )
    
    version = models.CharField(
        max_length=50,
        help_text="Version identifier (e.g., 1.0, 2.1, etc.)"
    )
    
    checksum = models.CharField(
        max_length=64,
        help_text="SHA-256 checksum for content integrity verification"
    )
    
    publisher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='published_resources',
        help_text="User who published this resource (must have Publisher role)"
    )
    
    metadata = models.JSONField(
        default=dict,
        help_text="Additional resource-specific metadata (duration, reciter, etc.)"
    )
    
    published_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when the resource was published"
    )
    
    # Workflow fields
    WORKFLOW_STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('in_review', 'In Review'),
        ('reviewed', 'Reviewed'),
        ('published', 'Published'),
        ('rejected', 'Rejected'),
    ]
    
    workflow_status = models.CharField(
        max_length=20,
        choices=WORKFLOW_STATUS_CHOICES,
        default='draft',
        help_text="Current workflow status of the resource"
    )
    
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_resources',
        help_text="User who reviewed this resource (must have Reviewer role)"
    )
    
    reviewed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when the resource was reviewed"
    )
    
    review_notes = models.TextField(
        blank=True,
        help_text="Notes from the reviewer about the resource"
    )
    
    submitted_for_review_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when resource was submitted for review"
    )

    # Managers
    objects = ActiveObjectsManager()
    all_objects = AllObjectsManager()

    class Meta:
        db_table = 'resource'
        verbose_name = 'Resource'
        verbose_name_plural = 'Resources'
        ordering = ['-published_at', '-created_at']
        indexes = [
            models.Index(fields=['resource_type']),
            models.Index(fields=['language']),
            models.Index(fields=['publisher']),
            models.Index(fields=['published_at']),
            models.Index(fields=['workflow_status']),
            models.Index(fields=['reviewed_by']),
            models.Index(fields=['submitted_for_review_at']),
        ]

    def __str__(self):
        return f"{self.title} ({self.resource_type}, {self.language})"

    def get_language_display(self):
        """Get human-readable language name"""
        language_map = {
            'ar': 'Arabic',
            'en': 'English',
            'ur': 'Urdu',
            'tr': 'Turkish',
            'id': 'Indonesian',
            'ms': 'Malay',
            'fr': 'French',
            'de': 'German',
            'es': 'Spanish',
        }
        return language_map.get(self.language, self.language.upper())

    def is_published(self):
        """Check if resource is published"""
        return self.published_at is not None

    def get_file_count(self):
        """Get number of associated media files"""
        return self.media_files.filter(is_active=True).count()

    def get_total_file_size(self):
        """Get total size of all associated files in bytes"""
        return self.media_files.filter(is_active=True).aggregate(
            total_size=models.Sum('file_size')
        )['total_size'] or 0
    
    # Workflow methods
    def can_submit_for_review(self, user):
        """Check if user can submit this resource for review"""
        return (
            self.workflow_status == 'draft' and
            (self.publisher == user or user.is_admin())
        )
    
    def can_review(self, user):
        """Check if user can review this resource"""
        return (
            self.workflow_status == 'in_review' and
            (user.is_reviewer() or user.is_admin())
        )
    
    def can_publish(self, user):
        """Check if user can publish this resource"""
        return (
            self.workflow_status == 'reviewed' and
            (user.is_reviewer() or user.is_admin())
        )
    
    def submit_for_review(self, user):
        """Submit resource for review"""
        if not self.can_submit_for_review(user):
            raise ValueError("Cannot submit resource for review")
        
        from django.utils import timezone
        self.workflow_status = 'in_review'
        self.submitted_for_review_at = timezone.now()
        self.save()
        
        # Send notification to reviewers
        self._send_workflow_notification('submitted_for_review')
    
    def approve_review(self, user, notes=''):
        """Approve resource review"""
        if not self.can_review(user):
            raise ValueError("Cannot approve resource")
        
        from django.utils import timezone
        self.workflow_status = 'reviewed'
        self.reviewed_by = user
        self.reviewed_at = timezone.now()
        self.review_notes = notes
        self.save()
        
        # Send notification to publisher
        self._send_workflow_notification('approved')
    
    def reject_review(self, user, notes=''):
        """Reject resource review"""
        if not self.can_review(user):
            raise ValueError("Cannot reject resource")
        
        from django.utils import timezone
        self.workflow_status = 'rejected'
        self.reviewed_by = user
        self.reviewed_at = timezone.now()
        self.review_notes = notes
        self.save()
        
        # Send notification to publisher
        self._send_workflow_notification('rejected')
    
    def publish_resource(self, user):
        """Publish the resource"""
        if not self.can_publish(user):
            raise ValueError("Cannot publish resource")
        
        from django.utils import timezone
        self.workflow_status = 'published'
        self.published_at = timezone.now()
        self.save()
        
        # Send notification to publisher and team
        self._send_workflow_notification('published')
    
    def reset_to_draft(self, user):
        """Reset resource to draft status"""
        if not (self.publisher == user or user.is_admin()):
            raise ValueError("Cannot reset resource to draft")
        
        self.workflow_status = 'draft'
        self.reviewed_by = None
        self.reviewed_at = None
        self.review_notes = ''
        self.submitted_for_review_at = None
        self.published_at = None
        self.save()
        
        # Send notification
        self._send_workflow_notification('reset_to_draft')
    
    def _send_workflow_notification(self, action):
        """Send workflow notification via Celery"""
        try:
            from apps.licensing.tasks import send_workflow_notification
            send_workflow_notification.delay(
                resource_id=str(self.id),
                action=action,
                resource_title=self.title,
                publisher_email=self.publisher.email
            )
        except ImportError:
            # Handle case where Celery task doesn't exist yet
            pass
    
    def get_workflow_status_display_color(self):
        """Get color for workflow status display"""
        color_map = {
            'draft': 'default',
            'in_review': 'processing',
            'reviewed': 'success',
            'published': 'green',
            'rejected': 'error',
        }
        return color_map.get(self.workflow_status, 'default')
    
    def get_workflow_history(self):
        """Get workflow transition history"""
        history = []
        
        if self.created_at:
            history.append({
                'status': 'draft',
                'timestamp': self.created_at,
                'user': self.publisher,
                'notes': 'Resource created'
            })
        
        if self.submitted_for_review_at:
            history.append({
                'status': 'in_review',
                'timestamp': self.submitted_for_review_at,
                'user': self.publisher,
                'notes': 'Submitted for review'
            })
        
        if self.reviewed_at:
            history.append({
                'status': self.workflow_status,
                'timestamp': self.reviewed_at,
                'user': self.reviewed_by,
                'notes': self.review_notes or f'Resource {self.workflow_status}'
            })
        
        if self.published_at:
            history.append({
                'status': 'published',
                'timestamp': self.published_at,
                'user': self.reviewed_by or self.publisher,
                'notes': 'Resource published'
            })
        
        return sorted(history, key=lambda x: x['timestamp'])


class Distribution(BaseModel):
    """
    Delivery format/endpoint for accessing a Resource.
    Defines how developers can access the content.
    """
    FORMAT_TYPE_CHOICES = [
        ('REST_JSON', 'REST API (JSON)'),
        ('GraphQL', 'GraphQL API'),
        ('ZIP', 'ZIP Download'),
        ('API', 'Custom API'),
    ]
    
    resource = models.ForeignKey(
        Resource,
        on_delete=models.CASCADE,
        related_name='distributions',
        help_text="Resource that this distribution provides access to"
    )
    
    format_type = models.CharField(
        max_length=20,
        choices=FORMAT_TYPE_CHOICES,
        help_text="Format/method for accessing the resource"
    )
    
    endpoint_url = models.URLField(
        validators=[URLValidator()],
        help_text="API endpoint or download URL for accessing content"
    )
    
    version = models.CharField(
        max_length=50,
        help_text="Distribution version identifier"
    )
    
    access_config = models.JSONField(
        default=dict,
        help_text="Access configuration (API keys, rate limits, authentication)"
    )
    
    metadata = models.JSONField(
        default=dict,
        help_text="Format-specific metadata and configuration"
    )

    # Managers
    objects = ActiveObjectsManager()
    all_objects = AllObjectsManager()

    class Meta:
        db_table = 'distribution'
        verbose_name = 'Distribution'
        verbose_name_plural = 'Distributions'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['resource']),
            models.Index(fields=['format_type']),
        ]
        unique_together = [['resource', 'format_type', 'version']]

    def __str__(self):
        return f"{self.resource.title} - {self.format_type} v{self.version}"

    def get_access_method(self):
        """Get human-readable access method"""
        return dict(self.FORMAT_TYPE_CHOICES).get(self.format_type, self.format_type)

    def is_api_endpoint(self):
        """Check if this is an API endpoint (vs download)"""
        return self.format_type in ['REST_JSON', 'GraphQL', 'API']

    def is_download(self):
        """Check if this is a downloadable resource"""
        return self.format_type == 'ZIP'

    def get_rate_limit(self):
        """Get rate limit from access config"""
        return self.access_config.get('rate_limit', {})

    def requires_api_key(self):
        """Check if API key is required"""
        return self.access_config.get('requires_api_key', False)