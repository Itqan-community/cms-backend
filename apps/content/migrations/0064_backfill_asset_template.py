from django.apps.registry import Apps
from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor

TEXT_CATEGORIES = ["translation", "tafsir"]


def backfill_template(apps: Apps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    """Every pre-existing translation / tafsir was ayah-keyed by construction."""
    Asset = apps.get_model("content", "Asset")
    Asset.objects.filter(category__in=TEXT_CATEGORIES, template__isnull=True).update(template="ayah")


def clear_template(apps: Apps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    """Clears every translation/tafsir row's template, not just the ones the
    forward pass set. Safe only as part of a full 0063 unapply (which drops
    the column outright) -- it is not a precise inverse of backfill_template
    on its own.
    """
    Asset = apps.get_model("content", "Asset")
    Asset.objects.filter(category__in=TEXT_CATEGORIES).update(template=None)


class Migration(migrations.Migration):
    dependencies = [("content", "0063_asset_template_fields")]

    operations = [migrations.RunPython(backfill_template, clear_template)]
