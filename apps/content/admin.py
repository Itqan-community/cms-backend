from django.contrib import admin, messages
from django.db import transaction
from django.db.models import Count
from django.shortcuts import redirect, render
from django.urls import path, reverse
from django.utils.html import format_html

from ..core.mixins.constants import QURAN_SURAHS
from ..mixins.recitations_helpers import extract_surah_number_from_filename
from .forms.bulk_recitation_timings_upload_form import BulkRecitationTimingsUploadForm
from .forms.bulk_recitations_upload_form import BulkRecitationUploadForm
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
from .services.asset_recitations_sync import sync_asset_recitations_downloadable_json_file
from .services.ayah_timings_import import parse_json_bytes


class ResourceVersionInline(admin.TabularInline):
    model = ResourceVersion
    extra = 0
    fields = ["semvar", "file_type", "is_latest", "storage_url"]
    readonly_fields = ["created_at"]


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

    # Custom change form for actions for recitation assets
    change_form_template = "content/admin/asset_change_form.html"

    fieldsets = (
        (
            "Basic Information",
            {
                "fields": ("name", "resource", "category", "reciter", "riwayah"),
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
        ]
        return custom_urls + urls

    def sync_recitations_json_view(self, request, asset_id: int):
        if request.method != "POST":
            return redirect(reverse("admin:content_asset_change", args=[asset_id]))

        try:
            sync_asset_recitations_downloadable_json_file(asset_id=asset_id)
        except Exception as e:
            self.message_user(request, f"Sync failed: {e}", level="ERROR")
            return redirect(reverse("admin:content_asset_change", args=[asset_id]))

        self.message_user(request, "Asset Recitation Downloaded JSON File Synced Successfully.")
        return redirect(reverse("admin:content_asset_change", args=[asset_id]))


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
    search_fields = ["asset__name", "surah_name", "surah_name_en"]
    readonly_fields = [
        "surah_name",
        "surah_name_en",
        "size_bytes",
        "duration_ms",
        "created_at",
        "updated_at",
    ]

    @admin.display(description="Surah Name (AR)", ordering="surah_number")
    def surah_name(self, obj: RecitationSurahTrack) -> str:
        return QURAN_SURAHS[obj.surah_number]["name"]

    @admin.display(description="Surah Name (EN)", ordering="surah_number")
    def surah_name_en(self, obj: RecitationSurahTrack) -> str:
        return QURAN_SURAHS[obj.surah_number]["name_en"]

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
                            if RecitationSurahTrack.objects.filter(asset=asset, surah_number=surah_number).exists():
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
                    more = "" if len(duplicate_details) <= 10 else f" and {len(duplicate_details) - 10} more"
                    messages.warning(
                        request,
                        f"Skipped {skipped_duplicates} files due to duplicates: {preview}{more}.",
                    )
                if other_errors:
                    preview = "; ".join(other_error_details[:5])
                    more = "" if len(other_error_details) <= 5 else f" and {len(other_error_details) - 5} more"
                    messages.error(
                        request,
                        f"Upload encountered errors: {preview}{more}. All changes rolled back.",
                    )

                return redirect("admin:content_recitationsurahtrack_changelist")
        else:
            form = BulkRecitationUploadForm()

        context = {
            **self.admin_site.each_context(request),
            "title": "Bulk upload recitation surah tracks",
            "form": form,
            "redirect_url": reverse("admin:content_recitationsurahtrack_changelist"),
            "surah_map_ar": {k: v.get("name", "") for k, v in QURAN_SURAHS.items()},
            "surah_map_en": {k: v.get("name_en", "") for k, v in QURAN_SURAHS.items()},
        }
        return render(
            request,
            "content/admin/recitationsurahtrack_bulk_upload.html",
            context,
        )


@admin.register(RecitationAyahTiming)
class RecitationAyahTimingAdmin(admin.ModelAdmin):
    list_display = ["id", "track", "surah_name", "ayah_key", "start_ms", "end_ms", "duration_ms"]
    list_filter = ["track__asset", "track__surah_number"]
    search_fields = ["ayah_key", "track__surah_number"]
    readonly_fields = ["created_at", "updated_at"]
    change_list_template = "content/admin/recitationayahtiming_changelist.html"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("track", "track__asset")

    @admin.display(description="Surah Name", ordering="track__surah_number")
    def surah_name(self, obj: RecitationAyahTiming) -> str:
        return QURAN_SURAHS[obj.track.surah_number]["name"]

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "import-ayah-timings/",
                self.admin_site.admin_view(self.import_ayah_timings_view),
                name="recitationayahtiming_import",
            ),
        ]
        return custom_urls + urls

    def import_ayah_timings_view(self, request):
        if request.method == "POST":
            form = BulkRecitationTimingsUploadForm(request.POST, request.FILES)
            if form.is_valid():
                asset = form.cleaned_data["asset"]
                files = request.FILES.getlist("json_files")
                overwrite: bool = form.cleaned_data.get("overwrite", False)
                dry_run: bool = form.cleaned_data.get("dry_run", True)

                # Preload tracks for the asset
                tracks = RecitationSurahTrack.objects.filter(asset=asset).only("id", "surah_number")
                track_by_surah = {t.surah_number: t for t in tracks}

                created_total = 0
                updated_total = 0
                skipped_total = 0
                missing_tracks: list[int] = []
                file_errors: list[str] = []

                try:
                    with transaction.atomic():
                        for f in files:
                            try:
                                surah_number, rows = parse_json_bytes(f.read())
                            except Exception as e:
                                file_errors.append(f"{f.name}: {e}")
                                continue

                            track = track_by_surah.get(surah_number)
                            if not track:
                                missing_tracks.append(surah_number)
                                continue

                            existing = {
                                t.ayah_key: t
                                for t in RecitationAyahTiming.objects.filter(track=track).only(
                                    "id", "ayah_key", "start_ms", "end_ms", "duration_ms"
                                )
                            }

                            to_create: list[RecitationAyahTiming] = []
                            to_update: list[RecitationAyahTiming] = []

                            for row in rows:
                                obj: RecitationAyahTiming | None = existing.get(row.ayah_key)
                                if not obj:
                                    to_create.append(
                                        RecitationAyahTiming(
                                            track=track,
                                            ayah_key=row.ayah_key,
                                            start_ms=row.start_ms,
                                            end_ms=row.end_ms,
                                            duration_ms=row.duration_ms,
                                        )
                                    )
                                    continue

                                if not overwrite:
                                    skipped_total += 1
                                    continue

                                changed = (
                                    obj.start_ms != row.start_ms
                                    or obj.end_ms != row.end_ms
                                    or obj.duration_ms != row.duration_ms
                                )
                                if changed:
                                    obj.start_ms = row.start_ms
                                    obj.end_ms = row.end_ms
                                    obj.duration_ms = row.duration_ms
                                    to_update.append(obj)
                                else:
                                    skipped_total += 1

                            if to_create and not dry_run:
                                RecitationAyahTiming.objects.bulk_create(to_create, batch_size=2000)
                            if to_update and not dry_run:
                                RecitationAyahTiming.objects.bulk_update(
                                    to_update, fields=["start_ms", "end_ms", "duration_ms"], batch_size=2000
                                )

                            created_total += len(to_create)
                            updated_total += len(to_update)

                        if dry_run:
                            transaction.set_rollback(True)
                except Exception as e:
                    messages.error(request, f"Import failed: {e}")
                    return redirect("admin:content_recitationayahtiming_changelist")

                if missing_tracks:
                    missing_tracks = sorted(set(missing_tracks))
                    messages.warning(
                        request,
                        f"Missing RecitationSurahTrack for surah(s): {missing_tracks} (asset_id={asset.id})",
                    )
                if file_errors:
                    preview = "; ".join(file_errors[:5])
                    more = "" if len(file_errors) <= 5 else f" and {len(file_errors) - 5} more"
                    messages.warning(request, f"Some files failed to parse: {preview}{more}")

                messages.success(
                    request,
                    f"Done. created={created_total}, updated={updated_total}, skipped={skipped_total}, "
                    f"files={len(files)}, asset_id={asset.id}, dry_run={dry_run}, overwrite={overwrite}",
                )
                return redirect("admin:content_recitationayahtiming_changelist")
        else:
            # Default dry_run enabled
            form = BulkRecitationTimingsUploadForm(initial={"dry_run": True})

        context = {
            **self.admin_site.each_context(request),
            "title": "Import ayah timings from JSON files",
            "form": form,
        }
        return render(
            request,
            "content/admin/recitationayahtiming_import.html",
            context,
        )
