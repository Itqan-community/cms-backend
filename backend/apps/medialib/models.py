"""
Media Library Models for Itqan CMS

Handles file uploads, storage metadata, and integrates with MinIO S3-compatible storage.
"""
import uuid
from django.db import models
from django.conf import settings
from django.core.validators import FileExtensionValidator
from django.utils.text import slugify
from apps.core.models import BaseModel


class MediaFile(BaseModel):
    """
    Media file storage with metadata and MinIO integration
    """
    MEDIA_TYPES = [
        ('image', 'Image'),
        ('audio', 'Audio'),
        ('video', 'Video'),
        ('document', 'Document'),
        ('archive', 'Archive'),
        ('other', 'Other'),
    ]
    
    # File metadata
    title = models.CharField(max_length=255, help_text="Display name for the file")
    description = models.TextField(blank=True, help_text="Optional description")
    file = models.FileField(
        upload_to='uploads/%Y/%m/%d/',
        validators=[
            FileExtensionValidator(
                allowed_extensions=[
                    # Images
                    'jpg', 'jpeg', 'png', 'gif', 'webp', 'svg',
                    # Audio
                    'mp3', 'wav', 'ogg', 'flac', 'm4a',
                    # Video  
                    'mp4', 'webm', 'avi', 'mov', 'mkv',
                    # Documents
                    'pdf', 'doc', 'docx', 'txt', 'rtf',
                    # Archives
                    'zip', 'tar', 'gz', 'rar',
                ]
            )
        ]
    )
    
    # File properties
    original_filename = models.CharField(max_length=255)
    file_size = models.PositiveIntegerField(help_text="File size in bytes")
    mime_type = models.CharField(max_length=100)
    media_type = models.CharField(max_length=20, choices=MEDIA_TYPES, default='other')
    
    # Image-specific fields
    width = models.PositiveIntegerField(null=True, blank=True)
    height = models.PositiveIntegerField(null=True, blank=True)
    
    # Audio/Video-specific fields
    duration = models.DurationField(null=True, blank=True)
    
    # Storage metadata
    storage_path = models.CharField(max_length=500, help_text="Full path in storage backend")
    storage_url = models.URLField(max_length=500, blank=True, help_text="Public URL for access")
    checksum = models.CharField(max_length=64, blank=True, help_text="SHA-256 checksum for integrity")
    
    # Relationships
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='uploaded_files'
    )
    
    # Categorization
    tags = models.JSONField(default=list, blank=True, help_text="Tags for categorization")
    folder = models.ForeignKey(
        'MediaFolder',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='files'
    )
    
    class Meta:
        db_table = 'media_files'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['media_type']),
            models.Index(fields=['uploaded_by']),
            models.Index(fields=['created_at']),
            models.Index(fields=['original_filename']),
        ]
        
    def __str__(self):
        return self.title or self.original_filename
    
    def save(self, *args, **kwargs):
        """Override save to set metadata"""
        if self.file:
            # Set original filename if not set
            if not self.original_filename:
                self.original_filename = self.file.name
            
            # Set title from filename if not set
            if not self.title:
                name = self.original_filename
                if '.' in name:
                    name = name.rsplit('.', 1)[0]
                self.title = name.replace('_', ' ').replace('-', ' ').title()
            
            # Set file size
            if hasattr(self.file, 'size'):
                self.file_size = self.file.size
            
            # Set storage path
            self.storage_path = self.file.name
            
            # Determine media type from extension
            if self.original_filename:
                ext = self.original_filename.lower().split('.')[-1]
                if ext in ['jpg', 'jpeg', 'png', 'gif', 'webp', 'svg']:
                    self.media_type = 'image'
                elif ext in ['mp3', 'wav', 'ogg', 'flac', 'm4a']:
                    self.media_type = 'audio'
                elif ext in ['mp4', 'webm', 'avi', 'mov', 'mkv']:
                    self.media_type = 'video'
                elif ext in ['pdf', 'doc', 'docx', 'txt', 'rtf']:
                    self.media_type = 'document'
                elif ext in ['zip', 'tar', 'gz', 'rar']:
                    self.media_type = 'archive'
        
        super().save(*args, **kwargs)
    
    @property
    def file_url(self):
        """Get the public URL for this file"""
        if self.storage_url:
            return self.storage_url
        elif self.file:
            return self.file.url
        return None
    
    @property
    def human_readable_size(self):
        """Return file size in human readable format"""
        if not self.file_size:
            return "Unknown size"
        
        size = self.file_size
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"
    
    @property
    def is_image(self):
        return self.media_type == 'image'
    
    @property
    def is_audio(self):
        return self.media_type == 'audio'
    
    @property
    def is_video(self):
        return self.media_type == 'video'


class MediaFolder(BaseModel):
    """
    Hierarchical folder structure for organizing media files
    """
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    description = models.TextField(blank=True)
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children'
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='created_folders'
    )
    
    class Meta:
        db_table = 'media_folders'
        ordering = ['name']
        unique_together = [['parent', 'slug']]
        
    def __str__(self):
        if self.parent:
            return f"{self.parent} / {self.name}"
        return self.name
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)
    
    @property
    def full_path(self):
        """Get the full path of this folder"""
        if self.parent:
            return f"{self.parent.full_path}/{self.name}"
        return self.name
    
    def get_file_count(self):
        """Get total number of files in this folder and subfolders"""
        count = self.files.count()
        for child in self.children.all():
            count += child.get_file_count()
        return count


class MediaAttachment(BaseModel):
    """
    Links media files to other models (Resources, etc.)
    """
    media_file = models.ForeignKey(MediaFile, on_delete=models.CASCADE)
    content_type = models.ForeignKey('contenttypes.ContentType', on_delete=models.CASCADE)
    object_id = models.UUIDField()
    
    # Attachment metadata
    purpose = models.CharField(
        max_length=50,
        choices=[
            ('featured', 'Featured Image'),
            ('gallery', 'Gallery Image'),
            ('audio', 'Audio Content'),
            ('document', 'Document Attachment'),
            ('thumbnail', 'Thumbnail'),
            ('cover', 'Cover Image'),
            ('other', 'Other'),
        ],
        default='other'
    )
    order = models.PositiveIntegerField(default=0, help_text="Display order")
    
    class Meta:
        db_table = 'media_attachments'
        ordering = ['order', 'created_at']
        indexes = [
            models.Index(fields=['content_type', 'object_id']),
            models.Index(fields=['purpose']),
        ]
        
    def __str__(self):
        return f"{self.media_file.title} -> {self.content_type.model}"