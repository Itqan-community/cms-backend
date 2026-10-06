"""Backfill helper for the multi-language rollout.

Kept as a pure function taking the model classes so it can run against both the
historical models (from a data migration) and the real models (from tests).
"""

from __future__ import annotations


def backfill_source_languages(Asset, AssetLanguage, AssetVersion) -> None:
    """Ensure every asset has an ``is_source`` ``AssetLanguage`` (matching
    ``asset.language``) and link every version lacking one to it.

    Idempotent: safe to run more than once.
    """
    for asset in Asset.objects.all().iterator():
        source, created = AssetLanguage.objects.get_or_create(
            asset=asset,
            language=asset.language,
            defaults={"is_source": True},
        )
        if not created and not source.is_source:
            source.is_source = True
            # Persist promotion to the DB so callers/tests that reload the record see it
            source.save(update_fields=["is_source"])
        matching_versions = AssetVersion.objects.filter(asset=asset, asset_language__isnull=True)
        if hasattr(AssetVersion, "history"):
            from apps.core.audit import update_with_history

            update_with_history(matching_versions, asset_language=source)
        else:
            matching_versions.update(asset_language=source)
