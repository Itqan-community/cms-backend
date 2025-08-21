"""
Media Library API Views for Itqan CMS
"""
import hashlib
from django.core.files.uploadedfile import InMemoryUploadedFile
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from drf_spectacular.utils import extend_schema, extend_schema_view

from .models import MediaFile, MediaFolder, MediaAttachment
from .serializers import (
    MediaFileSerializer, 
    MediaFileUploadSerializer,
    MediaFolderSerializer, 
    MediaAttachmentSerializer
)


@extend_schema_view(
    list=extend_schema(summary="List media folders"),
    create=extend_schema(summary="Create media folder"),
    retrieve=extend_schema(summary="Get media folder"),
    update=extend_schema(summary="Update media folder"),
    destroy=extend_schema(summary="Delete media folder"),
)
class MediaFolderViewSet(viewsets.ModelViewSet):
    """API endpoints for media folders"""
    queryset = MediaFolder.objects.all()
    serializer_class = MediaFolderSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'created_at']
    ordering = ['name']
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


@extend_schema_view(
    list=extend_schema(summary="List media files"),
    create=extend_schema(summary="Upload media file"),
    retrieve=extend_schema(summary="Get media file"),
    update=extend_schema(summary="Update media file"),
    destroy=extend_schema(summary="Delete media file"),
)
class MediaFileViewSet(viewsets.ModelViewSet):
    """API endpoints for media files"""
    queryset = MediaFile.objects.all()
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['media_type', 'folder', 'uploaded_by']
    search_fields = ['title', 'original_filename', 'description']
    ordering_fields = ['title', 'file_size', 'created_at']
    ordering = ['-created_at']
    
    def get_serializer_class(self):
        if self.action == 'create':
            return MediaFileUploadSerializer
        return MediaFileSerializer
    
    def create(self, request, *args, **kwargs):
        """Handle file upload with metadata extraction"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Extract file metadata before saving
        file_obj = serializer.validated_data.get('file')
        if file_obj:
            # Calculate checksum
            if isinstance(file_obj, InMemoryUploadedFile):
                file_obj.seek(0)
                checksum = hashlib.sha256(file_obj.read()).hexdigest()
                file_obj.seek(0)
                serializer.validated_data['checksum'] = checksum
            
            # Set MIME type if not set
            if hasattr(file_obj, 'content_type'):
                serializer.validated_data['mime_type'] = file_obj.content_type
        
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        
        # Return full file data
        file_instance = serializer.instance
        response_serializer = MediaFileSerializer(file_instance, context={'request': request})
        return Response(response_serializer.data, status=status.HTTP_201_CREATED, headers=headers)
    
    @extend_schema(
        summary="Bulk upload multiple files",
        request=MediaFileUploadSerializer(many=True)
    )
    @action(detail=False, methods=['post'], parser_classes=[MultiPartParser, FormParser])
    def bulk_upload(self, request):
        """Upload multiple files at once"""
        files = request.FILES.getlist('files')
        folder_id = request.data.get('folder')
        
        if not files:
            return Response(
                {'error': 'No files provided'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        uploaded_files = []
        errors = []
        
        for file_obj in files:
            try:
                # Create media file instance
                data = {
                    'file': file_obj,
                    'folder': folder_id,
                    'title': file_obj.name.rsplit('.', 1)[0] if '.' in file_obj.name else file_obj.name
                }
                
                serializer = MediaFileUploadSerializer(data=data, context={'request': request})
                if serializer.is_valid():
                    # Add checksum
                    if hasattr(file_obj, 'read'):
                        file_obj.seek(0)
                        checksum = hashlib.sha256(file_obj.read()).hexdigest()
                        file_obj.seek(0)
                        serializer.validated_data['checksum'] = checksum
                    
                    # Set MIME type
                    if hasattr(file_obj, 'content_type'):
                        serializer.validated_data['mime_type'] = file_obj.content_type
                    
                    instance = serializer.save()
                    file_serializer = MediaFileSerializer(instance, context={'request': request})
                    uploaded_files.append(file_serializer.data)
                else:
                    errors.append({
                        'filename': file_obj.name,
                        'errors': serializer.errors
                    })
            except Exception as e:
                errors.append({
                    'filename': file_obj.name,
                    'errors': str(e)
                })
        
        response_data = {
            'uploaded': uploaded_files,
            'errors': errors,
            'total_uploaded': len(uploaded_files),
            'total_errors': len(errors)
        }
        
        return Response(response_data, status=status.HTTP_207_MULTI_STATUS)
    
    @extend_schema(
        summary="Get media file statistics",
        responses={200: {
            'type': 'object',
            'properties': {
                'total_files': {'type': 'integer'},
                'total_size': {'type': 'integer'},
                'by_type': {'type': 'object'},
                'recent_uploads': {'type': 'array'}
            }
        }}
    )
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Get media library statistics"""
        queryset = self.get_queryset()
        user_files = queryset.filter(uploaded_by=request.user)
        
        # Basic stats
        total_files = user_files.count()
        total_size = sum(f.file_size or 0 for f in user_files)
        
        # Files by type
        by_type = {}
        for media_type, _ in MediaFile.MEDIA_TYPES:
            count = user_files.filter(media_type=media_type).count()
            if count > 0:
                by_type[media_type] = count
        
        # Recent uploads (last 10)
        recent_files = user_files.order_by('-created_at')[:10]
        recent_serializer = MediaFileSerializer(recent_files, many=True, context={'request': request})
        
        return Response({
            'total_files': total_files,
            'total_size': total_size,
            'by_type': by_type,
            'recent_uploads': recent_serializer.data
        })


@extend_schema_view(
    list=extend_schema(summary="List media attachments"),
    create=extend_schema(summary="Create media attachment"),
    retrieve=extend_schema(summary="Get media attachment"),
    update=extend_schema(summary="Update media attachment"),
    destroy=extend_schema(summary="Delete media attachment"),
)
class MediaAttachmentViewSet(viewsets.ModelViewSet):
    """API endpoints for media attachments"""
    queryset = MediaAttachment.objects.all()
    serializer_class = MediaAttachmentSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['content_type', 'object_id', 'purpose']
    ordering_fields = ['order', 'created_at']
    ordering = ['order', 'created_at']