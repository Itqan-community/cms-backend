"""
Serializers for UsageEvent model and analytics data
"""
from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import UsageEvent

User = get_user_model()


class UsageEventSerializer(serializers.ModelSerializer):
    """
    Serializer for UsageEvent model with comprehensive tracking information
    """
    user_email = serializers.CharField(source='user.email', read_only=True)
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    resource_title = serializers.CharField(source='resource.title', read_only=True)
    resource_type = serializers.CharField(source='resource.resource_type', read_only=True)
    distribution_format = serializers.CharField(source='distribution.format_type', read_only=True)
    event_type_display = serializers.CharField(source='get_event_type_display', read_only=True)
    bandwidth_total = serializers.SerializerMethodField()
    is_successful = serializers.SerializerMethodField()
    response_time = serializers.SerializerMethodField()
    status_code = serializers.SerializerMethodField()
    client_info = serializers.SerializerMethodField()
    
    class Meta:
        model = UsageEvent
        fields = [
            'id', 'user', 'user_email', 'user_name',
            'resource', 'resource_title', 'resource_type',
            'distribution', 'distribution_format',
            'event_type', 'event_type_display', 'endpoint',
            'request_size', 'response_size', 'bandwidth_total',
            'ip_address', 'user_agent', 'client_info',
            'is_successful', 'response_time', 'status_code',
            'metadata', 'occurred_at', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'user_email', 'user_name', 'resource_title', 'resource_type',
            'distribution_format', 'event_type_display', 'bandwidth_total',
            'is_successful', 'response_time', 'status_code', 'client_info',
            'created_at', 'updated_at'
        ]
    
    def get_bandwidth_total(self, obj):
        """Get total bandwidth used"""
        return obj.get_bandwidth_total()
    
    def get_is_successful(self, obj):
        """Check if event was successful"""
        return obj.is_successful()
    
    def get_response_time(self, obj):
        """Get response time from metadata"""
        return obj.get_response_time()
    
    def get_status_code(self, obj):
        """Get HTTP status code from metadata"""
        return obj.get_status_code()
    
    def get_client_info(self, obj):
        """Get client information"""
        return obj.get_client_info()
    
    def validate_event_type(self, value):
        """Validate event type"""
        valid_types = ['api_call', 'download', 'view']
        if value not in valid_types:
            raise serializers.ValidationError(
                f"Event type must be one of: {', '.join(valid_types)}"
            )
        return value
    
    def validate_request_size(self, value):
        """Validate request size is non-negative"""
        if value < 0:
            raise serializers.ValidationError("Request size cannot be negative")
        return value
    
    def validate_response_size(self, value):
        """Validate response size is non-negative"""
        if value < 0:
            raise serializers.ValidationError("Response size cannot be negative")
        return value
    
    def validate_metadata(self, value):
        """Validate metadata structure"""
        if value and not isinstance(value, dict):
            raise serializers.ValidationError("Metadata must be a JSON object")
        return value or {}
    
    def create(self, validated_data):
        """Create usage event with auto-set user"""
        # Auto-set user to current user if not provided
        if 'user' not in validated_data:
            validated_data['user'] = self.context['request'].user
        
        return super().create(validated_data)


class UsageEventListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for usage event listings
    """
    user_email = serializers.CharField(source='user.email', read_only=True)
    resource_title = serializers.CharField(source='resource.title', read_only=True)
    event_type_display = serializers.CharField(source='get_event_type_display', read_only=True)
    bandwidth_total = serializers.SerializerMethodField()
    is_successful = serializers.SerializerMethodField()
    
    class Meta:
        model = UsageEvent
        fields = [
            'id', 'user_email', 'resource_title', 'event_type', 'event_type_display',
            'endpoint', 'bandwidth_total', 'is_successful', 'occurred_at'
        ]
    
    def get_bandwidth_total(self, obj):
        return obj.get_bandwidth_total()
    
    def get_is_successful(self, obj):
        return obj.is_successful()


class UsageStatsSerializer(serializers.Serializer):
    """
    Serializer for usage statistics data
    """
    total_events = serializers.IntegerField()
    api_calls = serializers.IntegerField()
    downloads = serializers.IntegerField()
    views = serializers.IntegerField()
    total_bandwidth = serializers.IntegerField()
    unique_users = serializers.IntegerField(required=False)
    
    # Optional time-based fields
    period_start = serializers.DateTimeField(required=False)
    period_end = serializers.DateTimeField(required=False)


class DailyUsageStatsSerializer(serializers.Serializer):
    """
    Serializer for daily usage statistics
    """
    date = serializers.DateField()
    total_events = serializers.IntegerField()
    total_users = serializers.IntegerField()
    total_resources = serializers.IntegerField()
    total_bandwidth = serializers.IntegerField()


class ResourceUsageStatsSerializer(serializers.Serializer):
    """
    Serializer for resource-specific usage statistics
    """
    resource_id = serializers.UUIDField()
    resource_title = serializers.CharField()
    resource_type = serializers.CharField()
    total_events = serializers.IntegerField()
    unique_users = serializers.IntegerField()
    api_calls = serializers.IntegerField()
    downloads = serializers.IntegerField()
    views = serializers.IntegerField()
    total_bandwidth = serializers.IntegerField()
    
    # Most active users for this resource
    top_users = serializers.ListField(
        child=serializers.DictField(),
        required=False
    )


class UserUsageStatsSerializer(serializers.Serializer):
    """
    Serializer for user-specific usage statistics
    """
    user_id = serializers.UUIDField()
    user_email = serializers.CharField()
    user_name = serializers.CharField()
    total_events = serializers.IntegerField()
    api_calls = serializers.IntegerField()
    downloads = serializers.IntegerField()
    views = serializers.IntegerField()
    total_bandwidth = serializers.IntegerField()
    
    # Most accessed resources by this user
    top_resources = serializers.ListField(
        child=serializers.DictField(),
        required=False
    )


class AnalyticsSummarySerializer(serializers.Serializer):
    """
    Serializer for comprehensive analytics summary
    """
    overview = UsageStatsSerializer()
    daily_stats = DailyUsageStatsSerializer(many=True)
    top_resources = ResourceUsageStatsSerializer(many=True)
    top_users = UserUsageStatsSerializer(many=True)
    
    # Event type breakdown
    event_type_breakdown = serializers.DictField()
    
    # Growth metrics
    growth_metrics = serializers.DictField(required=False)


class BandwidthUsageSerializer(serializers.Serializer):
    """
    Serializer for bandwidth usage statistics
    """
    total_bandwidth = serializers.IntegerField()
    request_bandwidth = serializers.IntegerField()
    response_bandwidth = serializers.IntegerField()
    average_request_size = serializers.FloatField()
    average_response_size = serializers.FloatField()
    
    # Bandwidth by event type
    api_call_bandwidth = serializers.IntegerField()
    download_bandwidth = serializers.IntegerField()
    view_bandwidth = serializers.IntegerField()


class ErrorStatsSerializer(serializers.Serializer):
    """
    Serializer for error statistics
    """
    total_errors = serializers.IntegerField()
    error_rate = serializers.FloatField()
    
    # Error breakdown by status code
    status_code_breakdown = serializers.DictField()
    
    # Most common error endpoints
    error_endpoints = serializers.ListField(
        child=serializers.DictField()
    )


class PerformanceStatsSerializer(serializers.Serializer):
    """
    Serializer for performance statistics
    """
    average_response_time = serializers.FloatField()
    median_response_time = serializers.FloatField()
    p95_response_time = serializers.FloatField()
    p99_response_time = serializers.FloatField()
    
    # Performance by endpoint
    endpoint_performance = serializers.ListField(
        child=serializers.DictField(),
        required=False
    )
