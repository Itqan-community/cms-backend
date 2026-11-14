from celery import shared_task
from django.core.management import call_command

# The dedupe job runs weekly; look back one extra day so a delayed run leaves no gap.
DUPLICATE_HISTORY_WINDOW_MINUTES = 8 * 24 * 60


# Weekly jobs over a week of history: the 60s default soft limit is far too short for them.
@shared_task(soft_time_limit=1500, time_limit=1560)
def prune_audit_history_task():
    """Weekly automated pruning of expired operational audit history."""
    call_command("prune_audit_history")


@shared_task(soft_time_limit=1500, time_limit=1560)
def clean_duplicate_history_task():
    """Weekly automated deduplication of redundant zero-diff historical snapshots.

    Implements Tier 3 retention policy via clean_duplicate_audit_history, which only
    removes a consecutive zero-diff update when the same actor saved it with the same
    change reason, so every distinct audit event survives. Only history from the
    last window is scanned instead of every row of every tracked model.
    """
    call_command("clean_duplicate_audit_history", auto=True, minutes=DUPLICATE_HISTORY_WINDOW_MINUTES)
