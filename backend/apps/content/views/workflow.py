"""
Workflow management views for Itqan CMS
"""
from rest_framework import status, permissions
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet
from django.shortcuts import get_object_or_404
from django.db.models import Q, Count
from drf_spectacular.utils import extend_schema, OpenApiParameter

from ..models import Resource
from ..serializers import ResourceSerializer
from apps.api.permissions import IsPublisherOwnerOrReviewer, IsReviewerOrAdmin


class WorkflowViewSet(ViewSet):
    """
    ViewSet for managing Resource workflow transitions
    """
    permission_classes = [permissions.IsAuthenticated]
    
    @extend_schema(
        summary="Get workflow dashboard statistics",
        description="Get overview of resources by workflow status for current user",
        responses={200: {
            'type': 'object',
            'properties': {
                'stats': {
                    'type': 'object',
                    'properties': {
                        'draft': {'type': 'integer'},
                        'in_review': {'type': 'integer'},
                        'reviewed': {'type': 'integer'},
                        'published': {'type': 'integer'},
                        'rejected': {'type': 'integer'}
                    }
                },
                'user_role': {'type': 'string'},
                'permissions': {
                    'type': 'object',
                    'properties': {
                        'can_review': {'type': 'boolean'},
                        'can_publish': {'type': 'boolean'}
                    }
                }
            }
        }}
    )
    @action(detail=False, methods=['get'])
    def dashboard(self, request):
        """Get workflow dashboard statistics"""
        user = request.user
        
        # Base queryset based on user role
        if user.is_reviewer() or user.is_admin():
            # Reviewers and admins can see all resources
            base_queryset = Resource.objects.filter(is_active=True)
        else:
            # Publishers can only see their own resources
            base_queryset = Resource.objects.filter(publisher=user, is_active=True)
        
        # Get counts by status
        stats = {}
        for status_code, _ in Resource.WORKFLOW_STATUS_CHOICES:
            stats[status_code] = base_queryset.filter(workflow_status=status_code).count()
        
        # User permissions
        permissions = {
            'can_review': user.is_reviewer() or user.is_admin(),
            'can_publish': user.is_reviewer() or user.is_admin(),
            'can_create': user.is_publisher() or user.is_admin(),
        }
        
        return Response({
            'stats': stats,
            'user_role': user.role.name if user.role else 'unknown',
            'permissions': permissions
        })
    
    @extend_schema(
        summary="Get resources by workflow status",
        description="Get list of resources filtered by workflow status",
        parameters=[
            OpenApiParameter(name='status', description='Workflow status', required=True, type=str),
            OpenApiParameter(name='limit', description='Number of results to return', required=False, type=int),
            OpenApiParameter(name='offset', description='Starting point for results', required=False, type=int),
        ],
        responses={200: ResourceSerializer(many=True)}
    )
    @action(detail=False, methods=['get'])
    def by_status(self, request):
        """Get resources by workflow status"""
        status = request.query_params.get('status')
        if not status:
            return Response({'error': 'Status parameter is required'}, 
                          status=status.HTTP_400_BAD_REQUEST)
        
        user = request.user
        limit = int(request.query_params.get('limit', 20))
        offset = int(request.query_params.get('offset', 0))
        
        # Base queryset based on user role
        if user.is_reviewer() or user.is_admin():
            queryset = Resource.objects.filter(is_active=True)
        else:
            queryset = Resource.objects.filter(publisher=user, is_active=True)
        
        # Filter by status
        queryset = queryset.filter(workflow_status=status)
        
        # Apply pagination
        total = queryset.count()
        resources = queryset[offset:offset + limit]
        
        serializer = ResourceSerializer(resources, many=True, context={'request': request})
        
        return Response({
            'results': serializer.data,
            'count': total,
            'next': f'?status={status}&limit={limit}&offset={offset + limit}' if offset + limit < total else None,
            'previous': f'?status={status}&limit={limit}&offset={max(0, offset - limit)}' if offset > 0 else None
        })
    
    @extend_schema(
        summary="Submit resource for review",
        description="Submit a draft resource for editorial review",
        request={'type': 'object', 'properties': {}},
        responses={200: ResourceSerializer}
    )
    @action(detail=True, methods=['post'], permission_classes=[IsPublisherOwnerOrReviewer])
    def submit_for_review(self, request, pk=None):
        """Submit resource for review"""
        resource = get_object_or_404(Resource, pk=pk, is_active=True)
        
        try:
            resource.submit_for_review(request.user)
            serializer = ResourceSerializer(resource, context={'request': request})
            return Response(serializer.data)
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
    @extend_schema(
        summary="Approve resource",
        description="Approve a resource in review (Reviewer/Admin only)",
        request={
            'type': 'object',
            'properties': {
                'notes': {'type': 'string', 'description': 'Review notes'}
            }
        },
        responses={200: ResourceSerializer}
    )
    @action(detail=True, methods=['post'], permission_classes=[IsReviewerOrAdmin])
    def approve(self, request, pk=None):
        """Approve resource review"""
        resource = get_object_or_404(Resource, pk=pk, is_active=True)
        notes = request.data.get('notes', '')
        
        try:
            resource.approve_review(request.user, notes)
            serializer = ResourceSerializer(resource, context={'request': request})
            return Response(serializer.data)
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
    @extend_schema(
        summary="Reject resource",
        description="Reject a resource in review (Reviewer/Admin only)",
        request={
            'type': 'object',
            'properties': {
                'notes': {'type': 'string', 'description': 'Rejection reason', 'required': True}
            }
        },
        responses={200: ResourceSerializer}
    )
    @action(detail=True, methods=['post'], permission_classes=[IsReviewerOrAdmin])
    def reject(self, request, pk=None):
        """Reject resource review"""
        resource = get_object_or_404(Resource, pk=pk, is_active=True)
        notes = request.data.get('notes', '')
        
        if not notes:
            return Response({'error': 'Rejection notes are required'}, 
                          status=status.HTTP_400_BAD_REQUEST)
        
        try:
            resource.reject_review(request.user, notes)
            serializer = ResourceSerializer(resource, context={'request': request})
            return Response(serializer.data)
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
    @extend_schema(
        summary="Publish resource",
        description="Publish an approved resource (Reviewer/Admin only)",
        request={'type': 'object', 'properties': {}},
        responses={200: ResourceSerializer}
    )
    @action(detail=True, methods=['post'], permission_classes=[IsReviewerOrAdmin])
    def publish(self, request, pk=None):
        """Publish approved resource"""
        resource = get_object_or_404(Resource, pk=pk, is_active=True)
        
        try:
            resource.publish_resource(request.user)
            serializer = ResourceSerializer(resource, context={'request': request})
            return Response(serializer.data)
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
    @extend_schema(
        summary="Reset resource to draft",
        description="Reset resource to draft status (Owner/Admin only)",
        request={'type': 'object', 'properties': {}},
        responses={200: ResourceSerializer}
    )
    @action(detail=True, methods=['post'], permission_classes=[IsPublisherOwnerOrReviewer])
    def reset_to_draft(self, request, pk=None):
        """Reset resource to draft status"""
        resource = get_object_or_404(Resource, pk=pk, is_active=True)
        
        try:
            resource.reset_to_draft(request.user)
            serializer = ResourceSerializer(resource, context={'request': request})
            return Response(serializer.data)
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
    @extend_schema(
        summary="Get workflow history",
        description="Get complete workflow history for a resource",
        responses={200: {
            'type': 'object',
            'properties': {
                'history': {
                    'type': 'array',
                    'items': {
                        'type': 'object',
                        'properties': {
                            'status': {'type': 'string'},
                            'timestamp': {'type': 'string', 'format': 'date-time'},
                            'user': {'type': 'string'},
                            'notes': {'type': 'string'}
                        }
                    }
                }
            }
        }}
    )
    @action(detail=True, methods=['get'])
    def history(self, request, pk=None):
        """Get workflow history for resource"""
        resource = get_object_or_404(Resource, pk=pk, is_active=True)
        
        # Check permissions - users can only see history of their own resources or if they're reviewers
        if not (resource.publisher == request.user or 
                request.user.is_reviewer() or 
                request.user.is_admin()):
            return Response({'error': 'Permission denied'}, 
                          status=status.HTTP_403_FORBIDDEN)
        
        history = resource.get_workflow_history()
        
        # Format history for API response
        formatted_history = []
        for entry in history:
            formatted_history.append({
                'status': entry['status'],
                'timestamp': entry['timestamp'].isoformat(),
                'user': entry['user'].get_full_name() if entry['user'] else 'System',
                'user_email': entry['user'].email if entry['user'] else '',
                'notes': entry['notes']
            })
        
        return Response({'history': formatted_history})


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
@extend_schema(
    summary="Get workflow permissions for user",
    description="Get current user's workflow permissions and capabilities",
    responses={200: {
        'type': 'object',
        'properties': {
            'user_role': {'type': 'string'},
            'can_create': {'type': 'boolean'},
            'can_review': {'type': 'boolean'},
            'can_publish': {'type': 'boolean'},
            'can_admin': {'type': 'boolean'}
        }
    }}
)
def workflow_permissions(request):
    """Get workflow permissions for current user"""
    user = request.user
    
    return Response({
        'user_role': user.role.name if user.role else 'unknown',
        'can_create': user.is_publisher() or user.is_admin(),
        'can_review': user.is_reviewer() or user.is_admin(),
        'can_publish': user.is_reviewer() or user.is_admin(),
        'can_admin': user.is_admin()
    })
