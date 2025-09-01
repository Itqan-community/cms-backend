"""
API Key Management models for Itqan CMS
"""
import uuid
import secrets
import hashlib
from django.db import models
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from apps.core.models import BaseModel


class APIKey(BaseModel):
    """
    Model for managing API keys for developers
    """
    # Key identification
    name = models.CharField(
        max_length=255,
        help_text="Human-readable name for this API key"
    )
    
    key_prefix = models.CharField(
        max_length=10,
        help_text="Prefix of the API key for identification (e.g., 'itq_live_')"
    )
    
    key_hash = models.CharField(
        max_length=64,
        unique=True,
        help_text="SHA-256 hash of the API key"
    )
    
    # Key metadata
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='api_keys',
        help_text="Owner of this API key"
    )
    
    description = models.TextField(
        blank=True,
        help_text="Description of what this key is used for"
    )
    
    # Permissions and restrictions
    permissions = models.JSONField(
        default=dict,
        help_text="Specific permissions for this API key"
    )
    
    allowed_ips = models.JSONField(
        default=list,
        blank=True,
        help_text="List of IP addresses/ranges allowed to use this key"
    )
    
    rate_limit = models.PositiveIntegerField(
        default=1000,
        help_text="Requests per hour allowed for this key"
    )
    
    # Usage tracking
    total_requests = models.PositiveIntegerField(
        default=0,
        help_text="Total number of requests made with this key"
    )
    
    last_used_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last time this key was used"
    )
    
    last_used_ip = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="IP address of the last request"
    )
    
    # Key lifecycle
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this key expires (null = never expires)"
    )
    
    revoked_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this key was revoked"
    )
    
    revoked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='revoked_api_keys',
        help_text="User who revoked this key"
    )
    
    revoked_reason = models.TextField(
        blank=True,
        help_text="Reason for revoking this key"
    )

    class Meta:
        db_table = 'api_key'
        verbose_name = 'API Key'
        verbose_name_plural = 'API Keys'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.key_prefix}***)"

    @classmethod
    def generate_key(cls, user, name, description="", expires_in_days=None, rate_limit=1000):
        """
        Generate a new API key
        """
        # Generate secure random key
        key_secret = secrets.token_urlsafe(32)
        key_prefix = "itq_" + ("test_" if settings.DEBUG else "live_")
        full_key = key_prefix + key_secret
        
        # Create hash for storage
        key_hash = hashlib.sha256(full_key.encode()).hexdigest()
        
        # Calculate expiration
        expires_at = None
        if expires_in_days:
            expires_at = timezone.now() + timedelta(days=expires_in_days)
        
        # Create API key record
        api_key = cls.objects.create(
            name=name,
            key_prefix=key_prefix[:10],
            key_hash=key_hash,
            user=user,
            description=description,
            expires_at=expires_at,
            rate_limit=rate_limit,
            permissions=cls._get_default_permissions(user)
        )
        
        # Return the API key object and the full key (only time it's available)
        return api_key, full_key

    @classmethod
    def _get_default_permissions(cls, user):
        """
        Get default permissions based on user role
        """
        if user.is_developer():
            return {
                'resources': ['read'],
                'distributions': ['read'],
                'access_requests': ['create', 'read_own'],
                'usage_events': ['read_own']
            }
        elif user.is_publisher():
            return {
                'resources': ['create', 'read', 'update'],
                'distributions': ['create', 'read', 'update'],
                'licenses': ['create', 'read', 'update']
            }
        elif user.is_admin():
            return {
                'all': ['*']  # Admin keys have full access
            }
        else:
            return {}

    @classmethod
    def authenticate(cls, key_string):
        """
        Authenticate an API key and return the associated user
        """
        if not key_string or not key_string.startswith('itq_'):
            return None, None
        
        # Hash the provided key
        key_hash = hashlib.sha256(key_string.encode()).hexdigest()
        
        try:
            # Find the API key
            api_key = cls.objects.select_related('user').get(
                key_hash=key_hash,
                is_active=True,
                revoked_at__isnull=True
            )
            
            # Check if key is expired
            if api_key.expires_at and api_key.expires_at < timezone.now():
                return None, None
            
            # Update usage stats
            api_key.total_requests += 1
            api_key.last_used_at = timezone.now()
            api_key.save(update_fields=['total_requests', 'last_used_at'])
            
            return api_key.user, api_key
            
        except cls.DoesNotExist:
            return None, None

    def revoke(self, revoked_by, reason=""):
        """
        Revoke this API key
        """
        self.revoked_at = timezone.now()
        self.revoked_by = revoked_by
        self.revoked_reason = reason
        self.is_active = False
        self.save()

    def is_expired(self):
        """
        Check if this API key is expired
        """
        if self.expires_at:
            return self.expires_at < timezone.now()
        return False

    def is_revoked(self):
        """
        Check if this API key is revoked
        """
        return self.revoked_at is not None

    def is_valid(self):
        """
        Check if this API key is valid for use
        """
        return (
            self.is_active and
            not self.is_expired() and
            not self.is_revoked()
        )

    def update_last_used(self, ip_address=None):
        """
        Update last used timestamp and IP
        """
        self.last_used_at = timezone.now()
        self.total_requests += 1
        if ip_address:
            self.last_used_ip = ip_address
        self.save(update_fields=['last_used_at', 'total_requests', 'last_used_ip'])

    def get_usage_stats(self, days=30):
        """
        Get usage statistics for this API key
        """
        from django.db.models import Count
        from django.utils import timezone
        from datetime import timedelta
        
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        # Get usage events for this key
        usage_data = APIKeyUsage.objects.filter(
            api_key=self,
            created_at__range=[start_date, end_date]
        ).extra({
            'date': 'DATE(created_at)'
        }).values('date').annotate(
            requests=Count('id')
        ).order_by('date')
        
        return list(usage_data)


class APIKeyUsage(BaseModel):
    """
    Model for tracking API key usage for analytics
    """
    api_key = models.ForeignKey(
        APIKey,
        on_delete=models.CASCADE,
        related_name='usage_logs',
        help_text="API key that was used"
    )
    
    endpoint = models.CharField(
        max_length=255,
        help_text="API endpoint that was accessed"
    )
    
    method = models.CharField(
        max_length=10,
        help_text="HTTP method used"
    )
    
    status_code = models.PositiveIntegerField(
        help_text="HTTP response status code"
    )
    
    ip_address = models.GenericIPAddressField(
        help_text="IP address of the request"
    )
    
    user_agent = models.TextField(
        blank=True,
        help_text="User agent string"
    )
    
    request_data = models.JSONField(
        default=dict,
        blank=True,
        help_text="Request parameters and metadata"
    )
    
    response_time = models.FloatField(
        null=True,
        blank=True,
        help_text="Response time in milliseconds"
    )

    class Meta:
        db_table = 'api_key_usage'
        verbose_name = 'API Key Usage'
        verbose_name_plural = 'API Key Usage'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['api_key', 'created_at']),
            models.Index(fields=['endpoint', 'created_at']),
            models.Index(fields=['status_code', 'created_at']),
        ]

    def __str__(self):
        return f"{self.api_key.name} - {self.method} {self.endpoint} ({self.status_code})"


class RateLimitEvent(BaseModel):
    """
    Model for tracking rate limit violations
    """
    api_key = models.ForeignKey(
        APIKey,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='rate_limit_events',
        help_text="API key that exceeded the rate limit (if applicable)"
    )
    
    ip_address = models.GenericIPAddressField(
        help_text="IP address that exceeded the rate limit"
    )
    
    endpoint = models.CharField(
        max_length=255,
        help_text="API endpoint that was accessed"
    )
    
    method = models.CharField(
        max_length=10,
        help_text="HTTP method used"
    )
    
    limit_type = models.CharField(
        max_length=50,
        choices=[
            ('api_key', 'API Key Rate Limit'),
            ('ip', 'IP Rate Limit'),
            ('user', 'User Rate Limit'),
            ('global', 'Global Rate Limit'),
        ],
        help_text="Type of rate limit that was exceeded"
    )
    
    current_count = models.PositiveIntegerField(
        help_text="Current request count when limit was exceeded"
    )
    
    limit_value = models.PositiveIntegerField(
        help_text="The rate limit value that was exceeded"
    )
    
    window_seconds = models.PositiveIntegerField(
        help_text="Rate limit window in seconds"
    )

    class Meta:
        db_table = 'rate_limit_event'
        verbose_name = 'Rate Limit Event'
        verbose_name_plural = 'Rate Limit Events'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['ip_address', 'created_at']),
            models.Index(fields=['api_key', 'created_at']),
            models.Index(fields=['limit_type', 'created_at']),
        ]

    def __str__(self):
        key_name = self.api_key.name if self.api_key else 'Anonymous'
        return f"{key_name} - {self.limit_type} limit exceeded at {self.endpoint}"
