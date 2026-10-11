from django.contrib import admin
from django.contrib.auth.models import Group
from django.contrib.sites.models import Site
from simple_history.admin import SimpleHistoryAdmin


class AuditedModelAdmin(SimpleHistoryAdmin):
    """ModelAdmin base class integrated with django-simple-history and the dual-database architecture.

    Features:
    - Provides object history inspection and point-in-time revert views in Django Admin.
    - Accurately attributes `_history_user = request.user`.
    - Handles resurrection of deleted rows when reverting a historical snapshot of a deleted object.
    """

    def save_model(self, request, obj, form, change):
        """Saves model instance, resurrecting deleted rows via force_insert if missing from operational DB."""
        obj._history_user = request.user
        # If the object was deleted from the operational table, resurrect it via force_insert
        if not self.model.objects.filter(pk=obj.pk).exists():
            obj._state.adding = True
            obj._state.db = "default"
            obj.save(force_insert=True)
            return

        super().save_model(request, obj, form, change)


admin.site.unregister(
    [
        Site,
        Group,
    ]
)
