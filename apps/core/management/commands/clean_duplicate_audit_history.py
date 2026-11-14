"""Audit-safe variant of django-simple-history's clean_duplicate_history (ITQ-36 / #434)."""

from datetime import timedelta
from itertools import chain, groupby

from django.utils import timezone
from simple_history.management.commands.clean_duplicate_history import Command as CleanDuplicateHistoryCommand
from simple_history.models import HistoricalChanges

# Objects whose history is read per round of queries.
_CHUNK = 1000


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
            pk_name = model._meta.pk.attname
            object_ids = list(
                history_model.objects.filter(history_date__gte=stop_date).values_list(pk_name, flat=True).distinct()
            )
            manager = model._base_manager if self.base_manager else model._default_manager
            deleted = 0
            for start in range(0, len(object_ids), _CHUNK):
                # Live objects only, as upstream: a deleted object's history is left as it is.
                live_ids = list(manager.filter(pk__in=object_ids[start : start + _CHUNK]).values_list("pk", flat=True))
                if live_ids:
                    deleted += self._process_chunk(history_model, pk_name, live_ids, stop_date, dry_run)
            self.log(self.DONE_CLEANING_FOR_MODEL.format(model=model, count=deleted))

    def _process_chunk(self, history_model, pk_name: str, object_ids: list, stop_date, dry_run: bool) -> int:
        """Upstream's per-object walk (each window snapshot against the next older one, the oldest
        against the newest snapshot from before the window) in three queries for the whole chunk,
        instead of three per object."""
        order = (pk_name, "-history_date", f"-{history_model._meta.pk.attname}")
        before_window = {
            getattr(entry, pk_name): entry
            for entry in history_model.objects.filter(**{f"{pk_name}__in": object_ids}, history_date__lte=stop_date)
            .order_by(*order)
            .distinct(pk_name)
        }
        in_window = (
            history_model.objects.filter(**{f"{pk_name}__in": object_ids}, history_date__gte=stop_date)
            .order_by(*order)
            .iterator(chunk_size=2000)
        )
        deleted = 0
        for object_id, entries in groupby(in_window, key=lambda entry: getattr(entry, pk_name)):
            newer = next(entries)
            for older in chain(entries, filter(None, [before_window.get(object_id)])):
                deleted += self._check_and_delete(newer, older, dry_run)
                newer = older
        return deleted

    def _check_and_delete(self, entry1: HistoricalChanges, entry2: HistoricalChanges, dry_run: bool = True) -> int:
        # entry1 is the newer record. Keep it unless it is a plain update by the same actor for the same reason.
        if (
            entry1.history_type != "~"
            or entry1.history_user_id != entry2.history_user_id
            or entry1.history_change_reason != entry2.history_change_reason
        ):
            return 0
        return super()._check_and_delete(entry1, entry2, dry_run)
