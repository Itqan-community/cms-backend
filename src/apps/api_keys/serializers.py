"""
Serializers for API key management
"""
from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import APIKey, APIKeyUsage, RateLimitEvent

User = get_user_model()


class APIKeySerializer(serializers.ModelSerializer):
    """
    Main serializer for API key model
    """
    user_email = serializers.CharField(source='user.email', read_only=True)
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    is_expired = serializers.BooleanField(read_only=True)
    is_revoked = serializers.BooleanField(read_only=True)
    is_valid = serializers.BooleanField(read_only=True)
    days_until_expiry = serializers.SerializerMethodField()
    
    class Meta:
        model = APIKey
        fields = [
            'id', 'name', 'key_prefix', 'user', 'user_email', 'user_name',
            'description', 'permissions', 'allowed_ips', 'rate_limit',
            'total_requests', 'last_used_at', 'last_used_ip',
            'expires_at', 'revoked_at', 'revoked_by', 'revoked_reason',
            'is_expired', 'is_revoked', 'is_valid', 'days_until_expiry',
            'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'key_prefix', 'user_email', 'user_name', 'total_requests',
            'last_used_at', 'last_used_ip', 'revoked_at', 'revoked_by',
            'revoked_reason', 'is_expired', 'is_revoked', 'is_valid',
            'days_until_expiry', 'created_at', 'updated_at'
        ]

    def get_days_until_expiry(self, obj):
        """Calculate days until expiry"""
        if not obj.expires_at:
            return None
        
        from django.utils import timezone
        days = (obj.expires_at - timezone.now()).days
        return max(0, days)


class APIKeyCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating new API keys
    """
    expires_in_days = serializers.IntegerField(
        required=False,
        min_value=1,
        max_value=365,
        help_text="Number of days until the key expires (optional)"
    )
    
    class Meta:
        model = APIKey
        fields = [
            'name', 'description', 'rate_limit', 'allowed_ips',
            'permissions', 'expires_in_days'
        ]

    def validate_name(self, value):
        """Validate API key name is unique for the user"""
        user = self.context['request'].user
        if APIKey.objects.filter(user=user, name=value, is_active=True).exists():
            raise serializers.ValidationError(
                "You already have an active API key with this name"
            )
        return value

    def validate_rate_limit(self, value):
        """Validate rate limit based on user role"""
        user = self.context['request'].user
        
        # Set maximum rate limits based on role
        max_limits = {
            'Admin': None,  # No limit
            'Publisher': 5000,
            'Developer': 1000,
            'Reviewer': 500,
        }
        
        role_name = user.role.name if user.role else 'Developer'
        max_limit = max_limits.get(role_name, 100)
        
        if max_limit and value > max_limit:
            raise serializers.ValidationError(
                f"Rate limit cannot exceed {max_limit} requests per hour for {role_name} role"
            )
        
        return value

    def validate_allowed_ips(self, value):
        """Validate IP addresses and CIDR blocks"""
        if not value:
            return value
        
        import ipaddress
        
        for ip_entry in value:
            try:
                if '/' in ip_entry:
                    # CIDR notation
                    ipaddress.ip_network(ip_entry, strict=False)
                else:
                    # Single IP
                    ipaddress.ip_address(ip_entry)
            except ValueError:
                raise serializers.ValidationError(
                    f"Invalid IP address or CIDR block: {ip_entry}"
                )
        
        return value


class APIKeyListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for API key lists
    """
    user_email = serializers.CharField(source='user.email', read_only=True)
    is_expired = serializers.BooleanField(read_only=True)
    is_revoked = serializers.BooleanField(read_only=True)
    status = serializers.SerializerMethodField()
    
    class Meta:
        model = APIKey
        fields = [
            'id', 'name', 'key_prefix', 'user_email', 'description',
            'rate_limit', 'total_requests', 'last_used_at',
            'expires_at', 'is_expired', 'is_revoked', 'status',
            'created_at'
        ]

    def get_status(self, obj):
        """Get human-readable status"""
        if obj.is_revoked():
            return 'revoked'
        elif obj.is_expired():
            return 'expired'
        elif obj.is_valid():
            return 'active'
        else:
            return 'inactive'


class APIKeyUsageSerializer(serializers.ModelSerializer):
    """
    Serializer for API key usage logs
    """
    api_key_name = serializers.CharField(source='api_key.name', read_only=True)
    
    class Meta:
        model = APIKeyUsage
        fields = [
            'id', 'api_key', 'api_key_name', 'endpoint', 'method',
            'status_code', 'ip_address', 'user_agent', 'request_data',
            'response_time', 'created_at'
        ]


class RateLimitEventSerializer(serializers.ModelSerializer):
    """
    Serializer for rate limit events
    """
    api_key_name = serializers.CharField(source='api_key.name', read_only=True)
    
    class Meta:
        model = RateLimitEvent
        fields = [
            'id', 'api_key', 'api_key_name', 'ip_address', 'endpoint',
            'method', 'limit_type', 'current_count', 'limit_value',
            'window_seconds', 'created_at'
        ]


class APIKeyStatsSerializer(serializers.Serializer):
    """
    Serializer for API key statistics
    """
    api_key_id = serializers.UUIDField()
    total_requests = serializers.IntegerField()
    error_requests = serializers.IntegerField()
    error_rate = serializers.FloatField()
    rate_limit_violations = serializers.IntegerField()
    daily_usage = serializers.ListField(
        child=serializers.DictField()
    )
    top_endpoints = serializers.ListField(
        child=serializers.DictField()
    )
    period_days = serializers.IntegerField()


class APIKeyPermissionSerializer(serializers.Serializer):
    """
    Serializer for API key permissions
    """
    resource = serializers.CharField()
    actions = serializers.ListField(child=serializers.CharField())


class APIKeyUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for updating API key settings
    """
    class Meta:
        model = APIKey
        fields = [
            'name', 'description', 'rate_limit', 'allowed_ips', 'permissions'
        ]

    def validate_name(self, value):
        """Validate API key name is unique for the user"""
        user = self.context['request'].user
        queryset = APIKey.objects.filter(user=user, name=value, is_active=True)
        
        # Exclude current instance when updating
        if self.instance:
            queryset = queryset.exclude(id=self.instance.id)
        
        if queryset.exists():
            raise serializers.ValidationError(
                "You already have an active API key with this name"
            )
        return value

    def validate_rate_limit(self, value):
        """Validate rate limit based on user role"""
        user = self.context['request'].user
        
        # Set maximum rate limits based on role
        max_limits = {
            'Admin': None,  # No limit
            'Publisher': 5000,
            'Developer': 1000,
            'Reviewer': 500,
        }
        
        role_name = user.role.name if user.role else 'Developer'
        max_limit = max_limits.get(role_name, 100)
        
        if max_limit and value > max_limit:
            raise serializers.ValidationError(
                f"Rate limit cannot exceed {max_limit} requests per hour for {role_name} role"
            )
        
        return value


class UserAPIKeySerializer(serializers.ModelSerializer):
    """
    Serializer for user's own API keys (limited view)
    """
    status = serializers.SerializerMethodField()
    
    class Meta:
        model = APIKey
        fields = [
            'id', 'name', 'key_prefix', 'description', 'rate_limit',
            'total_requests', 'last_used_at', 'expires_at', 'status',
            'created_at'
        ]

    def get_status(self, obj):
        """Get human-readable status"""
        if obj.is_revoked():
            return 'revoked'
        elif obj.is_expired():
            return 'expired'
        elif obj.is_valid():
            return 'active'
        else:
            return 'inactive'


class GlobalStatsSerializer(serializers.Serializer):
    """
    Serializer for global API statistics
    """
    api_keys = serializers.DictField()
    usage_last_30_days = serializers.DictField()
    top_api_keys = serializers.ListField(child=serializers.DictField())
    daily_requests = serializers.ListField(child=serializers.DictField())
