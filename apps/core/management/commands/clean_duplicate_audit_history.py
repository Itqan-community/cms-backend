"""Audit-safe variant of django-simple-history's clean_duplicate_history (ITQ-36 / #434)."""

from datetime import timedelta

from django.utils import timezone
from simple_history.management.commands.clean_duplicate_history import Command as CleanDuplicateHistoryCommand
from simple_history.models import HistoricalChanges


class Command(CleanDuplicateHistoryCommand):
    help = (
        "Deletes consecutive zero-diff update snapshots, but only when they were saved by the same actor "
        "with the same change reason, so no audit event (who did it and why) is lost."
    )

    def _process(self, to_process, date_back=None, dry_run=True) -> None:
        # The upstream command filters live rows with a subquery on the history table, which lives in the
        # audit database; as a subquery it would run on the default database, where those tables do not exist.
        if not date_back:
            super()._process(to_process, date_back=date_back, dry_run=dry_run)
            return
        stop_date = timezone.now() - timedelta(minutes=date_back)
        for model, history_model in to_process:
            pk_name = model._meta.pk.name
            object_ids = list(
                history_model.objects.filter(history_date__gte=stop_date).values_list(pk_name, flat=True).distinct()
            )
            manager = model._base_manager if self.base_manager else model._default_manager
            for start in range(0, len(object_ids), 1000):
                for instance in manager.filter(pk__in=object_ids[start : start + 1000]).iterator():
                    self._process_instance(instance, model, stop_date=stop_date, dry_run=dry_run)

    def _check_and_delete(self, entry1: HistoricalChanges, entry2: HistoricalChanges, dry_run: bool = True) -> int:
        # entry1 is the newer record. Keep it unless it is a plain update by the same actor for the same reason.
        if (
            entry1.history_type != "~"
            or entry1.history_user_id != entry2.history_user_id
            or entry1.history_change_reason != entry2.history_change_reason
        ):
            return 0
        return super()._check_and_delete(entry1, entry2, dry_run)
