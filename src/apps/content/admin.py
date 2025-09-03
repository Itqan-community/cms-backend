"""
Django admin configuration for Content app
"""
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.db import models
from django import forms
from .models import Resource, Distribution


class ResourceAdminForm(forms.ModelForm):
    """Enhanced form for Resource admin with asset-centric fields"""
    
    class Meta:
        model = Resource
        fields = '__all__'
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4, 'cols': 60}),
            'metadata': forms.Textarea(attrs={'rows': 6, 'cols': 60, 'placeholder': '{"key": "value"}'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Add help text for asset categories
        self.fields['resource_type'].help_text = (
            "Maps to asset categories: "
            "text → mushaf, tafsir → tafsir, audio → recitation"
        )
        
        # Enhance metadata field
        self.fields['metadata'].help_text = (
            "JSON metadata for the resource (e.g., duration for audio, "
            "page count for text, etc.)"
        )


@admin.register(Resource)
class ResourceAdmin(admin.ModelAdmin):
    """Enhanced Admin configuration for Resource model (Asset-centric view)"""
    form = ResourceAdminForm
    
    list_display = [
        'title', 'asset_category', 'language', 'publisher', 
        'version', 'asset_status', 'license_info', 'distributions_count', 
        'access_requests_count', 'published_at'
    ]
    list_filter = [
        'resource_type', 'language', 'workflow_status', 'is_active', 
        'published_at', 'created_at', 'publisher'
    ]
    search_fields = ['title', 'description', 'checksum', 'publisher__email']
    readonly_fields = ['id', 'checksum', 'created_at', 'updated_at']
    date_hierarchy = 'published_at'
    ordering = ['-created_at']
    
    actions = ['publish_resources', 'unpublish_resources', 'create_default_license']
    
    # Temporarily simplified fieldsets to avoid template rendering issues
    fields = [
        'title', 'description', 'resource_type', 'language', 'version',
        'publisher', 'workflow_status', 'published_at', 'checksum', 'metadata'
    ]
    
    def asset_category(self, obj):
        """Display asset category (mapped from resource_type)"""
        category_map = {
            'text': '📜 Mushaf',
            'tafsir': '📖 Tafsir', 
            'audio': '🎵 Recitation'
        }
        return category_map.get(obj.resource_type, obj.resource_type)
    asset_category.short_description = 'Category'
    
    def asset_status(self, obj):
        """Display asset status with workflow information"""
        if obj.workflow_status == 'published' and obj.published_at:
            return format_html(
                '<span style="color: green; font-weight: bold;">✅ Live</span>'
            )
        elif obj.workflow_status == 'reviewed':
            return format_html(
                '<span style="color: blue;">👀 Reviewed</span>'
            )
        elif obj.workflow_status == 'in_review':
            return format_html(
                '<span style="color: orange;">⏳ In Review</span>'
            )
        elif obj.workflow_status == 'rejected':
            return format_html(
                '<span style="color: red;">❌ Rejected</span>'
            )
        else:
            return format_html(
                '<span style="color: gray;">📝 Draft</span>'
            )
    asset_status.short_description = 'Status'
    
    def license_info(self, obj):
        """Display license information"""
        licenses = obj.licenses.filter(is_active=True)
        if licenses.exists():
            license = licenses.first()
            license_type_icons = {
                'open': '🌐',
                'restricted': '🔒',
                'commercial': '💰'
            }
            icon = license_type_icons.get(license.license_type, '📄')
            return format_html(
                f'{icon} {license.get_license_type_display()}'
            )
        return format_html('<span style="color: red;">⚠️ No License</span>')
    license_info.short_description = 'License'
    
    def distributions_count(self, obj):
        """Display count of distributions (download formats)"""
        count = obj.distributions.filter(is_active=True).count()
        if count > 0:
            url = reverse('admin:content_distribution_changelist')
            return format_html(
                '<a href="{}?resource__id__exact={}">{} format(s)</a>',
                url, obj.id, count
            )
        return format_html('<span style="color: orange;">⚠️ No formats</span>')
    distributions_count.short_description = 'Download Formats'
    
    def access_requests_count(self, obj):
        """Display total access requests across all distributions"""
        total_requests = 0
        for distribution in obj.distributions.filter(is_active=True):
            total_requests += distribution.access_requests.filter(is_active=True).count()
        
        if total_requests > 0:
            return format_html(
                '<span style="color: blue;">{} request(s)</span>',
                total_requests
            )
        return '0'
    access_requests_count.short_description = 'Access Requests'
    
    def asset_preview(self, obj):
        """Preview how this asset appears in the API"""
        if not obj.pk:
            return "Save the asset first to see preview"
        
        # Map resource type to API category
        category_map = {
            'text': 'mushaf',
            'tafsir': 'tafsir',
            'audio': 'recitation'
        }
        api_category = category_map.get(obj.resource_type, 'mushaf')
        
        # Get license info
        license = obj.licenses.filter(is_active=True).first()
        license_code = 'cc0' if not license else {
            'open': 'cc0',
            'restricted': 'custom-restricted', 
            'commercial': 'commercial'
        }.get(license.license_type, 'cc0')
        
        preview_html = f"""
        <div style="background: #f8f9fa; padding: 15px; border-radius: 5px; font-family: monospace;">
            <strong>API Endpoint:</strong> <code>/api/v1/assets/{obj.id}/</code><br><br>
            <strong>Asset Summary:</strong><br>
            &#123;<br>
            &nbsp;&nbsp;"id": "{obj.id}",<br>
            &nbsp;&nbsp;"title": "{obj.title}",<br>
            &nbsp;&nbsp;"category": "{api_category}",<br>
            &nbsp;&nbsp;"license": &#123; "code": "{license_code}" &#125;,<br>
            &nbsp;&nbsp;"has_access": false<br>
            &#125;
        </div>
        """
        return format_html(preview_html)
    asset_preview.short_description = 'API Preview'
    
    # Admin Actions
    def publish_resources(self, request, queryset):
        """Publish selected resources as assets"""
        from django.utils import timezone
        
        published_count = 0
        for resource in queryset:
            if resource.workflow_status in ['reviewed', 'draft']:
                resource.workflow_status = 'published'
                resource.published_at = timezone.now()
                resource.save()
                published_count += 1
        
        self.message_user(
            request,
            f"Successfully published {published_count} assets."
        )
    publish_resources.short_description = "✅ Publish selected assets"
    
    def unpublish_resources(self, request, queryset):
        """Unpublish selected resources"""
        unpublished_count = 0
        for resource in queryset.filter(workflow_status='published'):
            resource.workflow_status = 'draft'
            resource.published_at = None
            resource.save()
            unpublished_count += 1
        
        self.message_user(
            request,
            f"Successfully unpublished {unpublished_count} assets."
        )
    unpublish_resources.short_description = "📝 Unpublish selected assets"
    
    def create_default_license(self, request, queryset):
        """Create default CC0 license for resources without licenses"""
        from apps.licensing.models import License
        
        created_count = 0
        for resource in queryset:
            if not resource.licenses.filter(is_active=True).exists():
                License.objects.create(
                    resource=resource,
                    license_type='open',
                    terms='This work is released under CC0 - Public Domain. You may use it freely.',
                    requires_approval=False
                )
                created_count += 1
        
        self.message_user(
            request,
            f"Created default licenses for {created_count} assets."
        )
    create_default_license.short_description = "🌐 Create CC0 license for selected"
    
    def get_queryset(self, request):
        """Optimize queryset with select_related and prefetch_related"""
        return super().get_queryset(request).select_related(
            'publisher'
        ).prefetch_related(
            'licenses', 'distributions', 'distributions__access_requests'
        )


class DistributionAdminForm(forms.ModelForm):
    """Enhanced form for Distribution admin"""
    
    class Meta:
        model = Distribution
        fields = '__all__'
        widgets = {
            'access_config': forms.Textarea(attrs={'rows': 6, 'cols': 60, 'placeholder': '{"rate_limit": {"requests_per_hour": 1000}}'}),
            'metadata': forms.Textarea(attrs={'rows': 4, 'cols': 60, 'placeholder': '{"file_size": "2.5 MB", "format": "json"}'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Add help text
        self.fields['format_type'].help_text = (
            "How users can access this asset: "
            "ZIP for downloads, REST_JSON for API access"
        )
        self.fields['endpoint_url'].help_text = (
            "URL where the asset can be accessed or downloaded"
        )


@admin.register(Distribution)
class DistributionAdmin(admin.ModelAdmin):
    """Enhanced Admin configuration for Distribution model (Asset Download Formats)"""
    form = DistributionAdminForm
    
    list_display = [
        'asset_title', 'asset_category', 'format_display', 'version', 
        'endpoint_preview', 'access_type', 'access_requests_count', 'created_at'
    ]
    list_filter = [
        'format_type', 'is_active', 'created_at', 'resource__resource_type',
        'resource__workflow_status'
    ]
    search_fields = ['resource__title', 'endpoint_url', 'version']
    readonly_fields = ['id', 'created_at', 'updated_at', 'distribution_preview']
    ordering = ['-created_at']
    
    actions = ['create_access_requests', 'enable_distributions', 'disable_distributions']
    
    fieldsets = (
        ('Asset Download Format', {
            'fields': ('resource', 'format_type', 'version', 'endpoint_url'),
            'description': 'Configure how users can access this asset'
        }),
        ('Distribution Preview', {
            'fields': ('distribution_preview',),
            'description': 'Preview how this distribution appears in the API'
        }),
        ('Access Configuration', {
            'fields': ('access_config',),
            'classes': ('collapse',),
            'description': 'Rate limits and access controls'
        }),
        ('Technical Metadata', {
            'fields': ('metadata',),
            'classes': ('collapse',),
            'description': 'Technical details about the file/format'
        }),
        ('System Information', {
            'fields': ('id', 'is_active', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def asset_title(self, obj):
        """Display the asset title"""
        return obj.resource.title
    asset_title.short_description = 'Asset'
    
    def asset_category(self, obj):
        """Display asset category"""
        category_map = {
            'text': '📜 Mushaf',
            'tafsir': '📖 Tafsir', 
            'audio': '🎵 Recitation'
        }
        return category_map.get(obj.resource.resource_type, obj.resource.resource_type)
    asset_category.short_description = 'Category'
    
    def format_display(self, obj):
        """Display format type with icon"""
        format_icons = {
            'ZIP': '📦',
            'REST_JSON': '🔗',
            'GraphQL': '📊',
            'API': '⚡'
        }
        icon = format_icons.get(obj.format_type, '📄')
        return f"{icon} {obj.get_format_type_display()}"
    format_display.short_description = 'Format'
    
    def endpoint_preview(self, obj):
        """Display shortened endpoint URL"""
        if len(obj.endpoint_url) > 50:
            return format_html(
                '<span title="{}">{}<strong>...</strong></span>',
                obj.endpoint_url,
                obj.endpoint_url[:47]
            )
        return obj.endpoint_url
    endpoint_preview.short_description = 'Endpoint'
    
    def access_type(self, obj):
        """Display access configuration type"""
        requires_key = obj.access_config.get('requires_api_key', False)
        rate_limited = bool(obj.access_config.get('rate_limit'))
        
        if requires_key and rate_limited:
            return format_html('<span style="color: orange;">🔑 API Key + Rate Limited</span>')
        elif requires_key:
            return format_html('<span style="color: blue;">🔑 API Key Required</span>')
        elif rate_limited:
            return format_html('<span style="color: orange;">⏱️ Rate Limited</span>')
        else:
            return format_html('<span style="color: green;">🌐 Open Access</span>')
    access_type.short_description = 'Access Type'
    
    def access_requests_count(self, obj):
        """Display count of access requests for this distribution"""
        count = obj.access_requests.filter(is_active=True).count()
        if count > 0:
            url = reverse('admin:licensing_accessrequest_changelist')
            return format_html(
                '<a href="{}?distribution__id__exact={}">{} requests</a>',
                url, obj.id, count
            )
        return "0"
    access_requests_count.short_description = 'Access Requests'
    
    def distribution_preview(self, obj):
        """Preview how this distribution appears in asset download options"""
        if not obj.pk:
            return "Save the distribution first to see preview"
        
        preview_html = f"""
        <div style="background: #f8f9fa; padding: 15px; border-radius: 5px; font-family: monospace;">
            <strong>Asset Download Option:</strong><br><br>
            <strong>Format:</strong> {obj.get_format_type_display()}<br>
            <strong>Version:</strong> {obj.version}<br>
            <strong>Endpoint:</strong> <code>{obj.endpoint_url}</code><br>
            <strong>API Access:</strong> <code>/api/v1/assets/{obj.resource.id}/download</code><br><br>
            <em>Users will see this as a download option for the "{obj.resource.title}" asset.</em>
        </div>
        """
        return format_html(preview_html)
    distribution_preview.short_description = 'Download Preview'
    
    # Admin Actions
    def enable_distributions(self, request, queryset):
        """Enable selected distributions"""
        enabled_count = queryset.update(is_active=True)
        self.message_user(
            request,
            f"Successfully enabled {enabled_count} distributions."
        )
    enable_distributions.short_description = "✅ Enable selected distributions"
    
    def disable_distributions(self, request, queryset):
        """Disable selected distributions"""
        disabled_count = queryset.update(is_active=False)
        self.message_user(
            request,
            f"Successfully disabled {disabled_count} distributions."
        )
    disable_distributions.short_description = "❌ Disable selected distributions"
    
    def get_queryset(self, request):
        """Optimize queryset with select_related and prefetch_related"""
        return super().get_queryset(request).select_related(
            'resource', 'resource__publisher'
        ).prefetch_related(
            'access_requests'
        )


# Custom Admin Site Modifications for Asset Management
from django.contrib.admin import AdminSite
from django.contrib import admin
from django.urls import path
from django.shortcuts import render
from django.db.models import Count, Q


def assets_dashboard_view(request):
    """Custom dashboard view for asset management"""
    # Get statistics
    total_assets = Resource.objects.filter(is_active=True).count()
    published_assets = Resource.objects.filter(
        workflow_status='published', 
        published_at__isnull=False,
        is_active=True
    ).count()
    draft_assets = Resource.objects.filter(
        workflow_status='draft',
        is_active=True
    ).count()
    
    # Get assets by category
    assets_by_category = Resource.objects.filter(is_active=True).values(
        'resource_type'
    ).annotate(count=Count('id'))
    
    # Get recent assets
    recent_assets = Resource.objects.filter(
        is_active=True
    ).select_related('publisher').order_by('-created_at')[:5]
    
    # Get assets needing attention
    assets_no_license = Resource.objects.filter(
        is_active=True,
        licenses__isnull=True
    ).count()
    
    assets_no_distribution = Resource.objects.filter(
        is_active=True,
        distributions__isnull=True
    ).count()
    
    # Get pending access requests
    pending_requests = 0
    try:
        from apps.licensing.models import AccessRequest
        pending_requests = AccessRequest.objects.filter(
            status='pending',
            is_active=True
        ).count()
    except:
        pass
    
    context = {
        'title': 'Assets Dashboard',
        'total_assets': total_assets,
        'published_assets': published_assets,
        'draft_assets': draft_assets,
        'assets_by_category': assets_by_category,
        'recent_assets': recent_assets,
        'assets_no_license': assets_no_license,
        'assets_no_distribution': assets_no_distribution,
        'pending_requests': pending_requests,
    }
    
    return render(request, 'admin/content/assets_dashboard.html', context)


# Add dashboard to admin URLs
def get_urls_with_dashboard():
    """Add custom dashboard URL to admin"""
    original_get_urls = admin.site.get_urls
    
    def get_urls():
        urls = original_get_urls()
        custom_urls = [
            path('content/assets-dashboard/', assets_dashboard_view, name='assets_dashboard'),
        ]
        return custom_urls + urls
    
    return get_urls


# Replace admin site's get_urls method
admin.site.get_urls = get_urls_with_dashboard()