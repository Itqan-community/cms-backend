from celery import shared_task
from apps.publishers.services.stats import compute_publisher_stats_sync
from .types import PublisherStats

@shared_task
def compute_publisher_stats_task() -> PublisherStats:
    return compute_publisher_stats_sync()