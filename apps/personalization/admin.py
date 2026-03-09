from django.contrib import admin

from apps.personalization.models import Bookmark, Favorite, ListeningHistory, UserPreference


@admin.register(Favorite)
class FavoriteAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "content_type", "object_id", "created_at")
    list_filter = ("content_type",)
    search_fields = ("user__email",)
    raw_id_fields = ("user",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(Bookmark)
class BookmarkAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "asset", "surah_number", "position_ms", "created_at")
    list_filter = ("created_at",)
    search_fields = ("user__email", "asset__name")
    raw_id_fields = ("user", "asset")
    readonly_fields = ("created_at", "updated_at")


@admin.register(ListeningHistory)
class ListeningHistoryAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "asset", "surah_number", "last_position_ms", "played_at")
    list_filter = ("played_at",)
    search_fields = ("user__email", "asset__name")
    raw_id_fields = ("user", "asset")
    readonly_fields = ("created_at", "updated_at")


@admin.register(UserPreference)
class UserPreferenceAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "audio_quality", "language", "updated_at")
    search_fields = ("user__email",)
    raw_id_fields = ("user",)
    readonly_fields = ("created_at", "updated_at")
