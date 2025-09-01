"""
API views for API key management
"""
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Count, Q
from django.utils import timezone
from datetime import timedelta
from drf_spectacular.utils import extend_schema, OpenApiParameter

from .models import APIKey, APIKeyUsage, RateLimitEvent
from .serializers import (
    APIKeySerializer, APIKeyCreateSerializer, APIKeyListSerializer,
    APIKeyUsageSerializer, RateLimitEventSerializer, APIKeyStatsSerializer
)
from apps.accounts.permissions import IsAdminOrOwner, IsAdminUser


class APIKeyViewSet(viewsets.ModelViewSet):
    """
    ViewSet for API key management
    """
    permission_classes = [IsAdminOrOwner]
    lookup_field = 'id'
    
    def get_queryset(self):
        """Filter API keys based on user permissions"""
        if self.request.user.is_admin():
            return APIKey.objects.all()
        else:
            return APIKey.objects.filter(user=self.request.user)
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == 'create':
            return APIKeyCreateSerializer
        elif self.action == 'list':
            return APIKeyListSerializer
        return APIKeySerializer
    
    def perform_create(self, serializer):
        """Create new API key"""
        # Generate the API key
        api_key, full_key = APIKey.generate_key(
            user=self.request.user,
            name=serializer.validated_data['name'],
            description=serializer.validated_data.get('description', ''),
            expires_in_days=serializer.validated_data.get('expires_in_days'),
            rate_limit=serializer.validated_data.get('rate_limit', 1000)
        )
        
        # Store the full key in the serializer context for response
        serializer.instance = api_key
        serializer.context['full_key'] = full_key
    
    def create(self, request, *args, **kwargs):
        """Create new API key and return the full key"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        
        # Return the API key details with the full key
        response_data = APIKeySerializer(serializer.instance).data
        response_data['full_key'] = serializer.context['full_key']
        
        return Response(response_data, status=status.HTTP_201_CREATED)
    
    @extend_schema(
        summary="Revoke API key",
        description="Revoke an API key to prevent further usage",
        request={'type': 'object', 'properties': {'reason': {'type': 'string'}}},
        responses={200: APIKeySerializer}
    )
    @action(detail=True, methods=['post'])
    def revoke(self, request, id=None):
        """Revoke an API key"""
        api_key = self.get_object()
        
        if api_key.is_revoked():
            return Response(
                {'error': 'API key is already revoked'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        reason = request.data.get('reason', 'Revoked via API')
        api_key.revoke(revoked_by=request.user, reason=reason)
        
        serializer = self.get_serializer(api_key)
        return Response(serializer.data)
    
    @extend_schema(
        summary="Get API key usage statistics",
        description="Get usage statistics for the API key",
        parameters=[
            OpenApiParameter(name='days', type=int, location=OpenApiParameter.QUERY, default=30),
        ],
        responses={200: APIKeyStatsSerializer}
    )
    @action(detail=True, methods=['get'])
    def stats(self, request, id=None):
        """Get usage statistics for an API key"""
        api_key = self.get_object()
        days = int(request.query_params.get('days', 30))
        
        # Get usage stats
        usage_stats = api_key.get_usage_stats(days=days)
        
        # Get additional statistics
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        total_requests = APIKeyUsage.objects.filter(
            api_key=api_key,
            created_at__range=[start_date, end_date]
        ).count()
        
        error_requests = APIKeyUsage.objects.filter(
            api_key=api_key,
            created_at__range=[start_date, end_date],
            status_code__gte=400
        ).count()
        
        rate_limit_violations = RateLimitEvent.objects.filter(
            api_key=api_key,
            created_at__range=[start_date, end_date]
        ).count()
        
        # Top endpoints
        top_endpoints = APIKeyUsage.objects.filter(
            api_key=api_key,
            created_at__range=[start_date, end_date]
        ).values('endpoint').annotate(
            requests=Count('id')
        ).order_by('-requests')[:10]
        
        stats_data = {
            'api_key_id': api_key.id,
            'total_requests': total_requests,
            'error_requests': error_requests,
            'error_rate': (error_requests / total_requests * 100) if total_requests > 0 else 0,
            'rate_limit_violations': rate_limit_violations,
            'daily_usage': usage_stats,
            'top_endpoints': list(top_endpoints),
            'period_days': days
        }
        
        serializer = APIKeyStatsSerializer(data=stats_data)
        serializer.is_valid()
        return Response(serializer.data)
    
    @extend_schema(
        summary="Regenerate API key",
        description="Generate a new key for this API key record",
        responses={200: APIKeySerializer}
    )
    @action(detail=True, methods=['post'])
    def regenerate(self, request, id=None):
        """Regenerate the API key"""
        api_key = self.get_object()
        
        if api_key.is_revoked():
            return Response(
                {'error': 'Cannot regenerate a revoked API key'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Generate new key
        new_api_key, full_key = APIKey.generate_key(
            user=api_key.user,
            name=api_key.name,
            description=api_key.description,
            expires_in_days=None,  # Keep existing expiration logic
            rate_limit=api_key.rate_limit
        )
        
        # Copy settings from old key
        new_api_key.permissions = api_key.permissions
        new_api_key.allowed_ips = api_key.allowed_ips
        new_api_key.expires_at = api_key.expires_at
        new_api_key.save()
        
        # Revoke old key
        api_key.revoke(
            revoked_by=request.user,
            reason=f"Regenerated as new key {new_api_key.id}"
        )
        
        # Return new key details with full key
        response_data = APIKeySerializer(new_api_key).data
        response_data['full_key'] = full_key
        
        return Response(response_data)


class APIKeyUsageViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for API key usage logs (read-only)
    """
    serializer_class = APIKeyUsageSerializer
    permission_classes = [IsAdminOrOwner]
    filterset_fields = ['api_key', 'endpoint', 'method', 'status_code']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Filter usage logs based on user permissions"""
        if self.request.user.is_admin():
            return APIKeyUsage.objects.all()
        else:
            # Users can only see usage logs for their own API keys
            return APIKeyUsage.objects.filter(api_key__user=self.request.user)


class RateLimitEventViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for rate limit events (read-only)
    """
    serializer_class = RateLimitEventSerializer
    permission_classes = [IsAdminUser]  # Only admins can see rate limit events
    filterset_fields = ['api_key', 'limit_type', 'ip_address']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Return all rate limit events for admins"""
        return RateLimitEvent.objects.all()


class APIKeyStatisticsViewSet(viewsets.ViewSet):
    """
    ViewSet for API key statistics and analytics
    """
    permission_classes = [IsAdminUser]
    
    @extend_schema(
        summary="Get global API statistics",
        description="Get system-wide API key and usage statistics",
        responses={200: {'type': 'object'}}
    )
    @action(detail=False, methods=['get'])
    def global_stats(self, request):
        """Get global API key statistics"""
        # API key statistics
        total_keys = APIKey.objects.count()
        active_keys = APIKey.objects.filter(
            is_active=True,
            revoked_at__isnull=True
        ).count()
        expired_keys = APIKey.objects.filter(
            expires_at__lt=timezone.now()
        ).count()
        revoked_keys = APIKey.objects.filter(
            revoked_at__isnull=False
        ).count()
        
        # Usage statistics (last 30 days)
        end_date = timezone.now()
        start_date = end_date - timedelta(days=30)
        
        total_requests = APIKeyUsage.objects.filter(
            created_at__range=[start_date, end_date]
        ).count()
        
        error_requests = APIKeyUsage.objects.filter(
            created_at__range=[start_date, end_date],
            status_code__gte=400
        ).count()
        
        rate_limit_events = RateLimitEvent.objects.filter(
            created_at__range=[start_date, end_date]
        ).count()
        
        # Top API keys by usage
        top_keys = APIKeyUsage.objects.filter(
            created_at__range=[start_date, end_date]
        ).values('api_key__name', 'api_key__id').annotate(
            requests=Count('id')
        ).order_by('-requests')[:10]
        
        # Daily request volume
        daily_requests = APIKeyUsage.objects.filter(
            created_at__range=[start_date, end_date]
        ).extra({
            'date': 'DATE(created_at)'
        }).values('date').annotate(
            requests=Count('id')
        ).order_by('date')
        
        return Response({
            'api_keys': {
                'total': total_keys,
                'active': active_keys,
                'expired': expired_keys,
                'revoked': revoked_keys
            },
            'usage_last_30_days': {
                'total_requests': total_requests,
                'error_requests': error_requests,
                'error_rate': (error_requests / total_requests * 100) if total_requests > 0 else 0,
                'rate_limit_events': rate_limit_events
            },
            'top_api_keys': list(top_keys),
            'daily_requests': list(daily_requests)
        })
