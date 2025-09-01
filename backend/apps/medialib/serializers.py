"""
Media Library Serializers for Itqan CMS API
"""
from rest_framework import serializers
from .models import MediaFile, MediaFolder, MediaAttachment


class MediaFolderSerializer(serializers.ModelSerializer):
    """Serializer for media folders"""
    file_count = serializers.ReadOnlyField(source='get_file_count')
    full_path = serializers.ReadOnlyField()
    
    class Meta:
        model = MediaFolder
        fields = [
            'id', 'name', 'slug', 'description', 'parent', 
            'full_path', 'file_count', 'created_by', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'slug', 'created_by', 'created_at', 'updated_at']


class MediaFileSerializer(serializers.ModelSerializer):
    """Serializer for media files"""
    file_url = serializers.ReadOnlyField()
    human_readable_size = serializers.ReadOnlyField()
    folder_name = serializers.CharField(source='folder.name', read_only=True)
    uploaded_by_name = serializers.CharField(source='uploaded_by.get_full_name', read_only=True)
    
    class Meta:
        model = MediaFile
        fields = [
            'id', 'title', 'description', 'file', 'file_url',
            'original_filename', 'file_size', 'human_readable_size',
            'mime_type', 'media_type', 'width', 'height', 'duration',
            'storage_path', 'storage_url', 'checksum',
            'folder', 'folder_name', 'tags',
            'uploaded_by', 'uploaded_by_name',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'original_filename', 'file_size', 'mime_type', 
            'storage_path', 'storage_url', 'checksum',
            'width', 'height', 'duration', 'uploaded_by',
            'created_at', 'updated_at'
        ]


class MediaFileUploadSerializer(serializers.ModelSerializer):
    """Simplified serializer for file uploads"""
    
    class Meta:
        model = MediaFile
        fields = ['file', 'title', 'description', 'folder', 'tags']
        
    def create(self, validated_data):
        # Set the uploaded_by field from the request user
        validated_data['uploaded_by'] = self.context['request'].user
        return super().create(validated_data)


class MediaAttachmentSerializer(serializers.ModelSerializer):
    """Serializer for media attachments"""
    media_file_data = MediaFileSerializer(source='media_file', read_only=True)
    
    class Meta:
        model = MediaAttachment
        fields = [
            'id', 'media_file', 'media_file_data',
            'content_type', 'object_id', 'purpose', 'order',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
