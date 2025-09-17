"""
Celery tasks for async analytics processing
Handles usage event tracking and analytics computations
"""
from celery import shared_task
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db import transaction
import logging

User = get_user_model()
logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def create_usage_event_task(self, event_data):
    """
    Async task to create usage events without blocking API requests
    
    Args:
        event_data: Dictionary containing:
            - developer_user_id: User ID
            - usage_kind: Type of usage (view, file_download, api_access)
            - subject_kind: What was accessed (asset, resource, publisher)
            - asset_id: Asset ID (optional)
            - resource_id: Resource ID (optional)
            - metadata: Additional event metadata
            - ip_address: Client IP address
            - user_agent: Client user agent
    """
    try:
        from .models import UsageEvent, Asset, Resource
        
        # Validate required fields
        required_fields = ['developer_user_id', 'usage_kind', 'subject_kind']
        for field in required_fields:
            if field not in event_data:
                logger.error(f"Missing required field '{field}' in usage event data")
                return False
        
        # Get user
        try:
            user = User.objects.get(id=event_data['developer_user_id'])
        except User.DoesNotExist:
            logger.error(f"User {event_data['developer_user_id']} not found for usage event")
            return False
        
        # Validate subject references
        asset_id = event_data.get('asset_id')
        resource_id = event_data.get('resource_id')
        
        if event_data['subject_kind'] == 'asset' and asset_id:
            try:
                Asset.objects.get(id=asset_id)
            except Asset.DoesNotExist:
                logger.error(f"Asset {asset_id} not found for usage event")
                return False
        elif event_data['subject_kind'] == 'resource' and resource_id:
            try:
                Resource.objects.get(id=resource_id)
            except Resource.DoesNotExist:
                logger.error(f"Resource {resource_id} not found for usage event")
                return False
        
        # Create usage event
        with transaction.atomic():
            usage_event = UsageEvent.objects.create(
                developer_user=user,
                usage_kind=event_data['usage_kind'],
                subject_kind=event_data['subject_kind'],
                asset_id=asset_id,
                resource_id=resource_id,
                metadata=event_data.get('metadata', {}),
                ip_address=event_data.get('ip_address'),
                user_agent=event_data.get('user_agent', '')
            )
            
            logger.info(f"Created usage event {usage_event.id} for user {user.id}")
            return True
            
    except Exception as exc:
        logger.error(f"Failed to create usage event: {exc}")
        # Retry the task
        raise self.retry(exc=exc, countdown=60 * (self.request.retries + 1))


@shared_task(bind=True, max_retries=3)
def update_asset_statistics_task(self, asset_id, stat_type, increment=1):
    """
    Async task to update asset statistics
    
    Args:
        asset_id: Asset ID to update
        stat_type: 'download_count' or 'view_count'
        increment: Amount to increment (default 1)
    """
    try:
        from .models import Asset
        
        asset = Asset.objects.get(id=asset_id)
        
        if stat_type == 'download_count':
            asset.download_count += increment
        elif stat_type == 'view_count':
            asset.view_count += increment
        else:
            logger.error(f"Invalid stat_type: {stat_type}")
            return False
        
        asset.save(update_fields=[stat_type, 'updated_at'])
        logger.info(f"Updated {stat_type} for asset {asset_id} by {increment}")
        return True
        
    except Asset.DoesNotExist:
        logger.error(f"Asset {asset_id} not found for statistics update")
        return False
    except Exception as exc:
        logger.error(f"Failed to update asset statistics: {exc}")
        raise self.retry(exc=exc, countdown=30 * (self.request.retries + 1))


@shared_task
def batch_create_usage_events_task(events_data):
    """
    Batch process multiple usage events for efficiency
    
    Args:
        events_data: List of event data dictionaries
    """
    try:
        from .models import UsageEvent
        
        events_to_create = []
        successful_events = 0
        
        for event_data in events_data:
            try:
                # Validate and prepare event
                user = User.objects.get(id=event_data['developer_user_id'])
                
                event = UsageEvent(
                    developer_user=user,
                    usage_kind=event_data['usage_kind'],
                    subject_kind=event_data['subject_kind'],
                    asset_id=event_data.get('asset_id'),
                    resource_id=event_data.get('resource_id'),
                    metadata=event_data.get('metadata', {}),
                    ip_address=event_data.get('ip_address'),
                    user_agent=event_data.get('user_agent', '')
                )
                events_to_create.append(event)
                
            except Exception as e:
                logger.error(f"Failed to prepare usage event: {e}")
                continue
        
        # Bulk create events
        if events_to_create:
            with transaction.atomic():
                UsageEvent.objects.bulk_create(events_to_create)
                successful_events = len(events_to_create)
        
        logger.info(f"Batch created {successful_events} usage events from {len(events_data)} attempts")
        return successful_events
        
    except Exception as exc:
        logger.error(f"Failed to batch create usage events: {exc}")
        return 0


@shared_task
def compute_daily_analytics_task():
    """
    Daily task to compute analytics aggregations
    """
    try:
        from .models import UsageEvent, Asset, Publisher
        from django.db.models import Count, Sum
        
        today = timezone.now().date()
        
        # Compute daily statistics
        daily_stats = {
            'date': today.isoformat(),
            'total_downloads': UsageEvent.objects.filter(
                created_at__date=today,
                usage_kind='file_download'
            ).count(),
            'total_views': UsageEvent.objects.filter(
                created_at__date=today,
                usage_kind='view'
            ).count(),
            'unique_users': UsageEvent.objects.filter(
                created_at__date=today
            ).values('developer_user').distinct().count(),
            'top_assets': [],
            'top_publishers': []
        }
        
        # Get top assets by downloads today
        top_assets = UsageEvent.objects.filter(
            created_at__date=today,
            usage_kind='file_download',
            asset_id__isnull=False
        ).values('asset_id').annotate(
            download_count=Count('id')
        ).order_by('-download_count')[:10]
        
        for asset_stat in top_assets:
            try:
                asset = Asset.objects.get(id=asset_stat['asset_id'])
                daily_stats['top_assets'].append({
                    'asset_id': asset.id,
                    'title': asset.title,
                    'download_count': asset_stat['download_count']
                })
            except Asset.DoesNotExist:
                continue
        
        # Get top publishers by activity today
        top_publishers = UsageEvent.objects.filter(
            created_at__date=today,
            asset_id__isnull=False
        ).values('asset__publishing_organization').annotate(
            activity_count=Count('id')
        ).order_by('-activity_count')[:10]
        
        for pub_stat in top_publishers:
            try:
                pub_id = pub_stat['asset__publishing_organization']
                publisher = Publisher.objects.get(id=pub_id)
                daily_stats['top_publishers'].append({
                    'publisher_id': publisher.id,
                    'name': publisher.name,
                    'activity_count': pub_stat['activity_count']
                })
            except Publisher.DoesNotExist:
                continue
        
        # Store or cache the daily stats
        # This could be stored in Redis or a dedicated analytics table
        logger.info(f"Computed daily analytics for {today}: {daily_stats}")
        
        return daily_stats
        
    except Exception as exc:
        logger.error(f"Failed to compute daily analytics: {exc}")
        return None


@shared_task
def cleanup_old_usage_events_task(days_to_keep=90):
    """
    Clean up old usage events to maintain database performance
    
    Args:
        days_to_keep: Number of days of usage events to retain
    """
    try:
        from .models import UsageEvent
        
        cutoff_date = timezone.now() - timezone.timedelta(days=days_to_keep)
        
        # Delete old events in batches
        deleted_count = 0
        batch_size = 1000
        
        while True:
            with transaction.atomic():
                old_events = UsageEvent.objects.filter(
                    created_at__lt=cutoff_date
                ).values_list('id', flat=True)[:batch_size]
                
                old_events_list = list(old_events)
                if not old_events_list:
                    break
                
                UsageEvent.objects.filter(id__in=old_events_list).delete()
                deleted_count += len(old_events_list)
                
                logger.info(f"Deleted {len(old_events_list)} old usage events")
        
        logger.info(f"Cleanup completed: deleted {deleted_count} usage events older than {days_to_keep} days")
        return deleted_count
        
    except Exception as exc:
        logger.error(f"Failed to cleanup old usage events: {exc}")
        return 0


@shared_task
def update_publisher_statistics_task(publisher_id):
    """
    Update cached statistics for a publisher
    
    Args:
        publisher_id: Publisher ID
    """
    try:
        from .models import Publisher, Asset, Resource
        
        publisher = Publisher.objects.get(id=publisher_id)
        
        # Calculate fresh statistics
        assets = Asset.objects.filter(publishing_organization=publisher)
        resources = Resource.objects.filter(publishing_organization=publisher)
        
        stats = {
            'resources_count': resources.count(),
            'assets_count': assets.count(),
            'total_downloads': sum(asset.download_count for asset in assets),
            'total_views': sum(asset.view_count for asset in assets),
            'last_updated': timezone.now().isoformat()
        }
        
        # Store stats (could be cached in Redis or database)
        logger.info(f"Updated statistics for publisher {publisher_id}: {stats}")
        
        return stats
        
    except Publisher.DoesNotExist:
        logger.error(f"Publisher {publisher_id} not found for statistics update")
        return None
    except Exception as exc:
        logger.error(f"Failed to update publisher statistics: {exc}")
        return None


# Enhanced analytics helper function
def track_event_async(event_data):
    """
    Helper function to queue usage event tracking
    
    Args:
        event_data: Event data dictionary
    """
    try:
        # Queue the task for async processing
        create_usage_event_task.delay(event_data)
        return True
    except Exception as e:
        logger.error(f"Failed to queue usage event: {e}")
        # Fallback to synchronous creation if Celery is unavailable
        try:
            from .models import UsageEvent
            UsageEvent.objects.create(**event_data)
            return True
        except Exception as sync_e:
            logger.error(f"Failed to create usage event synchronously: {sync_e}")
            return False


def update_asset_stats_async(asset_id, stat_type, increment=1):
    """
    Helper function to queue asset statistics updates
    
    Args:
        asset_id: Asset ID
        stat_type: 'download_count' or 'view_count'
        increment: Amount to increment
    """
    try:
        update_asset_statistics_task.delay(asset_id, stat_type, increment)
        return True
    except Exception as e:
        logger.error(f"Failed to queue asset statistics update: {e}")
        return False
