"""
Celery tasks for search indexing in Itqan CMS
"""
import logging
from typing import List, Dict, Optional
from celery import shared_task
from django.apps import apps
from django.utils import timezone
from datetime import timedelta

from .client import meili_client
from .serializers import ResourceSearchSerializer

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def index_resource(self, resource_id: str, action: str = 'update'):
    """
    Index a single resource in MeiliSearch
    
    Args:
        resource_id: UUID of the resource to index
        action: 'create', 'update', or 'delete'
    """
    try:
        Resource = apps.get_model('content', 'Resource')
        
        if action == 'delete':
            # Delete from search index
            task_info = meili_client.delete_document('resources', resource_id)
            if task_info:
                meili_client.wait_for_task(task_info.task_uid)
                logger.info(f"Deleted resource {resource_id} from search index")
            return {'status': 'deleted', 'resource_id': resource_id}
        
        # Get resource from database
        try:
            resource = Resource.objects.select_related('publisher', 'publisher__role').get(id=resource_id)
        except Resource.DoesNotExist:
            logger.warning(f"Resource {resource_id} not found for indexing")
            return {'status': 'not_found', 'resource_id': resource_id}
        
        # Only index active and published resources
        if not resource.is_active or not resource.published_at:
            logger.info(f"Skipping inactive/unpublished resource {resource_id}")
            return {'status': 'skipped', 'resource_id': resource_id}
        
        # Serialize resource for search
        serializer = ResourceSearchSerializer(resource)
        document = serializer.data
        
        # Add/update in search index
        task_info = meili_client.update_documents('resources', [document])
        if task_info:
            meili_client.wait_for_task(task_info.task_uid)
            logger.info(f"Indexed resource {resource_id} in search")
        
        return {'status': 'indexed', 'resource_id': resource_id, 'action': action}
        
    except Exception as exc:
        logger.error(f"Failed to index resource {resource_id}: {exc}")
        
        # Retry the task
        if self.request.retries < self.max_retries:
            raise self.retry(countdown=60 * (2 ** self.request.retries))
        
        return {'status': 'failed', 'resource_id': resource_id, 'error': str(exc)}


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def bulk_index_resources(self, resource_ids: List[str] = None, batch_size: int = 100):
    """
    Bulk index multiple resources
    
    Args:
        resource_ids: List of resource UUIDs to index (None = all active resources)
        batch_size: Number of resources to process in each batch
    """
    try:
        Resource = apps.get_model('content', 'Resource')
        
        # Build queryset
        queryset = Resource.objects.select_related('publisher', 'publisher__role').filter(
            is_active=True,
            published_at__isnull=False
        )
        
        if resource_ids:
            queryset = queryset.filter(id__in=resource_ids)
        
        total_count = queryset.count()
        indexed_count = 0
        failed_count = 0
        
        logger.info(f"Starting bulk indexing of {total_count} resources")
        
        # Process in batches
        for offset in range(0, total_count, batch_size):
            batch = queryset[offset:offset + batch_size]
            documents = []
            
            for resource in batch:
                try:
                    serializer = ResourceSearchSerializer(resource)
                    documents.append(serializer.data)
                except Exception as e:
                    logger.error(f"Failed to serialize resource {resource.id}: {e}")
                    failed_count += 1
            
            if documents:
                # Index batch
                task_info = meili_client.update_documents('resources', documents)
                if task_info:
                    success = meili_client.wait_for_task(task_info.task_uid)
                    if success:
                        indexed_count += len(documents)
                        logger.info(f"Indexed batch of {len(documents)} resources")
                    else:
                        failed_count += len(documents)
                        logger.error(f"Failed to index batch of {len(documents)} resources")
        
        return {
            'status': 'completed',
            'total_count': total_count,
            'indexed_count': indexed_count,
            'failed_count': failed_count
        }
        
    except Exception as exc:
        logger.error(f"Bulk indexing failed: {exc}")
        
        # Retry the task
        if self.request.retries < self.max_retries:
            raise self.retry(countdown=60 * (2 ** self.request.retries))
        
        return {'status': 'failed', 'error': str(exc)}


@shared_task
def rebuild_all_indexes():
    """
    Rebuild all search indexes from scratch
    """
    try:
        logger.info("Starting complete search index rebuild")
        
        # Clear existing index
        task_info = meili_client.clear_index('resources')
        if task_info:
            meili_client.wait_for_task(task_info.task_uid)
        
        # Reindex all resources
        result = bulk_index_resources.delay()
        
        logger.info("Search index rebuild initiated")
        return {'status': 'initiated', 'task_id': result.id}
        
    except Exception as e:
        logger.error(f"Failed to rebuild search indexes: {e}")
        return {'status': 'failed', 'error': str(e)}


@shared_task
def cleanup_failed_tasks():
    """
    Clean up failed Celery tasks older than 7 days
    """
    try:
        from celery.result import AsyncResult
        from celery import current_app
        
        cutoff_date = timezone.now() - timedelta(days=7)
        
        # Get inspection API
        inspect = current_app.control.inspect()
        
        # Clean up reserved tasks
        reserved = inspect.reserved()
        if reserved:
            for worker, tasks in reserved.items():
                for task in tasks:
                    task_id = task.get('id')
                    if task_id:
                        result = AsyncResult(task_id)
                        if result.date_done and result.date_done < cutoff_date:
                            result.forget()
        
        logger.info("Completed cleanup of failed tasks")
        return {'status': 'completed'}
        
    except Exception as e:
        logger.error(f"Failed to cleanup tasks: {e}")
        return {'status': 'failed', 'error': str(e)}


@shared_task(bind=True, max_retries=2)
def health_check_meilisearch(self):
    """
    Check MeiliSearch health and report status
    """
    try:
        is_healthy = meili_client.health_check()
        
        if is_healthy:
            logger.info("MeiliSearch health check passed")
            return {'status': 'healthy'}
        else:
            logger.warning("MeiliSearch health check failed")
            return {'status': 'unhealthy'}
    
    except Exception as exc:
        logger.error(f"MeiliSearch health check error: {exc}")
        
        # Retry once
        if self.request.retries < self.max_retries:
            raise self.retry(countdown=30)
        
        return {'status': 'error', 'error': str(exc)}


@shared_task
def get_search_stats():
    """
    Get search index statistics
    """
    try:
        stats = meili_client.get_index_stats('resources')
        
        if stats:
            logger.info(f"Search index stats: {stats}")
            return {
                'status': 'success',
                'stats': stats
            }
        else:
            return {'status': 'failed', 'error': 'Could not retrieve stats'}
    
    except Exception as e:
        logger.error(f"Failed to get search stats: {e}")
        return {'status': 'failed', 'error': str(e)}


@shared_task(bind=True)
def reindex_resource_on_publish(self, resource_id: str):
    """
    Reindex a resource when it gets published
    """
    try:
        # Add a small delay to ensure database transaction is committed
        import time
        time.sleep(2)
        
        return index_resource.delay(resource_id, action='update')
    
    except Exception as e:
        logger.error(f"Failed to trigger reindex for published resource {resource_id}: {e}")
        return {'status': 'failed', 'error': str(e)}
