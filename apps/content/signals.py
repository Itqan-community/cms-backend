from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.content.cache import invalidate_recitation_tracks_cache
from apps.content.models import Asset, CategoryChoice, RecitationFolder, RecitationSurahTrack


@receiver(post_save, sender=RecitationSurahTrack)
@receiver(post_delete, sender=RecitationSurahTrack)
def clear_recitation_tracks_cache(sender, instance: RecitationSurahTrack, **kwargs) -> None:
    invalidate_recitation_tracks_cache(instance.asset_id)


@receiver(post_save, sender=Asset)
def create_default_recitation_folder(sender, instance: Asset, created: bool, **kwargs) -> None:
    """
    Give every new recitation Asset its default folder.

    Tracks require a folder, and the APIs fall back to the default one whenever a
    caller does not name a variant. Doing this on the signal rather than in the
    repository means the invariant also holds for assets created through Django
    admin, fixtures, or data imports -- not just through the service layer.
    """
    if not created or instance.category != CategoryChoice.RECITATION:
        return

    RecitationFolder.objects.get_or_create(
        asset=instance,
        is_default=True,
        defaults={
            "name": RecitationFolder.DEFAULT_NAME_AR,
            "name_ar": RecitationFolder.DEFAULT_NAME_AR,
            "name_en": RecitationFolder.DEFAULT_NAME_EN,
            "slug": RecitationFolder.DEFAULT_SLUG,
        },
    )
