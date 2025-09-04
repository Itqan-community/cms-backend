"""
Usage analytics and event tracking models for Itqan CMS
"""
from django.db import models
from django.conf import settings
from django.utils import timezone
from apps.core.models import BaseModel, ActiveObjectsManager, AllObjectsManager


class LegacyUsageEvent(BaseModel):
    """
    Model for tracking all resource usage events for analytics, billing, and compliance.
    High-volume table that should be partitioned by date in production.
    """
    EVENT_TYPE_CHOICES = [
        ('api_call', 'API Call'),
        ('download', 'Download'),
        ('view', 'View'),
    ]
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='legacy_usage_events',
        help_text="User who triggered the event"
    )
    
    resource = models.ForeignKey(
        'content.Resource',
        on_delete=models.CASCADE,
        related_name='legacy_usage_events',
        help_text="Resource that was accessed"
    )
    
    distribution = models.ForeignKey(
        'content.Distribution',
        on_delete=models.CASCADE,
        related_name='legacy_usage_events',
        help_text="Specific distribution that was used"
    )
    
    event_type = models.CharField(
        max_length=20,
        choices=EVENT_TYPE_CHOICES,
        help_text="Type of usage event"
    )
    
    endpoint = models.CharField(
        max_length=500,
        help_text="Specific API endpoint or URL that was accessed"
    )
    
    request_size = models.PositiveIntegerField(
        default=0,
        help_text="Size of the request in bytes"
    )
    
    response_size = models.PositiveIntegerField(
        default=0,
        help_text="Size of the response in bytes"
    )
    
    ip_address = models.GenericIPAddressField(
        help_text="IP address of the client making the request"
    )
    
    user_agent = models.TextField(
        help_text="User agent string from the client"
    )
    
    metadata = models.JSONField(
        default=dict,
        help_text="Additional event-specific metadata and tracking data"
    )
    
    occurred_at = models.DateTimeField(
        default=timezone.now,
        help_text="When the event occurred"
    )

    # Override created_at to use occurred_at as the primary timestamp
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When this record was created in the database"
    )

    # Managers
    objects = ActiveObjectsManager()
    all_objects = AllObjectsManager()

    class Meta:
        db_table = 'legacy_usage_event'
        verbose_name = 'Usage Event'
        verbose_name_plural = 'Usage Events'
        ordering = ['-occurred_at']
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['resource']),
            models.Index(fields=['distribution']),
            models.Index(fields=['event_type']),
            models.Index(fields=['occurred_at']),
            models.Index(fields=['ip_address']),
            # Composite indexes for common queries
            models.Index(fields=['user', 'occurred_at']),
            models.Index(fields=['resource', 'occurred_at']),
            models.Index(fields=['event_type', 'occurred_at']),
        ]

    def __str__(self):
        return f"{self.user.email} - {self.event_type} - {self.resource.title}"

    def get_bandwidth_total(self):
        """Get total bandwidth used (request + response)"""
        return self.request_size + self.response_size

    def get_response_time(self):
        """Get response time from metadata if available"""
        return self.metadata.get('response_time_ms')

    def get_status_code(self):
        """Get HTTP status code from metadata if available"""
        return self.metadata.get('status_code')

    def get_client_info(self):
        """Get parsed client information from user agent"""
        return {
            'ip_address': self.ip_address,
            'user_agent': self.user_agent,
            'client_info': self.metadata.get('client_info', {}),
        }

    def get_geolocation(self):
        """Get geolocation data if available in metadata"""
        return self.metadata.get('geolocation', {})

    def is_successful(self):
        """Check if the event represents a successful operation"""
        status_code = self.get_status_code()
        if status_code:
            return 200 <= status_code < 300
        
        # If no status code, assume success for non-API events
        return self.event_type in ['download', 'view']

    def is_api_call(self):
        """Check if this is an API call event"""
        return self.event_type == 'api_call'

    def is_download(self):
        """Check if this is a download event"""
        return self.event_type == 'download'

    def is_view(self):
        """Check if this is a view event"""
        return self.event_type == 'view'

    @classmethod
    def get_user_usage_stats(cls, user, start_date=None, end_date=None):
        """Get usage statistics for a specific user"""
        queryset = cls.objects.filter(user=user)
        
        if start_date:
            queryset = queryset.filter(occurred_at__gte=start_date)
        if end_date:
            queryset = queryset.filter(occurred_at__lte=end_date)
        
        return {
            'total_events': queryset.count(),
            'api_calls': queryset.filter(event_type='api_call').count(),
            'downloads': queryset.filter(event_type='download').count(),
            'views': queryset.filter(event_type='view').count(),
            'total_bandwidth': queryset.aggregate(
                total=models.Sum('request_size') + models.Sum('response_size')
            )['total'] or 0,
        }

    @classmethod
    def get_resource_usage_stats(cls, resource, start_date=None, end_date=None):
        """Get usage statistics for a specific resource"""
        queryset = cls.objects.filter(resource=resource)
        
        if start_date:
            queryset = queryset.filter(occurred_at__gte=start_date)
        if end_date:
            queryset = queryset.filter(occurred_at__lte=end_date)
        
        return {
            'total_events': queryset.count(),
            'unique_users': queryset.values('user').distinct().count(),
            'api_calls': queryset.filter(event_type='api_call').count(),
            'downloads': queryset.filter(event_type='download').count(),
            'views': queryset.filter(event_type='view').count(),
            'total_bandwidth': queryset.aggregate(
                total=models.Sum('request_size') + models.Sum('response_size')
            )['total'] or 0,
        }

    @classmethod
    def get_daily_stats(cls, start_date, end_date):
        """Get daily usage statistics for a date range"""
        from django.db.models import Count, Sum
        from django.db.models.functions import TruncDate
        
        return cls.objects.filter(
            occurred_at__date__range=[start_date, end_date]
        ).annotate(
            date=TruncDate('occurred_at')
        ).values('date').annotate(
            total_events=Count('id'),
            total_users=Count('user', distinct=True),
            total_resources=Count('resource', distinct=True),
            total_bandwidth=Sum('request_size') + Sum('response_size'),
        ).order_by('date')

    def save(self, *args, **kwargs):
        """Override save to ensure occurred_at is set"""
        if not self.occurred_at:
            self.occurred_at = timezone.now()
        super().save(*args, **kwargs)