from django.db import transaction
from django.db.models.signals import m2m_changed, post_delete, post_save
from django.dispatch import receiver

from apps.content.cache import invalidate_portal_asset_counts, invalidate_recitation_tracks_cache
from apps.content.models import ASSET_CHANNEL_FIELDS, Asset, CategoryChoice, RecitationQuality, RecitationSurahTrack


@receiver(post_save, sender=RecitationSurahTrack)
@receiver(post_delete, sender=RecitationSurahTrack)
def clear_recitation_tracks_cache(sender, instance: RecitationSurahTrack, **kwargs) -> None:
    invalidate_recitation_tracks_cache(instance.asset_id)


@receiver(post_save, sender=Asset)
def clear_public_recitation_cache_on_access_policy_change(
    sender, instance: Asset, update_fields=None, **kwargs
) -> None:
    """
    Bust the public recitation caches whenever the access policy may have changed.

    Both warm paths (track-list and range) authorize from the cached asset
    metadata, so a flip of ``is_open_access`` or the channel flags
    must drop it -- otherwise the warm path keeps serving a stale allow/deny
    decision for up to the meta TTL (CWE-862/863).

    The deletion is deferred to ``transaction.on_commit``: writers like
    ``RecitationRepository.update_recitation`` save inside ``atomic()``, and a
    synchronous delete would run before the new policy commits -- letting a
    concurrent request repopulate the metadata from the pre-commit row and
    leaving stale authorization data after commit (CWE-863). Outside an
    atomic block (autocommit saves) the callback runs immediately.

    This subsumes the staging-side "invalidate on any recitation asset save":
    full saves (update_fields=None, e.g. admin/portal PUT) always invalidate,
    while partial saves only do so for access-policy fields, so unrelated
    edits don't churn the warm cache.
    """
    if instance.category != CategoryChoice.RECITATION:
        return
    if update_fields is not None and not ({"is_open_access", "status", *ASSET_CHANNEL_FIELDS} & set(update_fields)):
        return
    transaction.on_commit(lambda asset_id=instance.id: invalidate_recitation_tracks_cache(asset_id))


@receiver(post_save, sender=Asset)
def create_default_recitation_quality(sender, instance: Asset, created: bool, **kwargs) -> None:
    """
    Give every new recitation Asset its default quality.

    Tracks require a quality, and the APIs fall back to the default one whenever a
    caller does not name a variant. Doing this on the signal rather than in the
    repository means the invariant also holds for assets created through Django
    admin, fixtures, or data imports -- not just through the service layer.
    """
    if not created or instance.category != CategoryChoice.RECITATION:
        return

    RecitationQuality.objects.get_or_create(
        asset=instance,
        is_default=True,
        defaults={
            "name": RecitationQuality.DEFAULT_NAME_AR,
            "name_ar": RecitationQuality.DEFAULT_NAME_AR,
            "name_en": RecitationQuality.DEFAULT_NAME_EN,
            "slug": RecitationQuality.DEFAULT_SLUG,
        },
    )


# The fields the portal home counts group or filter by.
_PORTAL_ASSET_COUNT_FIELDS = frozenset({"category", "status", "publisher", "publisher_id"})


@receiver(post_save, sender=Asset)
def clear_portal_asset_counts_on_save(sender, instance: Asset, created: bool, update_fields=None, **kwargs) -> None:
    """Drop the cached portal home counts when a save may change them (after commit, like the recitation cache)."""
    if not created and update_fields is not None and not (_PORTAL_ASSET_COUNT_FIELDS & set(update_fields)):
        return
    transaction.on_commit(invalidate_portal_asset_counts)


@receiver(post_delete, sender=Asset)
def clear_portal_asset_counts_on_delete(sender, instance: Asset, **kwargs) -> None:
    transaction.on_commit(invalidate_portal_asset_counts)


@receiver(m2m_changed, sender=Asset.tags.through)
def clear_portal_asset_counts_on_tags_change(sender, action: str, **kwargs) -> None:
    """The text tile breaks its count down by tag."""
    if action in {"post_add", "post_remove", "post_clear"}:
        transaction.on_commit(invalidate_portal_asset_counts)
