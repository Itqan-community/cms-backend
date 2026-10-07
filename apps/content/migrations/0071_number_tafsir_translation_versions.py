from collections import defaultdict

from django.apps.registry import Apps
from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor


def number_versions(apps: Apps, schema_editor: BaseDatabaseSchemaEditor | None) -> None:
    """Give every translation / tafsir version a "major.minor" number.

    The free-text name moves to ``label`` (the version name). Committed versions
    are numbered 1.0, 1.1, 1.2, ... in creation order within each (asset,
    language) sequence; drafts are unnumbered until they are committed. Legacy
    versions with no ``asset_language`` belong to the source language.
    """
    AssetVersion = apps.get_model("content", "AssetVersion")
    versions = (
        AssetVersion.objects.filter(asset__category__in=["translation", "tafsir"])
        .select_related("asset", "asset_language")
        .order_by("created_at", "id")
    )
    next_minor: dict[tuple[int, str], int] = defaultdict(int)
    for version in versions.iterator():
        version.label = version.name
        if version.state == "draft":
            version.name = ""
        else:
            language = version.asset_language.language if version.asset_language_id else version.asset.language
            key = (version.asset_id, language)
            version.name = f"1.{next_minor[key]}"
            next_minor[key] += 1
        version.save(update_fields=["name", "label"])


def restore_names(apps: Apps, schema_editor: BaseDatabaseSchemaEditor | None) -> None:
    """Move each label back into ``name``. A version without one (created after this
    migration with no name given) keeps its number rather than going blank."""
    AssetVersion = apps.get_model("content", "AssetVersion")
    for version in AssetVersion.objects.filter(asset__category__in=["translation", "tafsir"]).iterator():
        version.name = version.label or version.name
        version.save(update_fields=["name"])


class Migration(migrations.Migration):
    dependencies = [
        ("content", "0070_assetversion_label"),
    ]

    operations = [
        migrations.RunPython(number_versions, restore_names),
    ]
