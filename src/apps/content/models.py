"""
Complete ERD-aligned models for Itqan CMS
Based on db_design_v1.drawio specification
"""
from django.db import models
from django.conf import settings
from django.core.validators import URLValidator
from apps.core.models import BaseModel, ActiveObjectsManager, AllObjectsManager


# ============================================================================
# 1. PUBLISHING ORGANIZATION
# ============================================================================
class PublishingOrganization(BaseModel):
    """
    Publishing organization entity from ERD.
    Organizations that publish resources and have multiple members.
    """
    # Core fields from ERD
    name = models.CharField(
        max_length=255,
        help_text="Organization name e.g. 'Tafsir Center'"
    )
    
    slug = models.SlugField(
        unique=True,
        help_text="URL-friendly slug e.g. 'tafsir-center'"
    )
    
    icone_image_url = models.URLField(
        blank=True,
        help_text="Icon/logo image URL - used in V1 UI: Publisher Page"
    )
    
    summary = models.TextField(
        blank=True,
        help_text="Organization summary - used in V1 UI: Publisher Page"
    )
    
    # Additional fields for API support
    description = models.TextField(
        blank=True,
        help_text="Detailed organization description"
    )
    
    bio = models.TextField(
        blank=True,
        help_text="Organization bio for API responses"
    )
    
    cover_url = models.URLField(
        blank=True,
        help_text="Cover image URL for organization"
    )
    
    location = models.CharField(
        max_length=255,
        blank=True,
        help_text="Organization location"
    )
    
    website = models.URLField(
        blank=True,
        help_text="Organization website"
    )
    
    verified = models.BooleanField(
        default=False,
        help_text="Whether organization is verified"
    )
    
    social_links = models.JSONField(
        default=dict,
        help_text="Social media links as JSON"
    )
    
    # Relationships
    members = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through='PublishingOrganizationMember',
        related_name='publishing_organizations'
    )
    
    # Managers
    objects = ActiveObjectsManager()
    all_objects = AllObjectsManager()

    class Meta:
        db_table = 'publishing_organization'
        verbose_name = 'Publishing Organization'
        verbose_name_plural = 'Publishing Organizations'
        ordering = ['name']

    def __str__(self):
        return self.name


# ============================================================================
# 2. PUBLISHING ORGANIZATION MEMBER
# ============================================================================
class PublishingOrganizationMember(BaseModel):
    """
    Junction table for User <-> PublishingOrganization relationships.
    Defines membership roles within organizations.
    """
    ROLE_CHOICES = [
        ('owner', 'Owner'),
        ('manager', 'Manager'),  # V1: Itqan team to upload data on publishers behalf from Admin Panel. V2: more rules.
    ]
    
    # Foreign keys from ERD
    publishing_organization = models.ForeignKey(
        PublishingOrganization,
        on_delete=models.CASCADE,
        related_name='memberships'
    )
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='organization_memberships'
    )
    
    # Role field from ERD
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        help_text="Member's role in the organization"
    )
    
    # Managers
    objects = ActiveObjectsManager()
    all_objects = AllObjectsManager()

    class Meta:
        db_table = 'publishing_organization_member'
        unique_together = ['publishing_organization', 'user']
        verbose_name = 'Organization Member'
        verbose_name_plural = 'Organization Members'

    def __str__(self):
        return f"{self.user.email} -> {self.publishing_organization.name} ({self.role})"


# ============================================================================
# 3. LICENSE
# ============================================================================
class License(BaseModel):
    """
    License definitions with terms and permissions.
    Each resource has a default license.
    """
    # Core fields that would be in detailed license schema
    code = models.CharField(
        max_length=50,
        unique=True,
        help_text="License code e.g. 'cc0', 'cc-by-4.0'"
    )
    
    name = models.CharField(
        max_length=255,
        help_text="Full license name"
    )
    
    short_name = models.CharField(
        max_length=50,
        blank=True,
        help_text="Abbreviated name"
    )
    
    url = models.URLField(
        blank=True,
        help_text="Official license URL"
    )
    
    icon_url = models.URLField(
        blank=True,
        help_text="License icon URL"
    )
    
    summary = models.TextField(
        blank=True,
        help_text="Brief license description"
    )
    
    full_text = models.TextField(
        blank=True,
        help_text="Complete license text"
    )
    
    legal_code_url = models.URLField(
        blank=True,
        help_text="Legal code URL"
    )
    
    # JSON fields for structured data
    license_terms = models.JSONField(
        default=list,
        help_text="License terms as JSON array"
    )
    
    permissions = models.JSONField(
        default=list,
        help_text="Permissions as JSON array"
    )
    
    conditions = models.JSONField(
        default=list,
        help_text="Conditions as JSON array"
    )
    
    limitations = models.JSONField(
        default=list,
        help_text="Limitations as JSON array"
    )
    
    is_default = models.BooleanField(
        default=False,
        help_text="Whether this is the default license"
    )
    
    # Managers
    objects = ActiveObjectsManager()
    all_objects = AllObjectsManager()

    class Meta:
        db_table = 'license'
        verbose_name = 'License'
        verbose_name_plural = 'Licenses'
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.code})"


# ============================================================================
# 4. RESOURCE
# ============================================================================
class Resource(BaseModel):
    """
    Core resource entity from ERD.
    Original content packages published by organizations.
    """
    CATEGORY_CHOICES = [
        ('recitation', 'Recitation'),
        ('mushaf', 'Mushaf'),
        ('tafsir', 'Tafsir'),
    ]
    
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('ready', 'Ready'),  # V1: ready = ready to extract Assets from
    ]
    
    # Core fields from ERD
    publishing_organization = models.ForeignKey(
        PublishingOrganization,
        on_delete=models.PROTECT,
        related_name='resources'
    )
    
    name = models.CharField(
        max_length=255,
        help_text="Resource name e.g. 'Tafsir Ibn Katheer CSV'"
    )
    
    slug = models.SlugField(
        help_text="URL slug e.g. 'tafsir-ibn-katheer-csv'"
    )
    
    description = models.TextField(
        help_text="Resource description"
    )
    
    category = models.CharField(
        max_length=20,
        choices=CATEGORY_CHOICES,
        help_text="Simple options in V1"
    )
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='draft',
        help_text="V1: ready = ready to extract Assets from"
    )
    
    default_license = models.ForeignKey(
        License,
        on_delete=models.PROTECT,
        related_name='default_for_resources',
        help_text="Default license for this resource"
    )
    
    # Managers
    objects = ActiveObjectsManager()
    all_objects = AllObjectsManager()

    class Meta:
        db_table = 'resource'
        verbose_name = 'Resource'
        verbose_name_plural = 'Resources'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['publishing_organization']),
            models.Index(fields=['category']),
            models.Index(fields=['status']),
            models.Index(fields=['slug']),
        ]

    def __str__(self):
        return f"{self.name} ({self.category})"


# ============================================================================
# 5. RESOURCE VERSION
# ============================================================================
class ResourceVersion(BaseModel):
    """
    Versioned instances of resources with semantic versioning.
    Links to storage URLs and file metadata.
    """
    TYPE_CHOICES = [
        ('csv', 'CSV'),
        ('excel', 'Excel'),
        ('json', 'JSON'),
        ('zip', 'ZIP'),
    ]
    
    # Relationships
    resource = models.ForeignKey(
        Resource,
        on_delete=models.CASCADE,
        related_name='versions'
    )
    
    # Version fields from ERD
    name = models.CharField(
        max_length=255,
        help_text="Version name - V1: same as resource name, V2: updates on content"
    )
    
    summary = models.TextField(
        blank=True,
        help_text="Version summary"
    )
    
    semvar = models.CharField(
        max_length=20,
        help_text="Semantic versioning e.g. '1.0.0' - core to bind with an AssetVersion"
    )
    
    storage_url = models.URLField(
        help_text="Absolute URL for file on S3"
    )
    
    type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES,
        help_text="File type"
    )
    
    size_bytes = models.PositiveBigIntegerField(
        help_text="File size in bytes"
    )
    
    is_latest = models.BooleanField(
        default=False,
        help_text="Whether this is the latest version"
    )
    
    # Managers
    objects = ActiveObjectsManager()
    all_objects = AllObjectsManager()

    class Meta:
        db_table = 'resource_version'
        verbose_name = 'Resource Version'
        verbose_name_plural = 'Resource Versions'
        ordering = ['-created_at']
        unique_together = ['resource', 'semvar']

    def __str__(self):
        return f"{self.resource.name} v{self.semvar}"


# ============================================================================
# 6. ASSET
# ============================================================================
class Asset(BaseModel):
    """
    Individual assets that can be downloaded.
    Part of resources, published by organizations.
    """
    # Relationships from ERD
    publishing_organization = models.ForeignKey(
        PublishingOrganization,
        on_delete=models.PROTECT,
        related_name='assets'
    )
    
    # Core asset fields that would be in the detailed schema
    name = models.CharField(
        max_length=255,
        help_text="Asset name"
    )
    
    title = models.CharField(
        max_length=255,
        help_text="Display title for API"
    )
    
    description = models.TextField(
        help_text="Asset description"
    )
    
    long_description = models.TextField(
        blank=True,
        help_text="Extended description"
    )
    
    thumbnail_url = models.URLField(
        blank=True,
        help_text="Asset thumbnail image"
    )
    
    category = models.CharField(
        max_length=20,
        choices=Resource.CATEGORY_CHOICES,
        help_text="Asset category matching resource categories"
    )
    
    # License relationship
    license = models.ForeignKey(
        License,
        on_delete=models.PROTECT,
        related_name='assets'
    )
    
    # Technical details
    file_size = models.CharField(
        max_length=50,
        help_text="Human readable file size e.g. '2.5 MB'"
    )
    
    format = models.CharField(
        max_length=50,
        help_text="File format"
    )
    
    encoding = models.CharField(
        max_length=50,
        default='UTF-8',
        help_text="Text encoding"
    )
    
    version = models.CharField(
        max_length=50,
        help_text="Asset version"
    )
    
    language = models.CharField(
        max_length=10,
        help_text="Asset language code"
    )
    
    # Stats
    download_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of downloads"
    )
    
    view_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of views"
    )
    
    # Managers
    objects = ActiveObjectsManager()
    all_objects = AllObjectsManager()

    class Meta:
        db_table = 'asset'
        verbose_name = 'Asset'
        verbose_name_plural = 'Assets'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['publishing_organization']),
            models.Index(fields=['category']),
            models.Index(fields=['license']),
        ]

    def __str__(self):
        return f"{self.title} ({self.category})"


# ============================================================================
# 7. ASSET VERSION
# ============================================================================
class AssetVersion(BaseModel):
    """
    Individual downloadable assets extracted from resource versions.
    """
    # Relationships
    asset = models.ForeignKey(
        Asset,
        on_delete=models.CASCADE,
        related_name='versions'
    )
    
    resource_version = models.ForeignKey(
        ResourceVersion,
        on_delete=models.CASCADE,
        related_name='asset_versions'
    )
    
    # Asset version fields from ERD
    name = models.CharField(
        max_length=255,
        help_text="Asset version name"
    )
    
    summary = models.TextField(
        blank=True,
        help_text="Asset version summary"
    )
    
    file_url = models.URLField(
        help_text="Direct URL to asset file"
    )
    
    size_bytes = models.PositiveBigIntegerField(
        help_text="File size in bytes"
    )
    
    # Managers
    objects = ActiveObjectsManager()
    all_objects = AllObjectsManager()

    class Meta:
        db_table = 'asset_version'
        verbose_name = 'Asset Version'
        verbose_name_plural = 'Asset Versions'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.asset.name} -> {self.resource_version.semvar}"


# ============================================================================
# 8. ASSET ACCESS REQUEST
# ============================================================================
class AssetAccessRequest(BaseModel):
    """
    User requests for asset access with approval workflow.
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    
    INTENDED_USE_CHOICES = [
        ('commercial', 'Commercial'),
        ('non-commercial', 'Non-Commercial'),
    ]
    
    # Relationships from ERD
    developer_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='asset_requests'
    )
    
    asset = models.ForeignKey(
        Asset,
        on_delete=models.CASCADE,
        related_name='access_requests'
    )
    
    # Request fields from ERD
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )
    
    developer_access_reason = models.TextField(
        help_text="Reason for requesting access - used in V1 UI"
    )
    
    intended_use = models.CharField(
        max_length=20,
        choices=INTENDED_USE_CHOICES,
        help_text="Commercial or non-commercial use"
    )
    
    # Admin response
    admin_response = models.TextField(
        blank=True,
        help_text="Admin response message"
    )
    
    approved_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When request was approved"
    )
    
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_asset_requests'
    )
    
    # Managers
    objects = ActiveObjectsManager()
    all_objects = AllObjectsManager()

    class Meta:
        db_table = 'asset_access_request'
        verbose_name = 'Asset Access Request'
        verbose_name_plural = 'Asset Access Requests'
        ordering = ['-created_at']
        unique_together = ['developer_user', 'asset']

    def __str__(self):
        return f"{self.developer_user.email} -> {self.asset.title} ({self.status})"


# ============================================================================
# 9. ASSET ACCESS
# ============================================================================
class AssetAccess(BaseModel):
    """
    Granted access to assets for users.
    Created when access requests are approved.
    """
    # Relationships from ERD
    asset_access_request = models.OneToOneField(
        AssetAccessRequest,
        on_delete=models.CASCADE,
        related_name='access_grant'
    )
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='asset_accesses'
    )
    
    asset = models.ForeignKey(
        Asset,
        on_delete=models.CASCADE,
        related_name='user_accesses'
    )
    
    # License snapshot from ERD
    effective_license = models.ForeignKey(
        License,
        on_delete=models.PROTECT,
        help_text="License snapshot at time of access grant"
    )
    
    # Access details
    granted_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When access was granted"
    )
    
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When access expires (null = never expires)"
    )
    
    download_url = models.URLField(
        blank=True,
        help_text="Direct download URL"
    )
    
    # Managers
    objects = ActiveObjectsManager()
    all_objects = AllObjectsManager()

    class Meta:
        db_table = 'asset_access'
        verbose_name = 'Asset Access'
        verbose_name_plural = 'Asset Accesses'
        ordering = ['-granted_at']
        unique_together = ['user', 'asset']

    def __str__(self):
        return f"{self.user.email} has access to {self.asset.title}"


# ============================================================================
# 10. USAGE EVENT
# ============================================================================
class UsageEvent(BaseModel):
    """
    Analytics tracking for asset and resource usage.
    Tracks downloads and other usage events.
    """
    USAGE_KIND_CHOICES = [
        ('file_download', 'File Download'),
        ('view', 'View'),
        ('api_access', 'API Access'),
    ]
    
    SUBJECT_KIND_CHOICES = [
        ('resource', 'Resource'),
        ('asset', 'Asset'),
    ]
    
    # User tracking
    developer_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='usage_events'
    )
    
    # Event details from ERD
    usage_kind = models.CharField(
        max_length=20,
        choices=USAGE_KIND_CHOICES,
        help_text="Type of usage event"
    )
    
    subject_kind = models.CharField(
        max_length=20,
        choices=SUBJECT_KIND_CHOICES,
        help_text="Whether tracking resource or asset"
    )
    
    # Conditional foreign keys based on subject_kind
    resource_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Resource ID if subject_kind = 'resource'"
    )
    
    asset_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Asset ID if subject_kind = 'asset'"
    )
    
    # Event metadata
    metadata = models.JSONField(
        default=dict,
        help_text="Additional event metadata"
    )
    
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="User IP address"
    )
    
    user_agent = models.TextField(
        blank=True,
        help_text="User browser/client information"
    )
    
    # Managers
    objects = ActiveObjectsManager()
    all_objects = AllObjectsManager()

    class Meta:
        db_table = 'usage_event'
        verbose_name = 'Usage Event'
        verbose_name_plural = 'Usage Events'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['developer_user']),
            models.Index(fields=['usage_kind']),
            models.Index(fields=['subject_kind']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"{self.developer_user.email} - {self.usage_kind} on {self.subject_kind}"


# ============================================================================
# 11. DISTRIBUTION (CHANNEL)
# ============================================================================
class Distribution(BaseModel):
    """
    Distribution channels for accessing resource content.
    Defines different delivery methods (API, ZIP download, etc).
    """
    FORMAT_TYPE_CHOICES = [
        ('REST_JSON', 'REST API (JSON)'),
        ('GraphQL', 'GraphQL API'),
        ('ZIP', 'ZIP Download'),
        ('API', 'Custom API'),
    ]
    
    # Relationship
    resource = models.ForeignKey(
        Resource,
        on_delete=models.CASCADE,
        related_name='distributions',
        help_text="Resource that this distribution provides access to"
    )
    
    # Distribution details
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
        return f"{self.resource.name} - {self.format_type} v{self.version}"

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