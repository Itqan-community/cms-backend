import re

from django.apps.registry import Apps
from django.conf.locale import LANG_INFO
from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor

# --- Language codes ---------------------------------------------------------------
# Older assets stored their language as a name ("Arabic", "English") instead of a
# code ("ar", "en"). Everything that compares languages (the source rendition, member
# access, the package registry's manifests) needs the code, so names are rewritten.

ARABIC_DIACRITICS_RE = re.compile(r"[ً-ْ]")


def _language_key(value: str) -> str:
    return ARABIC_DIACRITICS_RE.sub("", value).strip().casefold()


def _language_codes() -> dict[str, str]:
    """Language code, English name and native name -> code, for every plain code Django knows."""
    codes: dict[str, str] = {}
    for code, info in LANG_INFO.items():
        if "-" in code or "name" not in info:
            continue
        for label in (code, info["name"], info.get("name_local", "")):
            if label:
                codes.setdefault(_language_key(label), code)
    return codes


def _normalize(model, owner_field: str | None, codes: dict[str, str]) -> None:
    """Rewrite ``model.language`` names to codes. With ``owner_field`` (a unique
    (owner, language) pair), a rename that would collide with an existing row is skipped."""
    for row in model.objects.exclude(language__in=list(set(codes.values()))):
        code = codes.get(_language_key(row.language))
        if code is None or code == row.language:
            continue
        if owner_field is not None:
            owner_id = getattr(row, f"{owner_field}_id")
            if model.objects.filter(**{f"{owner_field}_id": owner_id, "language": code}).exists():
                print(f"  {model.__name__} {row.pk}: {row.language!r} left as is, {owner_field} already has {code!r}")
                continue
        row.language = code
        row.save(update_fields=["language"])


def normalize_language_codes(apps: Apps, schema_editor: BaseDatabaseSchemaEditor | None) -> None:
    codes = _language_codes()
    _normalize(apps.get_model("content", "Asset"), None, codes)
    _normalize(apps.get_model("content", "AssetLanguage"), "asset", codes)
    _normalize(apps.get_model("publishers", "MemberLanguage"), "member", codes)


# --- Mushaf / font version numbers ------------------------------------------------
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
    dependencies = [
        ("content", "0004_seed_mushaf_layouts"),
        ("publishers", "0002_initial"),
    ]

    # Reversing is a no-op: language names map to codes one way, and the versions' old
    # names are kept as their labels. Languages go first: numbering groups by language.
    operations = [
        migrations.RunPython(normalize_language_codes, migrations.RunPython.noop),
        migrations.RunPython(number_mushaf_font_versions, migrations.RunPython.noop),
    ]
