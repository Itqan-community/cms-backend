import re

from django.apps.registry import Apps
from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor

# Mushaf and font version names used to be free text (usually the asset's title), which
# the package registry skips: it only serves versions named with a version number. They
# are now issued "major.minor" numbers like tafsirs and translations.

NUMBERED_CATEGORIES = ["mushaf", "font"]
VERSION_NUMBER_RE = re.compile(r"^(\d{1,9})\.(\d{1,9})$")
ARABIC_RE = re.compile(r"[؀-ۿ]")


def number_mushaf_font_versions(apps: Apps, schema_editor: BaseDatabaseSchemaEditor | None) -> None:
    """Give every published mushaf / font version without a version number one.

    Each (asset, language) sequence is numbered in creation order, continuing after
    its highest existing number, else from 1.0. The old name is kept as the version
    name (``label``), in Arabic or English by its script, unless a label is already set.
    """
    AssetVersion = apps.get_model("content", "AssetVersion")
    versions = (
        AssetVersion.objects.filter(asset__category__in=NUMBERED_CATEGORIES, state="published")
        .select_related("asset", "asset_language")
        .order_by("asset_id", "created_at", "id")
    )
    sequences: dict[tuple[int, str], list] = {}
    for version in versions:
        language = version.asset_language.language if version.asset_language_id else version.asset.language
        sequences.setdefault((version.asset_id, language), []).append(version)

    for sequence in sequences.values():
        numbers = [m.groups() for m in (VERSION_NUMBER_RE.match(v.name.strip()) for v in sequence) if m]
        major, minor = max(((int(a), int(b)) for a, b in numbers), default=(1, -1))
        for version in sequence:
            if VERSION_NUMBER_RE.match(version.name.strip()):
                continue
            minor += 1
            old_name = version.name.strip()
            version.name = f"{major}.{minor}"
            if old_name and not (version.label_en or version.label_ar):
                if ARABIC_RE.search(old_name):
                    version.label_ar = old_name
                else:
                    version.label_en = old_name
            version.save(update_fields=["name", "label_en", "label_ar"])


class Migration(migrations.Migration):
    dependencies = [("content", "0004_seed_mushaf_layouts")]

    # Reversing is a no-op: the old names are kept as the versions' labels.
    operations = [migrations.RunPython(number_mushaf_font_versions, migrations.RunPython.noop)]
