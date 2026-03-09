from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import BaseModel


class Favorite(BaseModel):
    """
    Polymorphic favorite — users can favorite Reciters, Resources, or Assets.
    Uses Django ContentType framework (same pattern as ContentIssueReport).
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="favorites",
        help_text="User who favorited this item",
    )

    content_type = models.ForeignKey(
        "contenttypes.ContentType",
        on_delete=models.CASCADE,
        limit_choices_to={"model__in": ["reciter", "resource", "asset"]},
        help_text="Django ContentType for the favorited object",
    )

    object_id = models.PositiveIntegerField(help_text="ID of the favorited content object")

    content_object = GenericForeignKey("content_type", "object_id")

    class Meta:
        verbose_name = "Favorite"
        verbose_name_plural = "Favorites"
        unique_together = [["user", "content_type", "object_id"]]
        indexes = [
            models.Index(fields=["content_type", "object_id"]),
            models.Index(fields=["user", "created_at"]),
        ]

    def __str__(self) -> str:
        content_type_name = self.content_type.model if self.content_type else "unknown"
        return f"Favorite(user={self.user_id}, content={content_type_name}:{self.object_id})"


class Bookmark(BaseModel):
    """
    Audio bookmark — users can save a playback position on an Asset
    with an optional note for reference.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="bookmarks",
        help_text="User who created this bookmark",
    )

    asset = models.ForeignKey(
        "content.Asset",
        on_delete=models.CASCADE,
        related_name="bookmarks",
        help_text="Asset being bookmarked",
    )

    surah_number = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text="Surah number (1..114) if bookmarking a specific surah track",
    )

    position_ms = models.PositiveIntegerField(
        help_text="Playback position in milliseconds for resume functionality",
    )

    note = models.TextField(
        blank=True,
        default="",
        help_text="Optional user note for this bookmark (max 500 characters)",
    )

    class Meta:
        verbose_name = "Bookmark"
        verbose_name_plural = "Bookmarks"
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["user", "asset"]),
        ]

    def __str__(self) -> str:
        return f"Bookmark(user={self.user_id}, asset={self.asset_id}, position={self.position_ms}ms)"

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.note and len(self.note) > 500:
            raise ValidationError({"note": "Note cannot exceed 500 characters."})


class ListeningHistory(BaseModel):
    """
    Listening history — tracks when users listen to audio assets.
    Uses upsert pattern: one entry per user + asset + surah_number, updated on replay.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="listening_history",
        help_text="User who listened",
    )

    asset = models.ForeignKey(
        "content.Asset",
        on_delete=models.CASCADE,
        related_name="listening_history",
        help_text="Asset that was listened to",
    )

    surah_number = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text="Surah number if listening to a specific surah track",
    )

    last_position_ms = models.PositiveIntegerField(
        default=0,
        help_text="Last playback position in milliseconds (for resume)",
    )

    duration_listened_ms = models.PositiveIntegerField(
        default=0,
        help_text="Total duration listened in this session (milliseconds)",
    )

    played_at = models.DateTimeField(
        help_text="When the playback session occurred",
    )

    class Meta:
        verbose_name = "Listening History"
        verbose_name_plural = "Listening History"
        unique_together = [["user", "asset", "surah_number"]]
        indexes = [
            models.Index(fields=["user", "-played_at"]),
        ]

    def __str__(self) -> str:
        surah = f", surah={self.surah_number}" if self.surah_number else ""
        return f"ListeningHistory(user={self.user_id}, asset={self.asset_id}{surah})"


class UserPreference(BaseModel):
    """
    User preferences — stores personalization settings such as preferred reciters,
    qiraah/riwayah, audio quality, language, and notification settings.
    """

    class AudioQualityChoice(models.TextChoices):
        LOW = "low", _("Low")
        MEDIUM = "medium", _("Medium")
        HIGH = "high", _("High")

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="preference",
        help_text="User these preferences belong to",
    )

    preferred_reciter_ids = models.JSONField(
        default=list,
        blank=True,
        help_text="List of preferred Reciter IDs",
    )

    preferred_qiraah_ids = models.JSONField(
        default=list,
        blank=True,
        help_text="List of preferred Qiraah IDs",
    )

    preferred_riwayah_ids = models.JSONField(
        default=list,
        blank=True,
        help_text="List of preferred Riwayah IDs",
    )

    audio_quality = models.CharField(
        max_length=10,
        choices=AudioQualityChoice.choices,
        default=AudioQualityChoice.HIGH,
        help_text="Preferred audio quality",
    )

    language = models.CharField(
        max_length=10,
        default="en",
        help_text="Preferred language code (e.g. 'en', 'ar')",
    )

    notification_settings = models.JSONField(
        default=dict,
        blank=True,
        help_text="Notification preferences (e.g. {new_content: true, recommendations: true})",
    )

    class Meta:
        verbose_name = "User Preference"
        verbose_name_plural = "User Preferences"

    def __str__(self) -> str:
        return f"UserPreference(user={self.user_id})"
