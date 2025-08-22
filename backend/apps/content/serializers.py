"""
Serializers for Resource and Distribution models
"""
from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Resource, Distribution

User = get_user_model()


class ResourceSerializer(serializers.ModelSerializer):
    """
    Serializer for Resource model with publisher information
    """
    publisher_name = serializers.CharField(source='publisher.get_full_name', read_only=True)
    publisher_email = serializers.CharField(source='publisher.email', read_only=True)
    language_display = serializers.CharField(source='get_language_display', read_only=True)
    is_published = serializers.SerializerMethodField()
    distribution_count = serializers.SerializerMethodField()
    license_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Resource
        fields = [
            'id', 'title', 'title_en', 'title_ar', 'description', 'description_en', 'description_ar',
            'resource_type', 'language', 'language_display', 'version', 'checksum', 'publisher', 
            'publisher_name', 'publisher_email', 'metadata', 'is_published',
            'published_at', 'distribution_count', 'license_count',
            'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'checksum', 'publisher_name', 'publisher_email', 
            'language_display', 'is_published', 'distribution_count', 
            'license_count', 'created_at', 'updated_at'
        ]
    
    def get_is_published(self, obj):
        """Check if resource is published"""
        return obj.is_published()
    
    def get_distribution_count(self, obj):
        """Get count of active distributions"""
        return obj.distributions.filter(is_active=True).count()
    
    def get_license_count(self, obj):
        """Get count of active licenses"""
        return obj.licenses.filter(is_active=True).count()
    
    def validate_resource_type(self, value):
        """Validate resource type"""
        valid_types = ['text', 'audio', 'translation', 'tafsir']
        if value not in valid_types:
            raise serializers.ValidationError(
                f"Resource type must be one of: {', '.join(valid_types)}"
            )
        return value
    
    def validate_language(self, value):
        """Validate language code"""
        # Basic language code validation (ISO 639-1)
        valid_languages = [
            'ar', 'en', 'ur', 'tr', 'id', 'ms', 'fr', 'de', 'es', 
            'ru', 'zh', 'ja', 'ko', 'hi', 'bn', 'fa', 'sw'
        ]
        if value not in valid_languages:
            raise serializers.ValidationError(
                f"Language code '{value}' is not supported. "
                f"Valid codes: {', '.join(valid_languages)}"
            )
        return value
    
    def validate_publisher(self, value):
        """Validate publisher has Publisher role"""
        if value and not value.is_publisher():
            raise serializers.ValidationError(
                "User must have Publisher role to publish resources"
            )
        return value
    
    def validate_metadata(self, value):
        """Validate metadata structure"""
        if value and not isinstance(value, dict):
            raise serializers.ValidationError("Metadata must be a JSON object")
        return value or {}
    
    def create(self, validated_data):
        """Create resource with auto-generated checksum"""
        import hashlib
        
        # Auto-set publisher to current user if not provided
        if 'publisher' not in validated_data:
            validated_data['publisher'] = self.context['request'].user
        
        # Generate checksum based on content
        content_str = f"{validated_data['title']}{validated_data['description']}{validated_data['version']}"
        validated_data['checksum'] = hashlib.sha256(content_str.encode()).hexdigest()
        
        return super().create(validated_data)


class ResourceListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for resource listings
    """
    publisher_name = serializers.CharField(source='publisher.get_full_name', read_only=True)
    language_display = serializers.CharField(source='get_language_display', read_only=True)
    is_published = serializers.SerializerMethodField()
    
    class Meta:
        model = Resource
        fields = [
            'id', 'title', 'resource_type', 'language', 'language_display',
            'version', 'publisher_name', 'is_published', 'published_at', 
            'created_at'
        ]
    
    def get_is_published(self, obj):
        return obj.is_published()


class DistributionSerializer(serializers.ModelSerializer):
    """
    Serializer for Distribution model with resource information
    """
    resource_title = serializers.CharField(source='resource.title', read_only=True)
    resource_type = serializers.CharField(source='resource.resource_type', read_only=True)
    format_display = serializers.CharField(source='get_format_type_display', read_only=True)
    access_method = serializers.CharField(source='get_access_method', read_only=True)
    is_api_endpoint = serializers.SerializerMethodField()
    is_download = serializers.SerializerMethodField()
    access_request_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Distribution
        fields = [
            'id', 'resource', 'resource_title', 'resource_type', 
            'format_type', 'format_display', 'access_method',
            'endpoint_url', 'version', 'access_config', 'metadata',
            'is_api_endpoint', 'is_download', 'access_request_count',
            'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'resource_title', 'resource_type', 'format_display',
            'access_method', 'is_api_endpoint', 'is_download', 
            'access_request_count', 'created_at', 'updated_at'
        ]
    
    def get_is_api_endpoint(self, obj):
        """Check if this is an API endpoint"""
        return obj.is_api_endpoint()
    
    def get_is_download(self, obj):
        """Check if this is a download"""
        return obj.is_download()
    
    def get_access_request_count(self, obj):
        """Get count of access requests"""
        return obj.access_requests.filter(is_active=True).count()
    
    def validate_format_type(self, value):
        """Validate format type"""
        valid_formats = ['REST_JSON', 'GraphQL', 'ZIP', 'API']
        if value not in valid_formats:
            raise serializers.ValidationError(
                f"Format type must be one of: {', '.join(valid_formats)}"
            )
        return value
    
    def validate_endpoint_url(self, value):
        """Validate endpoint URL format"""
        import re
        
        # Basic URL validation
        url_pattern = re.compile(
            r'^https?://'  # http:// or https://
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
            r'localhost|'  # localhost...
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
            r'(?::\d+)?'  # optional port
            r'(?:/?|[/?]\S+)$', re.IGNORECASE)
        
        if not url_pattern.match(value):
            raise serializers.ValidationError("Invalid URL format")
        
        return value
    
    def validate_access_config(self, value):
        """Validate access configuration"""
        if value and not isinstance(value, dict):
            raise serializers.ValidationError("Access config must be a JSON object")
        
        # Validate specific access config fields
        if value:
            # Validate rate limits
            if 'rate_limit' in value:
                rate_limit = value['rate_limit']
                if not isinstance(rate_limit, dict):
                    raise serializers.ValidationError("Rate limit must be an object")
                
                # Validate rate limit structure
                valid_rate_fields = ['requests_per_minute', 'requests_per_hour', 'requests_per_day']
                for field in rate_limit:
                    if field not in valid_rate_fields:
                        raise serializers.ValidationError(
                            f"Invalid rate limit field '{field}'. "
                            f"Valid fields: {', '.join(valid_rate_fields)}"
                        )
                    if not isinstance(rate_limit[field], int) or rate_limit[field] < 0:
                        raise serializers.ValidationError(
                            f"Rate limit '{field}' must be a non-negative integer"
                        )
        
        return value or {}
    
    def validate_metadata(self, value):
        """Validate metadata structure"""
        if value and not isinstance(value, dict):
            raise serializers.ValidationError("Metadata must be a JSON object")
        return value or {}
    
    def validate(self, attrs):
        """Cross-field validation"""
        # Ensure resource and format combination is unique for this version
        resource = attrs.get('resource')
        format_type = attrs.get('format_type')
        version = attrs.get('version')
        
        if resource and format_type and version:
            existing_qs = Distribution.objects.filter(
                resource=resource,
                format_type=format_type,
                version=version,
                is_active=True
            )
            
            # Exclude current instance if updating
            if self.instance:
                existing_qs = existing_qs.exclude(pk=self.instance.pk)
            
            if existing_qs.exists():
                raise serializers.ValidationError(
                    f"Distribution with format '{format_type}' and version '{version}' "
                    f"already exists for this resource"
                )
        
        return attrs


class DistributionListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for distribution listings
    """
    resource_title = serializers.CharField(source='resource.title', read_only=True)
    format_display = serializers.CharField(source='get_format_type_display', read_only=True)
    access_request_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Distribution
        fields = [
            'id', 'resource_title', 'format_type', 'format_display',
            'version', 'endpoint_url', 'access_request_count', 'created_at'
        ]
    
    def get_access_request_count(self, obj):
        return obj.access_requests.filter(is_active=True).count()
