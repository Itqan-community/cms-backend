import re

from django.apps.registry import Apps
from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor

ARABIC_LETTER = re.compile(r"[؀-ۿݐ-ݿࢠ-ࣿﭐ-﷿ﹰ-﻿]")
LATIN_LETTER = re.compile(r"[A-Za-z]")
FIELDS = ("label", "summary")


def is_mostly_arabic(text: str) -> bool:
    """More Arabic-script letters than Latin ones."""
    return len(ARABIC_LETTER.findall(text)) > len(LATIN_LETTER.findall(text))


def split_by_script(apps: Apps, schema_editor: BaseDatabaseSchemaEditor | None) -> None:
    """Move each version's single label/summary into the language it is written in:
    mostly Arabic script → ``*_ar``, anything else → ``*_en``. The other is left empty."""
    AssetVersion = apps.get_model("content", "AssetVersion")
    for version in AssetVersion.objects.only("id", *FIELDS).iterator():
        for field in FIELDS:
            text = getattr(version, field) or ""
            arabic = is_mostly_arabic(text)
            setattr(version, f"{field}_ar", text if arabic else "")
            setattr(version, f"{field}_en", "" if arabic else text)
        version.save(update_fields=[f"{field}_{lang}" for field in FIELDS for lang in ("en", "ar")])


def join_back(apps: Apps, schema_editor: BaseDatabaseSchemaEditor | None) -> None:
    """Put each version's text back into the single field, preferring English."""
    AssetVersion = apps.get_model("content", "AssetVersion")
    for version in AssetVersion.objects.iterator():
        for field in FIELDS:
            setattr(version, field, getattr(version, f"{field}_en") or getattr(version, f"{field}_ar") or "")
        version.save(update_fields=list(FIELDS))


class Migration(migrations.Migration):
    dependencies = [
        ("content", "0073_assetversion_bilingual_label_summary"),
    ]

    operations = [
        migrations.RunPython(split_by_script, join_back),
    ]
