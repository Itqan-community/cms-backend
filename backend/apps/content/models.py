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