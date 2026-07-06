from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.content.cache import invalidate_recitation_tracks_cache
from apps.content.models import RecitationSurahTrack


@receiver(post_save, sender=RecitationSurahTrack)
@receiver(post_delete, sender=RecitationSurahTrack)
def clear_recitation_tracks_cache(sender, instance: RecitationSurahTrack, **kwargs) -> None:
    invalidate_recitation_tracks_cache(instance.asset_id)
