from django.contrib import admin, messages
from django.db import transaction
from django.db.models import Count
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.urls import path, reverse
from django.utils.html import format_html

from config.settings.base import CLOUDFLARE_R2_PUBLIC_BASE_URL

from ..core.mixins.constants import SURAH_NUMBER_NAME_AR, SURAH_NUMBER_NAME_EN
from ..mixins.recitations_helpers import extract_surah_number_from_filename
from .forms.bulk_recitations_upload_form import BulkRecitationUploadForm
from .forms.download_recitations_json_form import DownloadRecitationsJsonForm
from .models import (
    Asset,
    AssetAccess,
    AssetAccessRequest,
    AssetPreview,
    AssetVersion,
    RecitationAyahTiming,
    RecitationSurahTrack,
    Reciter,
    Resource,
    ResourceVersion,
    Riwayah,
    UsageEvent,
)


class ResourceVersionInline(admin.TabularInline):
    model = ResourceVersion
    extra = 0
    fields = ["semvar", "file_type", "is_latest", "storage_url"]
    readonly_fields = ["created_at"]
    raw_id_fields = ["resource"]


class AssetVersionInline(admin.TabularInline):
    model = AssetVersion
    extra = 0
    fields = ["resource_version", "name", "file_url"]
    readonly_fields = ["created_at"]


@admin.register(Resource)
class ResourceAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "publisher",
        "category",
        "status",
        "latest_version",
        "created_at",
    ]
    list_filter = ["category", "status", "publisher", "created_at"]
    search_fields = ["name", "description", "slug"]
    prepopulated_fields = {"slug": ("name",)}
    inlines = [ResourceVersionInline]
    raw_id_fields = ["publisher"]

    fieldsets = (
        (
            "Basic Information",
            {
                "fields": ("name", "slug", "publisher"),
            },
        ),
        (
            "Content",
            {
                "fields": ("description", "category", "status"),
            },
        ),
        (
            "Multilingual Fields",
            {
                "fields": ("name_en", "name_ar", "description_en", "description_ar"),
                "classes": ("collapse",),
            },
        ),
        (
            "Timestamps",
            {
                "fields": ("created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )
    readonly_fields = ["created_at", "updated_at"]

    def get_queryset(self, request):
        """Optimize queryset with annotations"""
        return (
            super()
            .get_queryset(request)
            .select_related("publisher")
            .annotate(
                annotated_version_count=Count("versions"),
            )
        )

    @admin.display(description="Versions", ordering="annotated_version_count")
    def version_count(self, obj):
        # Prefer annotated value; fall back to model property
        return getattr(obj, "annotated_version_count", obj.version_count)

    @admin.display(description="Latest Version")
    def latest_version(self, obj):
        latest = obj.get_latest_version()
        if latest:
            return f"{latest.semvar}"
        return "No versions"

    @admin.display(description="Versions")
    def view_versions(self, obj):
        """Link to view resource versions"""
        url = reverse("admin:content_resourceversion_changelist")
        count = getattr(obj, "annotated_version_count", obj.version_count)
        return format_html(
            '<a href="{}?resource__id__exact={}">View Versions ({})</a>',
            url,
            obj.pk,
            count,
        )


@admin.register(ResourceVersion)
class ResourceVersionAdmin(admin.ModelAdmin):
    list_display = [
        "resource",
        "semvar",
        "file_type",
        "is_latest",
        "size_bytes",
        "created_at",
    ]
    list_filter = ["file_type", "is_latest", "created_at"]
    search_fields = ["resource__name", "semvar"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "publisher_name",
        "category",
        "file_size",
        "format",
        "license",
        "created_at",
    ]
    list_filter = ["category", "license", "resource__publisher", "format", "created_at"]
    search_fields = ["name", "description", "long_description"]
    inlines = [AssetVersionInline]
    raw_id_fields = ["resource"]

    fieldsets = (
        (
            "Basic Information",
            {
                "fields": ("name", "resource", "category"),
            },
        ),
        (
            "Content",
            {
                "fields": ("description", "long_description", "thumbnail_url"),
            },
        ),
        (
            "Multilingual Fields",
            {
                "fields": (
                    "name_en",
                    "name_ar",
                    "description_en",
                    "description_ar",
                    "long_description_en",
                    "long_description_ar",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Technical Details",
            {
                "fields": ("format", "encoding", "file_size", "version", "language"),
            },
        ),
        (
            "Licensing",
            {
                "fields": ("license",),
            },
        ),
        (
            "Timestamps",
            {
                "fields": ("created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )
    readonly_fields = ["created_at", "updated_at"]

    def get_queryset(self, request):
        """Optimize queryset with annotations"""
        return (
            super()
            .get_queryset(request)
            .select_related("resource__publisher")
            .annotate(
                access_requests_count=Count("access_requests"),
                user_accesses_count=Count("user_accesses"),
            )
        )

    @admin.display(description="Publisher", ordering="resource__publisher")
    def publisher_name(self, obj):
        return obj.resource.publisher.name

    @admin.display(description="Access Requests", ordering="access_requests_count")
    def access_requests_count(self, obj):
        return obj.access_requests_count

    @admin.display(description="Active Access", ordering="user_accesses_count")
    def user_accesses_count(self, obj):
        return obj.user_accesses_count

    @admin.display(description="Access Requests")
    def view_access_requests(self, obj):
        """Link to view asset access requests"""
        url = reverse("admin:content_assetaccessrequest_changelist")
        return format_html(
            '<a href="{}?asset__id__exact={}">View Requests ({})</a>',
            url,
            obj.pk,
            obj.access_requests_count,
        )

    @admin.display(description="Usage Analytics")
    def view_usage_events(self, obj):
        """Link to view usage events for this asset"""
        url = reverse("admin:content_usageevent_changelist")
        return format_html(
            '<a href="{}?asset_id__exact={}">View Usage Events</a>',
            url,
            obj.pk,
        )

    @admin.display(description="File Size")
    def file_size_display(self, obj):
        """Display file size in human-readable format"""
        return obj.file_size

    @admin.display(description="Download")
    def download_url_display(self, obj):
        """Display download URL with link"""
        latest_version = obj.get_latest_version()
        if latest_version and latest_version.file_url:
            return format_html(
                '<a href="{}" target="_blank">Download</a>',
                latest_version.file_url.url,
            )
        return "No download URL"


@admin.register(AssetVersion)
class AssetVersionAdmin(admin.ModelAdmin):
    list_display = ["asset", "resource_version", "name", "size_bytes", "created_at"]
    list_filter = ["created_at"]
    search_fields = ["asset__name", "name"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(AssetPreview)
class AssetPreviewAdmin(admin.ModelAdmin):
    list_display = ["asset", "image_url", "title", "description", "order", "created_at"]
    search_fields = ["asset__name"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(AssetAccessRequest)
class AssetAccessRequestAdmin(admin.ModelAdmin):
    list_display = [
        "developer_user",
        "asset",
        "status",
        "intended_use",
        "created_at",
        "approved_at",
        "approved_by",
    ]
    list_filter = ["status", "intended_use", "created_at", "approved_at"]
    search_fields = ["developer_user__email", "asset__name", "developer_access_reason"]
    readonly_fields = ["created_at", "approved_at"]
    autocomplete_fields = ["developer_user", "asset", "approved_by"]

    fieldsets = (
        (
            "Request Information",
            {
                "fields": (
                    "developer_user",
                    "asset",
                    "developer_access_reason",
                    "intended_use",
                )
            },
        ),
        ("Admin Review", {"fields": ("status", "admin_response", "approved_by")}),
        (
            "Timestamps",
            {"fields": ("created_at", "approved_at"), "classes": ("collapse",)},
        ),
    )

    actions = ["approve_requests", "reject_requests"]

    @admin.action(description="Approve selected requests")
    def approve_requests(self, request, queryset):
        """Bulk approve access requests"""
        count = 0
        for access_request in queryset.filter(status="pending"):
            try:
                access_request.approve_request(approved_by_user=request.user, auto_approved=False)
                count += 1
            except Exception as e:
                self.message_user(
                    request,
                    f"Error approving request {access_request.id}: {e}",
                    level="ERROR",
                )

        self.message_user(request, f"Successfully approved {count} requests.")

    @admin.action(description="Reject selected requests")
    def reject_requests(self, request, queryset):
        """Bulk reject access requests"""
        count = 0
        for access_request in queryset.filter(status="pending"):
            try:
                access_request.reject_request(
                    rejected_by_user=request.user, reason="Bulk rejection from admin"
                )
                count += 1
            except Exception as e:
                self.message_user(
                    request,
                    f"Error rejecting request {access_request.id}: {e}",
                    level="ERROR",
                )

        self.message_user(request, f"Successfully rejected {count} requests.")

    def get_queryset(self, request):
        """Optimize queryset"""
        return (
            super().get_queryset(request).select_related("developer_user", "asset", "approved_by")
        )


@admin.register(AssetAccess)
class AssetAccessAdmin(admin.ModelAdmin):
    list_display = [
        "user",
        "asset",
        "effective_license",
        "granted_at",
        "expires_at",
        "is_active_status",
        "usage_count",
    ]
    list_filter = ["granted_at", "expires_at", "effective_license"]
    search_fields = ["user__email", "asset__name"]
    readonly_fields = ["granted_at", "usage_count"]
    raw_id_fields = ["user", "asset"]

    fieldsets = (
        ("Access Information", {"fields": ("asset_access_request", "user", "asset")}),
        ("License Information", {"fields": ("effective_license",)}),
        (
            "Access Details",
            {
                "fields": ("granted_at", "expires_at", "download_url"),
                "classes": ("collapse",),
            },
        ),
        ("Statistics", {"fields": ("usage_count",), "classes": ("collapse",)}),
    )

    def get_queryset(self, request):
        """Optimize queryset"""
        return super().get_queryset(request).select_related("user", "asset", "asset_access_request")

    @admin.display(description="Status")
    def is_active_status(self, obj):
        """Show if access is currently active"""
        return "✅ Active" if obj.is_active else "❌ Expired"

    @admin.display(description="Usage Events")
    def usage_count(self, obj):
        """Count usage events for this access"""
        return UsageEvent.objects.filter(developer_user=obj.user, asset_id=obj.asset.id).count()


@admin.register(UsageEvent)
class UsageEventAdmin(admin.ModelAdmin):
    """Admin for Usage Events"""

    list_display = ["developer_user", "usage_kind", "subject_kind", "created_at"]
    list_filter = ["usage_kind", "subject_kind", "created_at"]
    search_fields = ["developer_user__email"]
    readonly_fields = [
        "developer_user",
        "usage_kind",
        "subject_kind",
        "resource_id",
        "asset_id",
        "metadata",
        "ip_address",
        "user_agent",
        "created_at",
        "updated_at",
    ]

    # Make the model read-only in admin
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(Reciter)
class ReciterAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "name_ar", "slug", "is_active", "created_at"]
    list_filter = ["is_active", "created_at"]
    search_fields = ["name", "slug"]
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ["created_at", "updated_at"]


@admin.register(Riwayah)
class RiwayahAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "name_ar", "slug", "is_active", "created_at"]
    list_filter = ["is_active", "created_at"]
    search_fields = ["name", "slug"]
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ["created_at", "updated_at"]


@admin.register(RecitationSurahTrack)
class RecitationSurahTrackAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "asset",
        "surah_number",
        "surah_name",
        "surah_name_ar",
        "duration_ms",
        "size_bytes",
        "created_at",
    ]
    list_filter = ["asset", "created_at"]
    search_fields = ["asset__name", "surah_name", "surah_name_ar"]
    readonly_fields = [
        "surah_name",
        "surah_name_ar",
        "size_bytes",
        "duration_ms",
        "created_at",
        "updated_at",
    ]
    raw_id_fields = ["asset"]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("asset")

    change_list_template = "content/admin/recitationsurahtrack_changelist.html"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "bulk-upload/",
                self.admin_site.admin_view(self.bulk_upload_view),
                name="recitationsurahtrack_bulk_upload",
            ),
            path(
                "download-json/",
                self.admin_site.admin_view(self.download_json_view),
                name="recitationsurahtrack_download_json",
            ),
        ]
        return custom_urls + urls

    def bulk_upload_view(self, request):
        if request.method == "POST":
            form = BulkRecitationUploadForm(request.POST, request.FILES)
            if form.is_valid():
                asset = form.cleaned_data["asset"]
                files = request.FILES.getlist("audio_files")

                created = 0
                filename_errors = 0
                skipped_duplicates = 0
                other_errors = 0
                duplicate_details: list[str] = []
                other_error_details: list[str] = []
                uploaded_file_names: list[str] = []  # for best-effort cleanup on rollback
                seen_surahs: set[int] = set()  # duplicates within the same selection

                try:
                    with transaction.atomic():
                        for f in files:
                            try:
                                surah_number = extract_surah_number_from_filename(f.name)
                            except ValueError as e:
                                messages.error(request, str(e))
                                filename_errors += 1
                                continue

                            # Skip duplicate surah within this same upload selection
                            if surah_number in seen_surahs:
                                skipped_duplicates += 1
                                duplicate_details.append(f"{f.name} (duplicate in selection)")
                                continue
                            seen_surahs.add(surah_number)

                            # Skip if already exists in DB
                            if RecitationSurahTrack.objects.filter(
                                asset=asset, surah_number=surah_number
                            ).exists():
                                skipped_duplicates += 1
                                duplicate_details.append(f"{f.name} (already exists)")
                                continue

                            # Simple path: let Django storage handle the upload and create DB row
                            obj = RecitationSurahTrack.objects.create(
                                asset=asset,
                                surah_number=surah_number,
                                audio_file=f,
                            )
                            try:
                                if obj.audio_file and getattr(obj.audio_file, "name", None):
                                    uploaded_file_names.append(obj.audio_file.name)
                            except Exception:
                                pass
                            created += 1
                except Exception as e:
                    # Best-effort cleanup of any uploaded files when the DB transaction rolls back
                    try:
                        from django.core.files.storage import default_storage

                        for name in uploaded_file_names:
                            try:
                                default_storage.delete(name)
                            except Exception:
                                pass
                    except Exception:
                        pass

                    other_errors += 1
                    other_error_details.append(str(e))

                if created:
                    messages.success(
                        request,
                        f"Created {created} recitation tracks for asset {asset}.",
                    )
                if filename_errors:
                    messages.warning(
                        request,
                        f"{filename_errors} files were skipped due to filename issues.",
                    )
                if skipped_duplicates:
                    preview = ", ".join(duplicate_details[:10])
                    more = (
                        ""
                        if len(duplicate_details) <= 10
                        else f" and {len(duplicate_details) - 10} more"
                    )
                    messages.warning(
                        request,
                        f"Skipped {skipped_duplicates} files due to duplicates: {preview}{more}.",
                    )
                if other_errors:
                    preview = "; ".join(other_error_details[:5])
                    more = (
                        ""
                        if len(other_error_details) <= 5
                        else f" and {len(other_error_details) - 5} more"
                    )
                    messages.error(
                        request,
                        f"Upload encountered errors: {preview}{more}. All changes rolled back.",
                    )

                return redirect("admin:content_recitationsurahtrack_changelist")
        else:
            form = BulkRecitationUploadForm()

        # Provide surah name maps for client preview
        from apps.core.mixins.constants import SURAH_NUMBER_NAME_AR, SURAH_NUMBER_NAME_EN

        context = {
            **self.admin_site.each_context(request),
            "title": "Bulk upload recitation surah tracks",
            "form": form,
            "redirect_url": reverse("admin:content_recitationsurahtrack_changelist"),
            "surah_map_en": SURAH_NUMBER_NAME_EN,
            "surah_map_ar": SURAH_NUMBER_NAME_AR,
        }
        return render(
            request,
            "content/admin/recitationsurahtrack_bulk_upload.html",
            context,
        )

    def download_json_view(self, request):
        if request.method == "POST":
            form = DownloadRecitationsJsonForm(request.POST)
            if form.is_valid():
                import json

                asset = form.cleaned_data["asset"]
                tracks = (
                    RecitationSurahTrack.objects.filter(asset=asset)
                    .order_by("surah_number")
                    .only("surah_number", "audio_file", "duration_ms")
                )
                result: list[dict] = []
                for t in tracks:
                    try:
                        url = (
                            f"{CLOUDFLARE_R2_PUBLIC_BASE_URL}/media/{t.audio_file.name}"
                            if t.audio_file
                            else ""
                        )
                    except Exception:
                        url = ""
                    result.append(
                        {
                            "surah_number": int(t.surah_number),
                            "surah_name": SURAH_NUMBER_NAME_EN[int(t.surah_number)],
                            "surah_name_ar": SURAH_NUMBER_NAME_AR[int(t.surah_number)],
                            "audio_file": url,
                            "duration_ms": int(t.duration_ms or 0),
                            "ayah_timings": [],
                        }
                    )

                payload = json.dumps(result, ensure_ascii=False, indent=2)
                filename = f"asset_{asset.id}_recitations.json"
                response = HttpResponse(payload, content_type="application/json; charset=utf-8")
                response["Content-Disposition"] = f'attachment; filename="{filename}"'
                return response
        else:
            form = DownloadRecitationsJsonForm()

        context = {
            **self.admin_site.each_context(request),
            "title": "Download JSON file for Mushaf tracks",
            "form": form,
        }
        return render(
            request,
            "content/admin/recitationsurahtrack_download_json.html",
            context,
        )


@admin.register(RecitationAyahTiming)
class RecitationAyahTimingAdmin(admin.ModelAdmin):
    list_display = ["id", "track", "ayah_key", "start_ms", "end_ms", "duration_ms"]
    list_filter = ["track__asset", "track__surah_number"]
    search_fields = ["ayah_key", "track__surah_name"]
    readonly_fields = ["created_at", "updated_at", "duration_ms"]
    raw_id_fields = ["track"]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("track", "track__asset")
