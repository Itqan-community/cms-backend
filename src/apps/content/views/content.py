"""
API ViewSets for Content models
"""
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema, OpenApiResponse
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q
from django.utils import timezone

from ..models import Resource, ResourceVersion, UsageEvent
from ..serializers import (
    ResourceSerializer
)
from apps.api.permissions import ResourcePermission


class ResourceViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Resource management
    """
    queryset = Resource.objects.all()
    permission_classes = [ResourcePermission]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['category', 'publishing_organization', 'is_active']
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'created_at', 'updated_at']
    ordering = ['-created_at']
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == 'list':
            return ResourceSerializer
        return ResourceSerializer
    
    def get_queryset(self):
        """Filter queryset based on user permissions"""
        queryset = Resource.objects.all()
        
        if self.request.user.is_admin() or self.request.user.is_reviewer():
            # Admin and Reviewers can see all resources
            return queryset
        elif self.request.user.is_publisher():
            # Publishers can see their own resources
            return queryset.filter(publisher=self.request.user)
        elif self.request.user.is_developer():
            # Developers can only see published resources
            return queryset.filter(published_at__isnull=False)
        
        return queryset.none()
    
    @action(detail=True, methods=['post'])
    def publish(self, request, pk=None):
        """Publish a resource"""
        resource = self.get_object()
        
        if resource.published_at:
            return Response(
                {'error': 'Resource is already published'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        resource.published_at = timezone.now()
        resource.save()
        
        serializer = self.get_serializer(resource)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def unpublish(self, request, pk=None):
        """Unpublish a resource"""
        resource = self.get_object()
        
        if not resource.published_at:
            return Response(
                {'error': 'Resource is not published'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        resource.published_at = None
        resource.save()
        
        serializer = self.get_serializer(resource)
        return Response(serializer.data)


class ResourceDownloadView(APIView):
    """
    API Endpoint: GET /resources/{resource_id}/download
    Download file of the latest Resource Version
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Download resource",
        description="Return a direct download URL for the latest ResourceVersion file. Auth required; no access policy.",
        responses={
            200: {
                'type': 'object',
                'properties': {
                    'download_url': {'type': 'string'},
                    'version': {'type': 'string', 'nullable': True}
                }
            },
            404: OpenApiResponse(description="Resource or file not found")
        }
    )
    def get(self, request, resource_id):
        try:
            resource = Resource.objects.get(id=resource_id)
        except Resource.DoesNotExist:
            return Response(
                {'error': {'code': 'RESOURCE_NOT_FOUND', 'message': 'Resource not found'}},
                status=status.HTTP_404_NOT_FOUND
            )

        latest_version = resource.get_latest_version()
        if not latest_version:
            return Response(
                {'error': {'code': 'RESOURCE_VERSION_NOT_FOUND', 'message': 'No versions found for this resource'}},
                status=status.HTTP_404_NOT_FOUND
            )

        # Ensure there is a stored file with a URL
        if not latest_version.storage_url or not getattr(latest_version.storage_url, 'url', None):
            return Response(
                {'error': {'code': 'DOWNLOAD_UNAVAILABLE', 'message': 'Download URL not available for the latest version'}},
                status=status.HTTP_404_NOT_FOUND
            )

        download_url = latest_version.storage_url.url

        # Track resource download event
        UsageEvent.track_resource_download(
            user=request.user,
            resource=resource,
            ip_address=self._get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )

        return Response({
            'download_url': download_url,
            'version': latest_version.semvar
        })

    def _get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0]
        return request.META.get('REMOTE_ADDR')
