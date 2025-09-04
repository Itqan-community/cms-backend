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


# Asset API Serializers (Simplified frontend interface)
class LicenseSummarySerializer(serializers.Serializer):
    """Serializer for license summary in asset responses"""
    code = serializers.CharField()
    name = serializers.CharField()
    short_name = serializers.CharField(required=False)
    icon_url = serializers.URLField(required=False)
    is_default = serializers.BooleanField(default=False)
    
    @classmethod
    def from_license_model(cls, license_obj):
        """Create LicenseSummary from License model"""
        return {
            'code': license_obj.code,
            'name': license_obj.name,
            'short_name': license_obj.short_name,
            'icon_url': license_obj.icon_url,
            'is_default': license_obj.is_default
        }


class PublisherSummarySerializer(serializers.Serializer):
    """Serializer for publisher summary in asset responses - maps PublishingOrganization to OpenAPI Publisher"""
    id = serializers.IntegerField()
    name = serializers.CharField()
    thumbnail_url = serializers.URLField()
    bio = serializers.CharField(required=False)
    verified = serializers.BooleanField()
    
    @classmethod
    def from_publishing_organization(cls, org):
        """Create PublisherSummary from PublishingOrganization model"""
        return {
            'id': org.id,
            'name': org.name,
            'thumbnail_url': org.icone_image_url or '',  # Map icone_image_url -> thumbnail_url
            'bio': org.bio or '',
            'verified': org.verified
        }


class PublisherSerializer(serializers.Serializer):
    """Full Publisher serializer - maps PublishingOrganization to OpenAPI Publisher schema"""
    id = serializers.IntegerField()
    name = serializers.CharField()
    description = serializers.CharField()
    bio = serializers.CharField()
    thumbnail_url = serializers.URLField()
    cover_url = serializers.URLField(required=False, allow_null=True)
    location = serializers.CharField(required=False, allow_null=True)
    website = serializers.URLField(required=False, allow_null=True)
    verified = serializers.BooleanField()
    social_links = serializers.DictField()
    stats = serializers.DictField()
    assets = serializers.ListField(child=serializers.DictField(), default=list)
    
    @classmethod
    def from_publishing_organization(cls, org, request=None):
        """Create full Publisher from PublishingOrganization model with computed stats"""
        # Compute stats
        assets_count = org.assets.filter(is_active=True).count()
        resources_count = org.resources.filter(is_active=True).count()
        total_downloads = sum(asset.download_count for asset in org.assets.filter(is_active=True))
        
        # Get assets summary for this publisher
        assets_data = []
        for asset in org.assets.filter(is_active=True)[:10]:  # Limit to first 10 assets
            assets_data.append({
                'id': asset.id,
                'title': asset.title,
                'description': asset.description,
                'thumbnail_url': asset.thumbnail_url,
                'category': asset.category,
                'has_access': False,  # Would be computed based on user access
                'download_count': asset.download_count,
                'file_size': asset.file_size
            })
        
        return {
            'id': org.id,
            'name': org.name,
            'description': org.description,
            'bio': org.bio,
            'thumbnail_url': org.icone_image_url or '',  # Map icone_image_url -> thumbnail_url
            'cover_url': org.cover_url,
            'location': org.location,
            'website': org.website,
            'verified': org.verified,
            'social_links': org.social_links or {},
            'stats': {
                'resources_count': resources_count,
                'assets_count': assets_count,
                'total_downloads': total_downloads,
                'joined_at': org.created_at.isoformat()
            },
            'assets': assets_data
        }


class AssetSummarySerializer(serializers.Serializer):
    """Serializer for asset summary in list view - maps Asset model to OpenAPI AssetSummary"""
    id = serializers.IntegerField()  # Changed from UUIDField to IntegerField to match our model
    title = serializers.CharField()
    description = serializers.CharField()
    thumbnail_url = serializers.URLField()
    category = serializers.ChoiceField(choices=['mushaf', 'tafsir', 'recitation'])
    license = LicenseSummarySerializer()
    publisher = PublisherSummarySerializer()
    has_access = serializers.BooleanField()
    download_count = serializers.IntegerField()
    file_size = serializers.CharField()
    
    @classmethod
    def from_asset_model(cls, asset, user=None):
        """Create AssetSummary from Asset model with computed fields"""
        # Check if user has access to this asset
        has_access = False
        if user and user.is_authenticated:
            # Check if user has AssetAccess for this asset
            from .models import AssetAccess
            has_access = AssetAccess.objects.filter(
                user=user, asset=asset, is_active=True
            ).exists()
        
        return {
            'id': asset.id,
            'title': asset.title,
            'description': asset.description,
            'thumbnail_url': asset.thumbnail_url,
            'category': asset.category,
            'license': LicenseSummarySerializer.from_license_model(asset.license),
            'publisher': PublisherSummarySerializer.from_publishing_organization(asset.publishing_organization),
            'has_access': has_access,
            'download_count': asset.download_count,
            'file_size': asset.file_size
        }


class AssetSnapshotSerializer(serializers.Serializer):
    """Serializer for asset snapshots"""
    thumbnail_url = serializers.URLField()
    title = serializers.CharField()
    description = serializers.CharField()


class AssetResourceSerializer(serializers.Serializer):
    """Serializer for asset resource reference"""
    id = serializers.UUIDField()
    title = serializers.CharField()
    description = serializers.CharField()


class AssetTechnicalDetailsSerializer(serializers.Serializer):
    """Serializer for asset technical details"""
    file_size = serializers.CharField()
    format = serializers.CharField()
    encoding = serializers.CharField()
    version = serializers.CharField()
    language = serializers.CharField()


class AssetStatsSerializer(serializers.Serializer):
    """Serializer for asset statistics"""
    download_count = serializers.IntegerField()
    view_count = serializers.IntegerField()
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()


class AssetAccessSerializer(serializers.Serializer):
    """Serializer for asset access information"""
    has_access = serializers.BooleanField()
    requires_approval = serializers.BooleanField()


class RelatedAssetSerializer(serializers.Serializer):
    """Serializer for related assets"""
    id = serializers.UUIDField()
    title = serializers.CharField()
    thumbnail_url = serializers.URLField()


class LicenseDetailSerializer(serializers.Serializer):
    """Serializer for detailed license information with computed usage_count"""
    code = serializers.CharField()
    name = serializers.CharField()
    short_name = serializers.CharField()
    url = serializers.URLField()
    icon_url = serializers.URLField()
    summary = serializers.CharField()
    full_text = serializers.CharField()
    legal_code_url = serializers.URLField()
    license_terms = serializers.ListField(child=serializers.DictField(), default=list)
    permissions = serializers.ListField(child=serializers.DictField(), default=list)
    conditions = serializers.ListField(child=serializers.DictField(), default=list)
    limitations = serializers.ListField(child=serializers.DictField(), default=list)
    usage_count = serializers.IntegerField()
    is_default = serializers.BooleanField()
    
    @classmethod
    def from_license_model(cls, license_obj):
        """Create LicenseDetail from License model with computed usage_count"""
        # Compute usage count from related assets
        usage_count = license_obj.assets.filter(is_active=True).count()
        
        return {
            'code': license_obj.code,
            'name': license_obj.name,
            'short_name': license_obj.short_name,
            'url': license_obj.url,
            'icon_url': license_obj.icon_url,
            'summary': license_obj.summary,
            'full_text': license_obj.full_text,
            'legal_code_url': license_obj.legal_code_url,
            'license_terms': license_obj.license_terms or [],
            'permissions': license_obj.permissions or [],
            'conditions': license_obj.conditions or [],
            'limitations': license_obj.limitations or [],
            'usage_count': usage_count,  # Computed field
            'is_default': license_obj.is_default
        }


class AssetDetailSerializer(serializers.Serializer):
    """Serializer for detailed asset view - maps Asset model to OpenAPI Asset schema"""
    id = serializers.IntegerField()  # Changed from UUIDField to IntegerField
    title = serializers.CharField()
    description = serializers.CharField()
    long_description = serializers.CharField()
    thumbnail_url = serializers.URLField()
    category = serializers.ChoiceField(choices=['mushaf', 'tafsir', 'recitation'])
    license = LicenseDetailSerializer()
    snapshots = AssetSnapshotSerializer(many=True)
    publisher = PublisherSummarySerializer()
    resource = AssetResourceSerializer(required=False, allow_null=True)
    technical_details = AssetTechnicalDetailsSerializer()
    stats = AssetStatsSerializer()
    access = AssetAccessSerializer()
    related_assets = RelatedAssetSerializer(many=True)
    
    @classmethod
    def from_asset_model(cls, asset, user=None):
        """Create AssetDetail from Asset model with computed fields"""
        # Check if user has access to this asset
        has_access = False
        if user and user.is_authenticated:
            from .models import AssetAccess
            has_access = AssetAccess.objects.filter(
                user=user, asset=asset, is_active=True
            ).exists()
        
        # Generate snapshots (mock implementation - would use actual snapshot logic)
        snapshots_data = []
        if asset.thumbnail_url:
            snapshots_data.append({
                'thumbnail_url': asset.thumbnail_url,
                'title': f"{asset.title} - Preview",
                'description': f"Preview of {asset.title}"
            })
        
        # Get related assets (same category/publisher)
        related_assets = asset.publishing_organization.assets.filter(
            category=asset.category, is_active=True
        ).exclude(id=asset.id)[:5]
        
        related_data = []
        for related in related_assets:
            related_data.append({
                'id': related.id,
                'title': related.title,
                'thumbnail_url': related.thumbnail_url
            })
        
        return {
            'id': asset.id,
            'title': asset.title,
            'description': asset.description,
            'long_description': asset.long_description or asset.description,
            'thumbnail_url': asset.thumbnail_url,
            'category': asset.category,
            'license': LicenseDetailSerializer.from_license_model(asset.license),
            'snapshots': snapshots_data,
            'publisher': PublisherSummarySerializer.from_publishing_organization(asset.publishing_organization),
            'resource': {
                'id': asset.resource.id,
                'title': asset.resource.title,
                'description': asset.resource.description
            } if asset.resource else None,
            'technical_details': {
                'file_size': asset.file_size,
                'format': asset.format or 'Unknown',
                'encoding': asset.encoding or 'UTF-8',
                'version': asset.version or '1.0',
                'language': asset.language or 'ar'
            },
            'stats': {
                'download_count': asset.download_count,
                'view_count': asset.view_count,
                'created_at': asset.created_at,
                'updated_at': asset.updated_at
            },
            'access': {
                'has_access': has_access,
                'requires_approval': not asset.is_public
            },
            'related_assets': related_data
        }


class AccessRequestResponseSerializer(serializers.Serializer):
    """Serializer for access request response"""
    request_id = serializers.IntegerField()
    status = serializers.ChoiceField(choices=['approved', 'rejected', 'pending'])
    message = serializers.CharField()
    access = serializers.DictField(required=False, allow_null=True)
