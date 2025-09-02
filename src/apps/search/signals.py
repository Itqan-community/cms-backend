"""
Django signals for automatic search indexing
"""
import logging
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.conf import settings

from apps.content.models import Resource
from .tasks import index_resource, reindex_resource_on_publish

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Resource)
def resource_post_save(sender, instance, created, **kwargs):
    """
    Index resource when it's created or updated
    """
    try:
        # Skip indexing if Celery is in eager mode (for testing)
        if getattr(settings, 'CELERY_TASK_ALWAYS_EAGER', False):
            logger.debug(f"Skipping indexing for resource {instance.id} (Celery eager mode)")
            return
        
        # Determine action type
        action = 'create' if created else 'update'
        
        # Check if this is a publication event
        if not created and instance.published_at:
            # Check if this resource was just published
            try:
                # Get the previous state from database
                previous = Resource.objects.get(id=instance.id)
                if not previous.published_at and instance.published_at:
                    # Resource was just published, use special publish task
                    reindex_resource_on_publish.delay(str(instance.id))
                    logger.info(f"Triggered publish indexing for resource {instance.id}")
                    return
            except Resource.DoesNotExist:
                pass
        
        # Regular indexing
        index_resource.delay(str(instance.id), action=action)
        logger.info(f"Triggered {action} indexing for resource {instance.id}")
        
    except Exception as e:
        logger.error(f"Failed to trigger indexing for resource {instance.id}: {e}")


@receiver(post_delete, sender=Resource)
def resource_post_delete(sender, instance, **kwargs):
    """
    Remove resource from search index when deleted
    """
    try:
        # Skip indexing if Celery is in eager mode (for testing)
        if getattr(settings, 'CELERY_TASK_ALWAYS_EAGER', False):
            logger.debug(f"Skipping delete indexing for resource {instance.id} (Celery eager mode)")
            return
        
        index_resource.delay(str(instance.id), action='delete')
        logger.info(f"Triggered delete indexing for resource {instance.id}")
        
    except Exception as e:
        logger.error(f"Failed to trigger delete indexing for resource {instance.id}: {e}")


# Optional: Add signals for other models that should trigger reindexing
# For example, if a User (publisher) is updated, we might want to reindex their resources

@receiver(post_save, sender='accounts.User')
def user_post_save(sender, instance, created, **kwargs):
    """
    Reindex resources when a publisher's information changes
    """
    try:
        # Only reindex if this is a publisher and not a new user
        if created or not instance.is_publisher():
            return
        
        # Skip indexing if Celery is in eager mode
        if getattr(settings, 'CELERY_TASK_ALWAYS_EAGER', False):
            return
        
        # Get all published resources by this publisher
        published_resources = Resource.objects.filter(
            publisher=instance,
            is_active=True,
            published_at__isnull=False
        ).values_list('id', flat=True)
        
        if published_resources:
            from .tasks import bulk_index_resources
            resource_ids = [str(resource_id) for resource_id in published_resources]
            bulk_index_resources.delay(resource_ids=resource_ids)
            logger.info(f"Triggered reindexing of {len(resource_ids)} resources for publisher {instance.id}")
        
    except Exception as e:
        logger.error(f"Failed to trigger publisher reindexing for user {instance.id}: {e}")


# Signal for when a resource is soft-deleted (is_active changed to False)
@receiver(post_save, sender=Resource)
def resource_activation_change(sender, instance, created, **kwargs):
    """
    Handle resource activation/deactivation
    """
    try:
        # Skip for new resources or if Celery is in eager mode
        if created or getattr(settings, 'CELERY_TASK_ALWAYS_EAGER', False):
            return
        
        # Check if is_active status changed
        try:
            # Get the previous state from database
            if kwargs.get('update_fields'):
                # If specific fields were updated, check if is_active was one of them
                if 'is_active' not in kwargs['update_fields']:
                    return
            
            # If resource was deactivated, remove from index
            if not instance.is_active:
                index_resource.delay(str(instance.id), action='delete')
                logger.info(f"Triggered delete indexing for deactivated resource {instance.id}")
            
            # If resource was reactivated and is published, add back to index
            elif instance.is_active and instance.published_at:
                index_resource.delay(str(instance.id), action='update')
                logger.info(f"Triggered update indexing for reactivated resource {instance.id}")
        
        except Exception as e:
            logger.debug(f"Could not check previous state for resource {instance.id}: {e}")
    
    except Exception as e:
        logger.error(f"Failed to handle activation change for resource {instance.id}: {e}")


def connect_signals():
    """
    Function to manually connect signals if needed
    """
    logger.info("Search indexing signals connected")


def disconnect_signals():
    """
    Function to disconnect signals for testing
    """
    post_save.disconnect(resource_post_save, sender=Resource)
    post_delete.disconnect(resource_post_delete, sender=Resource)
    post_save.disconnect(user_post_save, sender='accounts.User')
    post_save.disconnect(resource_activation_change, sender=Resource)
    logger.info("Search indexing signals disconnected")
