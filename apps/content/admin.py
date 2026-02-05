import json
import logging

from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.db.models import Count
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.html import format_html

from apps.content.services.admin.asset_recitation_audio_tracks_direct_upload_service import (
    AssetRecitationAudioTracksDirectUploadService,
)
from apps.content.services.admin.asset_recitation_json_file_sync_service import (
    sync_asset_recitations_json_file,
)
from apps.core.ninja_utils.errors import ItqanError

from ..core.mixins.constants import QURAN_SURAHS
from .forms.direct_upload_recitations_form import DirectUploadRecitationsForm
from .forms.recitation_audio_tracks_bulk_upload_form import RecitationAudioTracksBulkUploadForm
from .forms.recitation_ayah_timestamps_bulk_upload_form import (
    RecitationAyahTimestampsBulkUploadForm,
)
from .models import (
    Asset,
    AssetAccess,
    AssetAccessRequest,
    AssetPreview,
    AssetVersion,
    Qiraah,
    RecitationAyahTiming,
    RecitationSurahTrack,
    Reciter,
    Resource,
    ResourceVersion,
    Riwayah,
    UsageEvent,
)
from .services.admin.asset_recitation_audio_tracks_upload_service import (
    bulk_upload_recitation_audio_tracks,
)
from .services.admin.asset_recitation_ayah_timestamps_upload_service import (
    bulk_upload_recitation_ayah_timestamps,
)

logger = logging.getLogger(__name__)


class ResourceVersionInline(admin.TabularInline):
    model = ResourceVersion
    extra = 0
    fields = ["semvar", "storage_url"]
    readonly_fields = ["created_at"]


class AssetVersionInline(admin.TabularInline):
    model = AssetVersion
    extra = 0
    fields = ["resource_version", "file_url"]
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
        "size_bytes",
        "created_at",
    ]
    list_filter = ["created_at"]
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

    # Custom change form for actions for recitation assets
    change_form_template = "content/admin/asset_change_form.html"

    fieldsets = (
        (
            "Basic Information",
            {
                "fields": ("name", "resource", "category", "riwayah"),
            },
        ),
        (
            "Recitation Details",
            {
                "fields": ("reciter", "madd_level", "meem_behaviour", "year"),
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

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "<int:asset_id>/sync-recitations-json/",
                self.admin_site.admin_view(self.sync_recitations_json_view),
                name="asset_sync_recitations_json",
            ),
            path(
                "<int:asset_id>/bulk-upload-audio-tracks/",
                self.admin_site.admin_view(self.bulk_upload_audio_tracks_view),
                name="asset_bulk_upload_recitation_audio_tracks",
            ),
            path(
                "<int:asset_id>/bulk-upload-ayahs-timestamps/",
                self.admin_site.admin_view(self.bulk_upload_ayahs_timestamps_view),
                name="asset_bulk_upload_recitation_ayah_timestamps",
            ),
            path(
                "validate-recitation-filenames/",
                self.admin_site.admin_view(self.validate_recitation_filenames_view),
                name="asset_validate_recitation_filenames",
            ),
            path(
                "<int:asset_id>/recitations/direct-upload/",
                self.admin_site.admin_view(self.upload_page),
                name="asset_direct_upload_recitations",
            ),
            path(
                "uploads/start/",
                self.admin_site.admin_view(self.uploads_start_view),
                name="asset_uploads_start",
            ),
            path(
                "uploads/sign-part/",
                self.admin_site.admin_view(self.uploads_sign_part_view),
                name="asset_uploads_sign_part",
            ),
            path(
                "uploads/finish/",
                self.admin_site.admin_view(self.uploads_finish_view),
                name="asset_uploads_finish",
            ),
            path(
                "uploads/abort/",
                self.admin_site.admin_view(self.uploads_abort_view),
                name="asset_uploads_abort",
            ),
        ]
        return custom_urls + urls

    def sync_recitations_json_view(self, request, asset_id: int):
        if request.method != "POST":
            return redirect(reverse("admin:content_asset_change", args=[asset_id]))

        try:
            sync_asset_recitations_json_file(asset_id=asset_id)
        except Exception as e:
            self.message_user(request, f"Sync failed: {e}", level="ERROR")
            return redirect(reverse("admin:content_asset_change", args=[asset_id]))

        self.message_user(request, "Asset Recitation Downloaded JSON File Synced Successfully.")
        return redirect(reverse("admin:content_asset_change", args=[asset_id]))

    def bulk_upload_audio_tracks_view(self, request, asset_id: int):
        if request.method == "POST":
            form = RecitationAudioTracksBulkUploadForm(request.POST, request.FILES)
            if form.is_valid():
                files = request.FILES.getlist("audio_files")

                # Parse durations if provided
                durations_by_filename = {}
                durations_json = request.POST.get("durations_json")
                if durations_json:
                    try:
                        durations_by_filename = json.loads(durations_json)
                    except Exception:
                        pass  # Silently ignore invalid JSON, fallback to mutagen

                stats = bulk_upload_recitation_audio_tracks(
                    asset_id=asset_id, files=files, durations_by_filename=durations_by_filename
                )

                if stats.get("created"):
                    self.message_user(request, f"Created {stats['created']} recitation tracks.")
                if stats.get("filename_errors"):
                    self.message_user(
                        request,
                        f"{stats['filename_errors']} files were skipped due to filename issues.",
                        level="WARNING",
                    )
                if stats.get("skipped_duplicates"):
                    preview_details = stats.get("duplicate_details") or []
                    preview = ", ".join(preview_details[:10])
                    more = "" if len(preview_details) <= 10 else f" and {len(preview_details) - 10} more"
                    self.message_user(
                        request,
                        f"Skipped {stats['skipped_duplicates']} files due to duplicates: {preview}{more}.",
                        level="WARNING",
                    )
                if stats.get("other_errors"):
                    error_details = stats.get("other_error_details") or []
                    preview = "; ".join(error_details[:5])
                    more = "" if len(error_details) <= 5 else f" and {len(error_details) - 5} more"
                    self.message_user(
                        request, f"Upload encountered errors: {preview}{more}. All changes rolled back.", level="ERROR"
                    )

                return redirect(reverse("admin:content_asset_change", args=[asset_id]))
        else:
            form = RecitationAudioTracksBulkUploadForm()

        context = {
            **self.admin_site.each_context(request),
            "title": "Bulk Upload Recitation Audio Tracks",
            "form": form,
            "redirect_url": reverse("admin:content_asset_change", args=[asset_id]),
            "surah_map_ar": {k: v.get("name", "") for k, v in QURAN_SURAHS.items()},
            "surah_map_en": {k: v.get("name_en", "") for k, v in QURAN_SURAHS.items()},
        }
        return render(
            request,
            "content/admin/recitationsurahtrack_bulk_upload.html",
            context,
        )

    def bulk_upload_ayahs_timestamps_view(self, request, asset_id: int):
        if request.method == "POST":
            form = RecitationAyahTimestampsBulkUploadForm(request.POST, request.FILES)
            if form.is_valid():
                files = request.FILES.getlist("json_files")

                stats = bulk_upload_recitation_ayah_timestamps(
                    asset_id=asset_id,
                    files=files,
                )

                if stats.get("missing_tracks"):
                    self.message_user(
                        request,
                        f"Missing RecitationSurahTrack for surah(s): {stats['missing_tracks']} (asset_id={asset_id})",
                        level="WARNING",
                    )
                if stats.get("file_errors"):
                    preview = "; ".join(stats["file_errors"][:5])
                    more = "" if len(stats["file_errors"]) <= 5 else f" and {len(stats['file_errors']) - 5} more"
                    self.message_user(request, f"Some files failed to parse: {preview}{more}", level="WARNING")

                self.message_user(
                    request,
                    f"Done. created={stats.get('created_total',0)}, updated={stats.get('updated_total',0)}, "
                    f"skipped={stats.get('skipped_total',0)}, files={len(files)}, asset_id={asset_id}",
                )
                return redirect(reverse("admin:content_asset_change", args=[asset_id]))
        else:
            form = RecitationAyahTimestampsBulkUploadForm()

        context = {
            **self.admin_site.each_context(request),
            "title": "Bulk Upload Recitation Ayah Timestamps",
            "form": form,
        }
        return render(
            request,
            "content/admin/recitationayahtiming_bulk_upload.html",
            context,
        )

    # -------- Direct-to-R2 Upload Views (Admin-only) --------
    def upload_page(self, request: HttpRequest, asset_id: int) -> HttpResponse:
        if not request.user.is_staff:
            raise PermissionDenied("Staff only")
        form = DirectUploadRecitationsForm()
        ctx = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "asset_id": asset_id,
            "title": "Direct Upload Recitation Tracks",
            "form": form,
            "redirect_url": reverse("admin:content_asset_change", args=[asset_id]),
            "surah_map_ar": {k: v.get("name", "") for k, v in QURAN_SURAHS.items()},
            "surah_map_en": {k: v.get("name_en", "") for k, v in QURAN_SURAHS.items()},
        }
        return TemplateResponse(request, "content/admin/direct_upload_recitations.html", ctx)

    def uploads_start_view(self, request: HttpRequest) -> JsonResponse:
        if not request.user.is_staff:
            raise PermissionDenied("Staff only")
        if request.method != "POST":
            return JsonResponse({"error_name": "method_not_allowed", "message": "POST required"}, status=405)
        try:
            if request.content_type == "application/json":
                body = json.loads(request.body or "{}")
                asset_id = int(body.get("assetId"))
                filename = str(body.get("filename", "")).strip()
                duration_ms = body.get("durationMs")
                if duration_ms is not None:
                    duration_ms = int(duration_ms)
            else:
                asset_id = int(request.POST.get("assetId"))
                filename = str(request.POST.get("filename", "")).strip()
                duration_ms = request.POST.get("durationMs")
                if duration_ms is not None:
                    duration_ms = int(duration_ms)
            service = AssetRecitationAudioTracksDirectUploadService()
            data = service.start_upload(asset_id=asset_id, filename=filename, duration_ms=duration_ms)
            return JsonResponse(data)
        except ItqanError as e:
            return JsonResponse(
                {"error_name": e.error_name, "message": e.message, "extra": e.extra}, status=e.status_code
            )
        except Exception:
            logger.exception(f"uploads_start_view failed (asset_id={locals().get('asset_id')})")
            return JsonResponse(
                {"error_name": "server_error", "message": "An unexpected error occurred"},
                status=500,
            )

    def uploads_sign_part_view(self, request: HttpRequest) -> JsonResponse:
        if not request.user.is_staff:
            raise PermissionDenied("Staff only")
        if request.method != "POST":
            return JsonResponse({"error_name": "method_not_allowed", "message": "POST required"}, status=405)
        try:
            body = json.loads(request.body or "{}")
            service = AssetRecitationAudioTracksDirectUploadService()
            url = service.sign_part(
                key=body["key"],
                upload_id=body["uploadId"],
                part_number=int(body["partNumber"]),
                expires_in=3600,
            )
            return JsonResponse({"url": url})
        except ItqanError as e:
            return JsonResponse(
                {"error_name": e.error_name, "message": e.message, "extra": e.extra}, status=e.status_code
            )
        except Exception:
            logger.exception(
                f"uploads_sign_part_view failed (\
                    key={(locals().get('body') or {}).get('key')},\
                    upload_id={(locals().get('body') or {}).get('uploadId')},\
                    part_number={(locals().get('body') or {}).get('partNumber')}\
                )"
            )
            return JsonResponse(
                {"error_name": "server_error", "message": "An unexpected error occurred"},
                status=500,
            )

    def uploads_finish_view(self, request: HttpRequest) -> JsonResponse:
        if not request.user.is_staff:
            raise PermissionDenied("Staff only")
        if request.method != "POST":
            return JsonResponse({"error_name": "method_not_allowed", "message": "POST required"}, status=405)
        try:
            body = json.loads(request.body or "{}")
            service = AssetRecitationAudioTracksDirectUploadService()
            result = service.finish_upload(key=body["key"], upload_id=body["uploadId"], parts=body["parts"])
            return JsonResponse(result)
        except ItqanError as e:
            return JsonResponse(
                {"error_name": e.error_name, "message": e.message, "extra": e.extra}, status=e.status_code
            )
        except Exception:
            logger.exception(
                f"uploads_finish_view failed (\
                    key={(locals().get('body') or {}).get('key')},\
                    upload_id={(locals().get('body') or {}).get('uploadId')}\
                )"
            )
            return JsonResponse(
                {"error_name": "server_error", "message": "An unexpected error occurred"},
                status=500,
            )

    def uploads_abort_view(self, request: HttpRequest) -> JsonResponse:
        if not request.user.is_staff:
            raise PermissionDenied("Staff only")
        if request.method != "POST":
            return JsonResponse({"error_name": "method_not_allowed", "message": "POST required"}, status=405)
        try:
            body = json.loads(request.body or "{}")
            service = AssetRecitationAudioTracksDirectUploadService()
            result = service.abort_upload(key=body["key"], upload_id=body["uploadId"])
            return JsonResponse(result)
        except ItqanError as e:
            return JsonResponse(
                {"error_name": e.error_name, "message": e.message, "extra": e.extra}, status=e.status_code
            )
        except Exception:
            logger.exception(
                f"uploads_abort_view failed (\
                    key={(locals().get('body') or {}).get('key')},\
                    upload_id={(locals().get('body') or {}).get('uploadId')}\
                )"
            )
            return JsonResponse(
                {"error_name": "server_error", "message": "An unexpected error occurred"},
                status=500,
            )

    def validate_recitation_filenames_view(self, request: HttpRequest) -> JsonResponse:
        if not request.user.is_staff:
            raise PermissionDenied("Staff only")
        if request.method != "POST":
            return JsonResponse({"error_name": "method_not_allowed", "message": "POST required"}, status=405)

        try:
            from apps.mixins.recitations_helpers import extract_surah_number_from_mp3_filename

            # Parse request
            if request.content_type == "application/json":
                body = json.loads(request.body or "{}")
                filenames = body.get("filenames", [])
                asset_id = body.get("asset_id")
            else:
                filenames = request.POST.getlist("filenames")
                asset_id = request.POST.get("asset_id")

            if not filenames:
                return JsonResponse({"results": []})

            # Validate each filename
            results = []
            for filename in filenames:
                try:
                    surah_number = extract_surah_number_from_mp3_filename(filename)

                    # Check if track already exists in database
                    exists = False
                    if asset_id:
                        exists = RecitationSurahTrack.objects.filter(
                            asset_id=int(asset_id),
                            surah_number=surah_number,
                        ).exists()

                    # Get surah names
                    surah_info = QURAN_SURAHS.get(surah_number, {})

                    results.append(
                        {
                            "filename": filename,
                            "valid": True,
                            "surah_number": surah_number,
                            "exists": exists,
                            "surah_name_en": surah_info.get("name_en", ""),
                            "surah_name_ar": surah_info.get("name", ""),
                        }
                    )
                except ItqanError as e:
                    results.append(
                        {
                            "filename": filename,
                            "valid": False,
                            "error_name": e.error_name,
                            "error_message": e.message,
                        }
                    )
                except Exception as e:
                    results.append(
                        {
                            "filename": filename,
                            "valid": False,
                            "error_name": "validation_error",
                            "error_message": str(e),
                        }
                    )

            return JsonResponse({"results": results})
        except Exception as e:
            return JsonResponse({"error_name": "server_error", "message": str(e)}, status=500)


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
                access_request.reject_request(rejected_by_user=request.user, reason="Bulk rejection from admin")
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
        return super().get_queryset(request).select_related("developer_user", "asset", "approved_by")


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


@admin.register(Qiraah)
class QiraahAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "slug", "is_active", "created_at"]
    list_filter = ["is_active", "created_at"]
    search_fields = ["name", "slug"]
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ["created_at", "updated_at"]

    fieldsets = (
        (
            "Basic Information",
            {
                "fields": ("name", "slug", "is_active"),
            },
        ),
        (
            "Multilingual Fields",
            {
                "fields": (
                    "name_en",
                    "name_ar",
                ),
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


@admin.register(Reciter)
class ReciterAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "slug", "is_active", "created_at"]
    list_filter = ["is_active", "created_at"]
    search_fields = ["name", "slug"]
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ["created_at", "updated_at"]

    fieldsets = (
        (
            "Basic Information",
            {
                "fields": ("name", "slug", "is_active"),
            },
        ),
        (
            "Multilingual Fields",
            {
                "fields": (
                    "name_en",
                    "name_ar",
                ),
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


@admin.register(Riwayah)
class RiwayahAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "slug", "qiraah", "is_active", "created_at"]
    list_filter = ["is_active", "qiraah", "created_at"]
    search_fields = ["name", "slug"]
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ["created_at", "updated_at"]

    fieldsets = (
        (
            "Basic Information",
            {
                "fields": ("qiraah", "name", "slug", "is_active"),
            },
        ),
        (
            "Multilingual Fields",
            {
                "fields": (
                    "name_en",
                    "name_ar",
                ),
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


@admin.register(RecitationSurahTrack)
class RecitationSurahTrackAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "asset",
        "surah_number",
        "surah_name",
        "surah_name_en",
        "duration_ms",
        "size_bytes",
        "created_at",
    ]
    list_filter = ["asset", "created_at"]
    search_fields = ["asset__name"]
    readonly_fields = [
        "surah_name",
        "surah_name_en",
        "original_filename",
        "size_bytes",
        "duration_ms",
        "created_at",
        "updated_at",
        "upload_finished_at",
    ]

    @admin.display(description="Surah Name (AR)", ordering="surah_number")
    def surah_name(self, obj: RecitationSurahTrack) -> str | None:
        if obj.surah_number:
            return QURAN_SURAHS[obj.surah_number]["name"]

    @admin.display(description="Surah Name (EN)", ordering="surah_number")
    def surah_name_en(self, obj: RecitationSurahTrack) -> str | None:
        if obj.surah_number:
            return QURAN_SURAHS[obj.surah_number]["name_en"]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("asset")


@admin.register(RecitationAyahTiming)
class RecitationAyahTimingAdmin(admin.ModelAdmin):
    list_display = ["id", "track", "surah_name", "ayah_key", "start_ms", "end_ms", "duration_ms"]
    list_filter = ["track__asset", "track__surah_number"]
    search_fields = ["ayah_key", "track__surah_number"]
    readonly_fields = ["created_at", "updated_at"]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("track", "track__asset")

    @admin.display(description="Surah Name (AR)", ordering="track__surah_number")
    def surah_name(self, obj: RecitationAyahTiming) -> str:
        return QURAN_SURAHS[obj.track.surah_number]["name"]
