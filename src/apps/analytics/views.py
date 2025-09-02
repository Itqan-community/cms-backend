"""
API ViewSets for Analytics models
"""
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Sum
from django.utils import timezone
from datetime import timedelta

from .models import UsageEvent
from .serializers import (
    UsageEventSerializer, UsageEventListSerializer,
    UsageStatsSerializer, DailyUsageStatsSerializer
)
from apps.api.permissions import UsageEventPermission


class UsageEventViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for UsageEvent analytics (read-only)
    """
    queryset = UsageEvent.objects.all()
    permission_classes = [UsageEventPermission]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['event_type', 'user', 'resource', 'distribution']
    search_fields = ['endpoint', 'ip_address']
    ordering_fields = ['occurred_at', 'created_at']
    ordering = ['-occurred_at']
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == 'list':
            return UsageEventListSerializer
        return UsageEventSerializer
    
    def get_queryset(self):
        """Filter queryset based on user permissions"""
        queryset = UsageEvent.objects.all()
        
        if self.request.user.is_admin():
            # Admin can see all events
            return queryset
        elif self.request.user.is_publisher():
            # Publishers can see events for their resources
            return queryset.filter(resource__publisher=self.request.user)
        elif self.request.user.is_developer():
            # Developers can see their own events
            return queryset.filter(user=self.request.user)
        
        return queryset.none()
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Get usage statistics"""
        queryset = self.get_queryset()
        
        # Get date range from query params
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        
        if start_date:
            try:
                start_date = timezone.datetime.fromisoformat(start_date)
                queryset = queryset.filter(occurred_at__gte=start_date)
            except ValueError:
                pass
        
        if end_date:
            try:
                end_date = timezone.datetime.fromisoformat(end_date)
                queryset = queryset.filter(occurred_at__lte=end_date)
            except ValueError:
                pass
        
        # Calculate stats
        stats = UsageEvent.get_user_usage_stats(
            request.user,
            start_date=start_date,
            end_date=end_date
        ) if request.user.is_developer() else {
            'total_events': queryset.count(),
            'api_calls': queryset.filter(event_type='api_call').count(),
            'downloads': queryset.filter(event_type='download').count(),
            'views': queryset.filter(event_type='view').count(),
            'total_bandwidth': queryset.aggregate(
                total=Sum('request_size') + Sum('response_size')
            )['total'] or 0,
        }
        
        serializer = UsageStatsSerializer(stats)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def daily_stats(self, request):
        """Get daily usage statistics"""
        # Default to last 30 days
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=30)
        
        # Override with query params if provided
        if request.query_params.get('start_date'):
            try:
                start_date = timezone.datetime.fromisoformat(
                    request.query_params['start_date']
                ).date()
            except ValueError:
                pass
        
        if request.query_params.get('end_date'):
            try:
                end_date = timezone.datetime.fromisoformat(
                    request.query_params['end_date']
                ).date()
            except ValueError:
                pass
        
        daily_stats = UsageEvent.get_daily_stats(start_date, end_date)
        serializer = DailyUsageStatsSerializer(daily_stats, many=True)
        return Response(serializer.data)