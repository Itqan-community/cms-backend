"""
Search API views for Itqan CMS
"""
import logging
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, OpenApiParameter

from .client import meili_client
from .serializers import SearchRequestSerializer, SearchResultSerializer
from .tasks import (
    bulk_index_resources, rebuild_all_indexes, 
    health_check_meilisearch, get_search_stats
)
from apps.api.permissions import IsAdminUser

logger = logging.getLogger(__name__)


class SearchAPIView(APIView):
    """
    Search resources using MeiliSearch
    """
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        summary="Search resources",
        description="Search for Quranic resources using full-text search with filtering and sorting",
        parameters=[
            OpenApiParameter(name='q', description='Search query', required=False, type=str),
            OpenApiParameter(name='offset', description='Number of results to skip', required=False, type=int),
            OpenApiParameter(name='limit', description='Maximum results to return', required=False, type=int),
            OpenApiParameter(name='filter', description='Filter expression', required=False, type=str),
            OpenApiParameter(name='sort', description='Sort criteria (comma-separated)', required=False, type=str),
            OpenApiParameter(name='facets', description='Facet attributes (comma-separated)', required=False, type=str),
        ],
        responses={200: SearchResultSerializer}
    )
    def get(self, request):
        """
        Search for resources
        """
        # Validate search parameters
        serializer = SearchRequestSerializer(data=request.query_params)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        search_params = serializer.validated_data
        
        # Build search options
        search_options = {
            'offset': search_params.get('offset', 0),
            'limit': search_params.get('limit', 20),
        }
        
        # Add filter (only show published resources to non-admin users)
        base_filter = 'is_active = true AND is_published = true'
        user_filter = search_params.get('filter', '')
        
        if user_filter:
            search_options['filter'] = f'({base_filter}) AND ({user_filter})'
        else:
            search_options['filter'] = base_filter
        
        # Admin users can see all resources
        if request.user.is_admin():
            search_options['filter'] = search_params.get('filter', 'is_active = true')
        
        # Publishers can see their own resources + published resources
        elif request.user.is_publisher():
            publisher_filter = f'publisher_id = "{request.user.id}"'
            if user_filter:
                search_options['filter'] = f'({base_filter} OR {publisher_filter}) AND ({user_filter})'
            else:
                search_options['filter'] = f'{base_filter} OR {publisher_filter}'
        
        # Add sorting
        if search_params.get('sort'):
            search_options['sort'] = search_params['sort']
        
        # Add facets
        if search_params.get('facets'):
            search_options['facets'] = search_params['facets']
        
        # Add highlighting
        if search_params.get('attributes_to_highlight'):
            search_options['attributesToHighlight'] = search_params['attributes_to_highlight']
            search_options['highlightPreTag'] = search_params.get('highlight_pre_tag', '<mark>')
            search_options['highlightPostTag'] = search_params.get('highlight_post_tag', '</mark>')
        
        # Add attribute selection
        if search_params.get('attributes_to_retrieve'):
            search_options['attributesToRetrieve'] = search_params['attributes_to_retrieve']
        
        try:
            # Perform search
            query = search_params.get('q', '')
            results = meili_client.search('resources', query, **search_options)
            
            if results is None:
                return Response(
                    {'error': 'Search service unavailable'},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE
                )
            
            # Format response
            response_serializer = SearchResultSerializer(results)
            return Response(response_serializer.data)
        
        except Exception as e:
            logger.error(f"Search error: {e}")
            return Response(
                {'error': 'Search failed'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@api_view(['POST'])
@permission_classes([IsAdminUser])
@extend_schema(
    summary="Rebuild search indexes",
    description="Rebuild all search indexes from scratch (Admin only)",
    responses={202: {'type': 'object', 'properties': {'message': {'type': 'string'}, 'task_id': {'type': 'string'}}}}
)
def rebuild_indexes(request):
    """
    Trigger a complete rebuild of search indexes
    """
    try:
        result = rebuild_all_indexes.delay()
        return Response({
            'message': 'Search index rebuild initiated',
            'task_id': result.id
        }, status=status.HTTP_202_ACCEPTED)
    
    except Exception as e:
        logger.error(f"Failed to initiate index rebuild: {e}")
        return Response(
            {'error': 'Failed to initiate index rebuild'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAdminUser])
@extend_schema(
    summary="Bulk reindex resources",
    description="Reindex specific resources or all resources (Admin only)",
    request={
        'type': 'object',
        'properties': {
            'resource_ids': {
                'type': 'array',
                'items': {'type': 'string', 'format': 'uuid'},
                'description': 'List of resource UUIDs to reindex (empty = all resources)'
            },
            'batch_size': {
                'type': 'integer',
                'default': 100,
                'description': 'Number of resources to process in each batch'
            }
        }
    },
    responses={202: {'type': 'object', 'properties': {'message': {'type': 'string'}, 'task_id': {'type': 'string'}}}}
)
def bulk_reindex(request):
    """
    Trigger bulk reindexing of resources
    """
    try:
        resource_ids = request.data.get('resource_ids', [])
        batch_size = request.data.get('batch_size', 100)
        
        # Validate batch size
        if not 1 <= batch_size <= 1000:
            return Response(
                {'error': 'Batch size must be between 1 and 1000'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        result = bulk_index_resources.delay(
            resource_ids=resource_ids if resource_ids else None,
            batch_size=batch_size
        )
        
        return Response({
            'message': f'Bulk reindexing initiated for {"all resources" if not resource_ids else f"{len(resource_ids)} resources"}',
            'task_id': result.id
        }, status=status.HTTP_202_ACCEPTED)
    
    except Exception as e:
        logger.error(f"Failed to initiate bulk reindex: {e}")
        return Response(
            {'error': 'Failed to initiate bulk reindex'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAdminUser])
@extend_schema(
    summary="Get search health status",
    description="Check MeiliSearch connectivity and health (Admin only)",
    responses={200: {'type': 'object', 'properties': {'healthy': {'type': 'boolean'}, 'task_id': {'type': 'string'}}}}
)
def search_health(request):
    """
    Check search service health
    """
    try:
        result = health_check_meilisearch.delay()
        return Response({
            'healthy': None,  # Will be determined by the async task
            'task_id': result.id,
            'message': 'Health check initiated'
        })
    
    except Exception as e:
        logger.error(f"Failed to initiate health check: {e}")
        return Response(
            {'error': 'Failed to initiate health check'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAdminUser])
@extend_schema(
    summary="Get search statistics",
    description="Get search index statistics and metrics (Admin only)",
    responses={200: {'type': 'object', 'properties': {'stats': {'type': 'object'}, 'task_id': {'type': 'string'}}}}
)
def search_stats(request):
    """
    Get search index statistics
    """
    try:
        result = get_search_stats.delay()
        return Response({
            'stats': None,  # Will be determined by the async task
            'task_id': result.id,
            'message': 'Stats retrieval initiated'
        })
    
    except Exception as e:
        logger.error(f"Failed to get search stats: {e}")
        return Response(
            {'error': 'Failed to get search stats'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@extend_schema(
    summary="Search suggestions",
    description="Get search suggestions based on a partial query",
    parameters=[
        OpenApiParameter(name='q', description='Partial search query', required=True, type=str),
        OpenApiParameter(name='limit', description='Maximum suggestions to return', required=False, type=int),
    ],
    responses={200: {'type': 'object', 'properties': {'suggestions': {'type': 'array', 'items': {'type': 'string'}}}}}
)
def search_suggestions(request):
    """
    Get search suggestions/autocomplete
    """
    try:
        query = request.query_params.get('q', '').strip()
        limit = min(int(request.query_params.get('limit', 10)), 20)
        
        if not query or len(query) < 2:
            return Response({'suggestions': []})
        
        # Search for matching titles and descriptions
        search_options = {
            'limit': limit * 2,  # Get more results to filter
            'attributesToRetrieve': ['title', 'description'],
            'filter': 'is_active = true AND is_published = true'
        }
        
        # Apply user-specific filters
        if request.user.is_publisher():
            publisher_filter = f'publisher_id = "{request.user.id}"'
            search_options['filter'] = f'(is_active = true AND is_published = true) OR {publisher_filter}'
        elif not request.user.is_admin():
            search_options['filter'] = 'is_active = true AND is_published = true'
        
        results = meili_client.search('resources', query, **search_options)
        
        if not results or not results.get('hits'):
            return Response({'suggestions': []})
        
        # Extract unique suggestions from titles
        suggestions = set()
        for hit in results['hits']:
            title = hit.get('title', '').strip()
            if title and len(suggestions) < limit:
                suggestions.add(title)
        
        return Response({'suggestions': list(suggestions)[:limit]})
    
    except Exception as e:
        logger.error(f"Search suggestions error: {e}")
        return Response(
            {'suggestions': []},
            status=status.HTTP_200_OK  # Return empty suggestions rather than error
        )