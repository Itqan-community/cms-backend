from django.contrib import admin
from django.contrib.auth.models import Group
from django.contrib.sites.models import Site
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404
from simple_history.admin import SimpleHistoryAdmin


class AuditedModelAdmin(SimpleHistoryAdmin):
    """ModelAdmin base class integrated with django-simple-history and the dual-database architecture.

    Features:
    - Provides object history inspection and point-in-time revert views in Django Admin.
    - Accurately attributes `_history_user = request.user`.
    - Handles resurrection of deleted rows when reverting a historical snapshot of a deleted object.
    - Enforces change permission on POST to prevent view-only staff from modifying or reverting records.
    """

    def history_form_view(self, request, object_id, version_id, extra_context=None):
        """Enforces change permission on POST to prevent view-only staff from modifying or reverting records."""
        if request.method == "POST":
            original_opts = self.model._meta
            model = getattr(self.model, self.model._meta.simple_history_manager_attribute).model
            obj = get_object_or_404(model, **{original_opts.pk.attname: object_id, "history_id": version_id}).instance
            if not self.has_change_permission(request, obj):
                raise PermissionDenied

        return super().history_form_view(request, object_id, version_id, extra_context=extra_context)

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
