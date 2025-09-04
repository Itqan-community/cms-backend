"""
API ViewSets for Content models
"""
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q
from django.utils import timezone

from ..models import Resource, Distribution
from ..serializers import (
    ResourceSerializer,
    DistributionSerializer
)
from apps.api.permissions import ResourcePermission, DistributionPermission


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


class DistributionViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Distribution management
    """
    queryset = Distribution.objects.all()
    serializer_class = DistributionSerializer
    permission_classes = [DistributionPermission]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['format_type', 'resource', 'is_active']
    search_fields = ['endpoint_url', 'version']
    ordering_fields = ['format_type', 'version', 'created_at', 'updated_at']
    ordering = ['-created_at']
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == 'list':
            return DistributionSerializer
        return DistributionSerializer
    
    def get_queryset(self):
        """Filter queryset based on user permissions"""
        queryset = Distribution.objects.all()
        
        if self.request.user.is_admin() or self.request.user.is_reviewer():
            # Admin and Reviewers can see all distributions
            return queryset
        elif self.request.user.is_publisher():
            # Publishers can see distributions for their resources
            return queryset.filter(resource__publisher=self.request.user)
        elif self.request.user.is_developer():
            # Developers can see distributions they have access to
            return queryset.filter(
                Q(access_requests__requester=self.request.user,
                  access_requests__status='approved',
                  access_requests__is_active=True) |
                Q(resource__published_at__isnull=False)  # Or published resources
            ).distinct()
        
        return queryset.none()
