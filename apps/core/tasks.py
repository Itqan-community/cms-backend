from celery import shared_task
from django.core.management import call_command


@shared_task
def prune_audit_history_task():
    """Weekly automated pruning of expired operational audit history."""
    call_command("prune_audit_history")


@shared_task
def clean_duplicate_history_task():
    """Weekly automated deduplication of redundant zero-diff historical snapshots.

    Implements Tier 3 retention policy by invoking django-simple-history's
    clean_duplicate_history --auto. This removes consecutive historical
    records where no model data fields changed (zero-diff noise saves),
    keeping historical tables compact while preserving all genuine state changes
    and immutable deletion tombstones.
    """
    call_command("clean_duplicate_history", auto=True)
