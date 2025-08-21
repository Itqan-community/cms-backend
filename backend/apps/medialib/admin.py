"""
Media Library Admin Interface for Itqan CMS
"""
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import MediaFile, MediaFolder, MediaAttachment


@admin.register(MediaFolder)
class MediaFolderAdmin(admin.ModelAdmin):
    """Admin interface for media folders"""
    list_display = ['name', 'parent', 'file_count', 'created_by', 'created_at']
    list_filter = ['created_at', 'created_by']
    search_fields = ['name', 'description']
    prepopulated_fields = {'slug': ('name',)}
    autocomplete_fields = ['parent', 'created_by']
    
    def file_count(self, obj):
        return obj.get_file_count()
    file_count.short_description = 'Files'


@admin.register(MediaFile)
class MediaFileAdmin(admin.ModelAdmin):
    """Admin interface for media files"""
    list_display = [
        'title', 
        'media_type', 
        'file_preview', 
        'human_readable_size', 
        'folder',
        'uploaded_by', 
        'created_at'
    ]
    list_filter = [
        'media_type', 
        'created_at', 
        'uploaded_by',
        'folder'
    ]
    search_fields = ['title', 'original_filename', 'description']
    readonly_fields = [
        'file_preview', 
        'storage_path', 
        'storage_url',
        'file_size', 
        'mime_type',
        'checksum',
        'width',
        'height',
        'duration'
    ]
    autocomplete_fields = ['uploaded_by', 'folder']
    fieldsets = [
        ('Basic Information', {
            'fields': ['title', 'description', 'file', 'folder']
        }),
        ('File Properties', {
            'fields': [
                'original_filename',
                'file_size',
                'mime_type', 
                'media_type'
            ],
            'classes': ['collapse']
        }),
        ('Media Dimensions', {
            'fields': ['width', 'height', 'duration'],
            'classes': ['collapse']
        }),
        ('Storage Information', {
            'fields': [
                'storage_path',
                'storage_url', 
                'checksum'
            ],
            'classes': ['collapse']
        }),
        ('Metadata', {
            'fields': ['tags', 'uploaded_by'],
            'classes': ['collapse']
        }),
        ('Preview', {
            'fields': ['file_preview'],
            'classes': ['wide']
        })
    ]
    
    def file_preview(self, obj):
        """Display file preview in admin"""
        if not obj.file:
            return "No file"
        
        file_url = obj.file_url
        if not file_url:
            return "No URL available"
        
        if obj.is_image:
            return format_html(
                '<img src="{}" style="max-height: 200px; max-width: 300px;" />',
                file_url
            )
        elif obj.is_audio:
            return format_html(
                '<audio controls><source src="{}" type="{}"></audio>',
                file_url,
                obj.mime_type
            )
        elif obj.is_video:
            return format_html(
                '<video controls style="max-width: 300px;"><source src="{}" type="{}"></video>',
                file_url,
                obj.mime_type
            )
        else:
            return format_html(
                '<a href="{}" target="_blank">📄 {}</a>',
                file_url,
                obj.original_filename
            )
    
    file_preview.short_description = 'Preview'
    
    def human_readable_size(self, obj):
        return obj.human_readable_size
    human_readable_size.short_description = 'Size'
    
    def save_model(self, request, obj, form, change):
        """Auto-set the uploaded_by field"""
        if not change:  # Only for new objects
            obj.uploaded_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(MediaAttachment)
class MediaAttachmentAdmin(admin.ModelAdmin):
    """Admin interface for media attachments"""
    list_display = [
        'media_file', 
        'purpose', 
        'content_type', 
        'object_id', 
        'order',
        'created_at'
    ]
    list_filter = ['purpose', 'content_type', 'created_at']
    search_fields = ['media_file__title', 'media_file__original_filename']
    autocomplete_fields = ['media_file']
    ordering = ['content_type', 'object_id', 'order']


# Inline admin for attachments
class MediaAttachmentInline(admin.TabularInline):
    """Inline admin for media attachments"""
    model = MediaAttachment
    extra = 1
    autocomplete_fields = ['media_file']
    fields = ['media_file', 'purpose', 'order']