"""
Enhanced DRF Serializers for ERD-aligned Content models
Updated for complete OpenAPI compliance with new model relationships
"""
from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import (
    PublishingOrganization, PublishingOrganizationMember, License, Resource, 
    ResourceVersion, Asset, AssetVersion, AssetAccessRequest, AssetAccess, 
    UsageEvent, Distribution
)

def get_file_url(file_field):
    """Helper function to safely get URL from file field"""
    if file_field and hasattr(file_field, 'url'):
        return file_field.url
    return ''

User = get_user_model()


# ============================================================================
# LICENSE SERIALIZERS
# ============================================================================

class LicenseSummarySerializer(serializers.Serializer):
    """License summary for asset/resource references"""
    code = serializers.CharField()
    name = serializers.CharField()
    short_name = serializers.CharField(required=False, allow_blank=True)
    icon_url = serializers.URLField(required=False, allow_blank=True)
    is_default = serializers.BooleanField(default=False)
    
    @classmethod
    def from_license_model(cls, license_obj):
        """Create LicenseSummary from License model"""
        return {
            'code': license_obj.code,
            'name': license_obj.name,
            'short_name': license_obj.short_name or '',
            'icon_url': get_file_url(license_obj.icon_url),
            'is_default': license_obj.is_default
        }


class LicenseDetailSerializer(serializers.Serializer):
    """Complete license details with terms and usage count"""
    code = serializers.CharField()
    name = serializers.CharField()
    short_name = serializers.CharField(required=False, allow_blank=True)
    url = serializers.URLField(required=False, allow_blank=True)
    icon_url = serializers.URLField(required=False, allow_blank=True)
    summary = serializers.CharField(required=False, allow_blank=True)
    full_text = serializers.CharField(required=False, allow_blank=True)
    legal_code_url = serializers.URLField(required=False, allow_blank=True)
    usage_count = serializers.IntegerField(default=0)
    license_terms = serializers.DictField(default=dict)
    permissions = serializers.DictField(default=dict)
    conditions = serializers.DictField(default=dict)
    limitations = serializers.DictField(default=dict)
    is_default = serializers.BooleanField(default=False)
    
    @classmethod
    def from_license_model(cls, license_obj):
        """Create LicenseDetail from License model"""
        # Calculate usage count safely
        try:
            usage_count = (
                license_obj.assets.count() + 
                license_obj.default_for_resources.count() +
                license_obj.effective_for_accesses.count()
            )
        except:
            usage_count = 0
            
        return {
            'code': license_obj.code,
            'name': license_obj.name,
            'short_name': license_obj.short_name or '',
            'url': license_obj.url or '',
            'icon_url': get_file_url(license_obj.icon_url),
            'summary': license_obj.summary or '',
            'full_text': license_obj.full_text or '',
            'legal_code_url': license_obj.legal_code_url or '',
            'usage_count': usage_count,
            'license_terms': license_obj.license_terms or {},
            'permissions': license_obj.permissions or {},
            'conditions': license_obj.conditions or {},
            'limitations': license_obj.limitations or {},
            'is_default': license_obj.is_default
        }


# ============================================================================
# PUBLISHER SERIALIZERS
# ============================================================================

class PublisherSummarySerializer(serializers.Serializer):
    """Publisher summary for asset/resource references"""
    id = serializers.IntegerField()
    name = serializers.CharField()
    thumbnail_url = serializers.URLField(allow_blank=True)
    bio = serializers.CharField(required=False, allow_blank=True)
    verified = serializers.BooleanField(default=False)
    
    @classmethod
    def from_publishing_organization(cls, org):
        """Create PublisherSummary from PublishingOrganization model"""
        return {
            'id': org.id,
            'name': org.name,
            'thumbnail_url': get_file_url(org.icone_image_url),  # Map icone_image_url -> thumbnail_url
            'bio': org.bio or '',
            'verified': getattr(org, 'verified', False)
        }


class PublisherSerializer(serializers.Serializer):
    """Full Publisher serializer for detailed organization information"""
    id = serializers.IntegerField()
    name = serializers.CharField()
    description = serializers.CharField(allow_blank=True)
    bio = serializers.CharField(allow_blank=True)
    thumbnail_url = serializers.URLField(allow_blank=True)
    cover_url = serializers.URLField(required=False, allow_blank=True, allow_null=True)
    location = serializers.CharField(required=False, allow_blank=True)
    website = serializers.URLField(required=False, allow_blank=True)
    verified = serializers.BooleanField(default=False)
    social_links = serializers.DictField(default=dict)
    stats = serializers.DictField()
    assets = serializers.ListField(child=serializers.DictField(), default=list)
    
    @classmethod
    def from_publishing_organization(cls, org, request=None):
        """Create full Publisher from PublishingOrganization model"""
        # Get related objects efficiently
        assets = Asset.objects.filter(
            resource__publishing_organization=org
        ).select_related('license').order_by('-created_at')[:10]
        
        resources = Resource.objects.filter(
            publishing_organization=org
        ).count()
        
        # Calculate stats
        assets_count = Asset.objects.filter(resource__publishing_organization=org).count()
        total_downloads = sum(asset.download_count for asset in assets)
        
        # Prepare assets data
        assets_data = []
        for asset in assets:
            assets_data.append({
                'id': asset.id,
                'title': asset.title,
                'description': asset.description,
                'thumbnail_url': get_file_url(asset.thumbnail_url),
                'category': asset.category,
                'license': LicenseSummarySerializer.from_license_model(asset.license),
                'has_access': cls._check_user_access(asset, request),
                'download_count': asset.download_count,
                'file_size': asset.file_size
            })
        
        return {
            'id': org.id,
            'name': org.name,
            'description': org.description or '',
            'bio': org.bio or '',
            'thumbnail_url': get_file_url(org.icone_image_url),
            'cover_url': get_file_url(getattr(org, 'cover_url', None)),
            'location': org.location or '',
            'website': org.website or '',
            'verified': getattr(org, 'verified', False),
            'social_links': org.social_links or {},
            'stats': {
                'resources_count': resources,
                'assets_count': assets_count,
                'total_downloads': total_downloads,
                'joined_at': org.created_at.isoformat() if org.created_at else None
            },
            'assets': assets_data
        }
    
    @staticmethod
    def _check_user_access(asset, request):
        """Check if user has access to asset"""
        if not request or not request.user.is_authenticated:
            return False
        return AssetAccess.user_has_access(request.user, asset)


# ============================================================================
# ASSET SERIALIZERS
# ============================================================================

class AssetSummarySerializer(serializers.Serializer):
    """Asset summary for listing views"""
    id = serializers.IntegerField()
    title = serializers.CharField()
    description = serializers.CharField(allow_blank=True)
    thumbnail_url = serializers.URLField(allow_blank=True)
    category = serializers.CharField()
    license = LicenseSummarySerializer()
    publisher = PublisherSummarySerializer()
    has_access = serializers.BooleanField(default=False)
    download_count = serializers.IntegerField(default=0)
    file_size = serializers.CharField(allow_blank=True)
    
    @classmethod
    def from_asset_model(cls, asset, request=None):
        """Create AssetSummary from Asset model"""
        return {
            'id': asset.id,
            'title': asset.title,
            'description': asset.description or '',
            'thumbnail_url': get_file_url(asset.thumbnail_url),
            'category': asset.category,
            'license': LicenseSummarySerializer.from_license_model(asset.license),
            'publisher': PublisherSummarySerializer.from_publishing_organization(asset.resource.publishing_organization),
            'has_access': cls._check_user_access(asset, request),
            'download_count': asset.download_count,
            'file_size': asset.file_size or ''
        }
    
    @staticmethod
    def _check_user_access(asset, request):
        """Check if user has access to asset"""
        if not request or not request.user.is_authenticated:
            return False
        return AssetAccess.user_has_access(request.user, asset)


class AssetSnapshotSerializer(serializers.Serializer):
    """Asset snapshots/previews"""
    id = serializers.IntegerField()
    type = serializers.CharField()
    url = serializers.URLField()
    description = serializers.CharField(required=False, allow_blank=True)


class AssetTechnicalDetailsSerializer(serializers.Serializer):
    """Technical details for assets"""
    format = serializers.CharField()
    encoding = serializers.CharField(required=False, allow_blank=True)
    file_size = serializers.CharField()
    version = serializers.CharField(required=False, allow_blank=True)
    language = serializers.CharField(required=False, allow_blank=True)
    
    @classmethod
    def from_asset_model(cls, asset):
        """Create technical details from Asset model"""
        latest_version = asset.get_latest_version()
        return {
            'format': asset.format or '',
            'encoding': asset.encoding or '',
            'file_size': asset.file_size or '',
            'version': asset.version or '',
            'language': asset.language or ''
        }


class AssetStatsSerializer(serializers.Serializer):
    """Statistics for assets"""
    download_count = serializers.IntegerField(default=0)
    view_count = serializers.IntegerField(default=0)
    last_downloaded_at = serializers.DateTimeField(required=False, allow_null=True)
    
    @classmethod
    def from_asset_model(cls, asset):
        """Create stats from Asset model"""
        return {
            'download_count': asset.download_count,
            'view_count': asset.view_count,
            'last_downloaded_at': None  # Could be computed from UsageEvent
        }


class AssetAccessSerializer(serializers.Serializer):
    """Asset access information"""
    has_access = serializers.BooleanField(default=False)
    requires_approval = serializers.BooleanField(default=False)
    download_url = serializers.URLField(required=False, allow_blank=True)
    
    @classmethod
    def from_asset_and_user(cls, asset, user):
        """Create access info from Asset and User"""
        if not user or not user.is_authenticated:
            return {
                'has_access': False,
                'requires_approval': False,
                'download_url': ''
            }
        
        access = AssetAccess.get_user_access(user, asset)
        return {
            'has_access': access is not None and access.is_active,
            'requires_approval': False,  # V1: Auto-approval
            'download_url': access.get_download_url() if access else ''
        }


class RelatedAssetSerializer(serializers.Serializer):
    """Related assets"""
    id = serializers.IntegerField()
    title = serializers.CharField()
    thumbnail_url = serializers.URLField(allow_blank=True)
    category = serializers.CharField()
    publisher = PublisherSummarySerializer()


class AssetResourceSerializer(serializers.Serializer):
    """Minimal resource info nested under asset details (per OpenAPI AssetResource)"""
    id = serializers.IntegerField()
    title = serializers.CharField()
    description = serializers.CharField(allow_blank=True)


class AssetDetailSerializer(serializers.Serializer):
    """Complete asset details"""
    id = serializers.IntegerField()
    title = serializers.CharField()
    description = serializers.CharField(allow_blank=True)
    long_description = serializers.CharField(allow_blank=True)
    thumbnail_url = serializers.URLField(allow_blank=True)
    category = serializers.CharField()
    license = LicenseDetailSerializer()
    publisher = PublisherSummarySerializer()
    resource = AssetResourceSerializer(required=False, allow_null=True)
    snapshots = serializers.ListField(child=AssetSnapshotSerializer(), default=list)
    technical_details = AssetTechnicalDetailsSerializer()
    stats = AssetStatsSerializer()
    access = AssetAccessSerializer()
    related_assets = serializers.ListField(child=RelatedAssetSerializer(), default=list)
    
    @classmethod
    def from_asset_model(cls, asset, request=None):
        """Create complete asset details from Asset model"""
        user = request.user if request and request.user.is_authenticated else None
        
        # Get related assets
        related_assets = asset.get_related_assets(limit=5)
        related_data = []
        for related in related_assets:
            related_data.append({
                'id': related.id,
                'title': related.title,
                'thumbnail_url': get_file_url(related.thumbnail_url),
                'category': related.category,
                'publisher': PublisherSummarySerializer.from_publishing_organization(related.resource.publishing_organization)
            })
        
        # Prepare resource info (nullable)
        resource_obj = getattr(asset, 'resource', None)
        resource_data = None
        if resource_obj:
            resource_data = {
                'id': resource_obj.id,
                'title': resource_obj.name or '',
                'description': resource_obj.description or ''
            }
        
        return {
            'id': asset.id,
            'title': asset.title,
            'description': asset.description or '',
            'long_description': asset.long_description or '',
            'thumbnail_url': get_file_url(asset.thumbnail_url),
            'category': asset.category,
            'license': LicenseDetailSerializer.from_license_model(asset.license),
            'publisher': PublisherSummarySerializer.from_publishing_organization(asset.resource.publishing_organization),
            'resource': resource_data,
            'snapshots': [],  # Could be implemented based on asset versions
            'technical_details': AssetTechnicalDetailsSerializer.from_asset_model(asset),
            'stats': AssetStatsSerializer.from_asset_model(asset),
            'access': AssetAccessSerializer.from_asset_and_user(asset, user),
            'related_assets': related_data
        }


# ============================================================================
# RESOURCE SERIALIZERS
# ============================================================================

class ResourceVersionSerializer(serializers.Serializer):
    """Resource version information"""
    version = serializers.CharField()
    type = serializers.CharField()
    size_bytes = serializers.IntegerField()
    is_latest = serializers.BooleanField()
    created_at = serializers.DateTimeField()
    
    @classmethod
    def from_resource_version(cls, version):
        """Create version info from ResourceVersion model"""
        return {
            'version': version.semvar,
            'type': version.type,
            'size_bytes': version.size_bytes,
            'is_latest': version.is_latest,
            'created_at': version.created_at
        }


class ResourceSerializer(serializers.ModelSerializer):
    """Complete resource serializer"""
    publishing_organization = PublisherSummarySerializer(read_only=True)
    default_license = LicenseSummarySerializer(read_only=True)
    latest_version = serializers.SerializerMethodField()
    version_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Resource
        fields = [
            'id', 'name', 'slug', 'description', 'category', 'status',
            'publishing_organization', 'default_license', 'latest_version',
            'version_count', 'created_at', 'updated_at'
        ]
    
    def get_latest_version(self, obj):
        """Get latest version info"""
        latest = obj.get_latest_version()
        return ResourceVersionSerializer.from_resource_version(latest) if latest else None
    
    def get_version_count(self, obj):
        """Get version count"""
        return obj.version_count


# ============================================================================
# ACCESS REQUEST SERIALIZERS
# ============================================================================

class AccessRequestResponseSerializer(serializers.Serializer):
    """Response for access request operations"""
    request_id = serializers.IntegerField()
    status = serializers.CharField()
    message = serializers.CharField()
    access = serializers.DictField(required=False)
    
    @classmethod
    def from_request_and_access(cls, request_obj, access_obj=None):
        """Create response from request and optional access"""
        data = {
            'request_id': request_obj.id,
            'status': request_obj.status,
            'message': request_obj.admin_response or f"Request {request_obj.status}"
        }
        
        if access_obj:
            data['access'] = {
                'download_url': access_obj.get_download_url(),
                'expires_at': access_obj.expires_at.isoformat() if access_obj.expires_at else None,
                'granted_at': access_obj.granted_at.isoformat()
            }
        
        return data


# ============================================================================
# USAGE EVENT SERIALIZERS  
# ============================================================================

class UsageEventSerializer(serializers.ModelSerializer):
    """Usage event serializer for analytics"""
    developer_user_email = serializers.CharField(source='developer_user.email', read_only=True)
    asset_title = serializers.SerializerMethodField()
    resource_name = serializers.SerializerMethodField()
    
    class Meta:
        model = UsageEvent
        fields = [
            'id', 'developer_user_email', 'usage_kind', 'subject_kind',
            'asset_title', 'resource_name', 'metadata', 'created_at'
        ]
    
    def get_asset_title(self, obj):
        """Get asset title if subject is asset"""
        if obj.subject_kind == 'asset' and obj.asset_id:
            try:
                asset = Asset.objects.get(id=obj.asset_id)
                return asset.title
            except Asset.DoesNotExist:
                pass
        return None
    
    def get_resource_name(self, obj):
        """Get resource name if subject is resource"""
        if obj.subject_kind == 'resource' and obj.resource_id:
            try:
                resource = Resource.objects.get(id=obj.resource_id)
                return resource.name
            except Resource.DoesNotExist:
                pass
        return None


## Distribution serializers removed in V1