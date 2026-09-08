from django.db import migrations

from apps.content.services.asset_language_backfill import backfill_source_languages


def backfill(apps, schema_editor):
    Asset = apps.get_model("content", "Asset")
    AssetLanguage = apps.get_model("content", "AssetLanguage")
    AssetVersion = apps.get_model("content", "AssetVersion")
    backfill_source_languages(Asset, AssetLanguage, AssetVersion)


def unbackfill(apps, schema_editor):
    AssetVersion = apps.get_model("content", "AssetVersion")
    AssetLanguage = apps.get_model("content", "AssetLanguage")
    AssetVersion.objects.update(asset_language=None)
    AssetLanguage.objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [("content", "0055_assetlanguage_and_asset_language_fk")]

    operations = [migrations.RunPython(backfill, unbackfill)]
