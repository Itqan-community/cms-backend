from django.db import migrations

# Mirrors RecitationFolder.DEFAULT_* — copied rather than imported so this migration
# keeps working if those class attributes are later renamed or moved.
DEFAULT_NAME_AR = "افتراضي"
DEFAULT_NAME_EN = "Default"
DEFAULT_SLUG = "default"

RECITATION_CATEGORY = "recitation"


def create_default_folders(apps, schema_editor):
    """
    Give every recitation Asset a default folder and move its existing tracks into it.

    This must land (and commit) before the follow-up migration makes
    RecitationSurahTrack.folder non-nullable and swaps the uniqueness constraint
    from (asset, surah_number) to (folder, surah_number).
    """
    Asset = apps.get_model("content", "Asset")
    RecitationFolder = apps.get_model("content", "RecitationFolder")
    RecitationSurahTrack = apps.get_model("content", "RecitationSurahTrack")

    asset_ids = list(
        Asset.objects.filter(category=RECITATION_CATEGORY).values_list("id", flat=True)
    )

    for asset_id in asset_ids:
        folder, _created = RecitationFolder.objects.get_or_create(
            asset_id=asset_id,
            slug=DEFAULT_SLUG,
            defaults={
                "name": DEFAULT_NAME_AR,
                "name_ar": DEFAULT_NAME_AR,
                "name_en": DEFAULT_NAME_EN,
                "is_default": True,
            },
        )
        RecitationSurahTrack.objects.filter(asset_id=asset_id, folder__isnull=True).update(folder_id=folder.id)

    # Tracks may exist on assets whose category is not "recitation" (data drift, or a
    # category edited after upload). They still need a folder, otherwise the next
    # migration's non-null constraint fails on them.
    orphan_asset_ids = (
        RecitationSurahTrack.objects.filter(folder__isnull=True)
        .values_list("asset_id", flat=True)
        .distinct()
    )
    for asset_id in list(orphan_asset_ids):
        folder, _created = RecitationFolder.objects.get_or_create(
            asset_id=asset_id,
            slug=DEFAULT_SLUG,
            defaults={
                "name": DEFAULT_NAME_AR,
                "name_ar": DEFAULT_NAME_AR,
                "name_en": DEFAULT_NAME_EN,
                "is_default": True,
            },
        )
        RecitationSurahTrack.objects.filter(asset_id=asset_id, folder__isnull=True).update(folder_id=folder.id)


def remove_default_folders(apps, schema_editor):
    """
    Detach tracks from their default folders and delete those folders.

    Only folders created by this migration (slug="default") are removed; folders
    added afterwards by users are left alone, as are any tracks inside them.
    """
    RecitationFolder = apps.get_model("content", "RecitationFolder")
    RecitationSurahTrack = apps.get_model("content", "RecitationSurahTrack")

    default_folder_ids = list(
        RecitationFolder.objects.filter(slug=DEFAULT_SLUG, is_default=True).values_list("id", flat=True)
    )

    RecitationSurahTrack.objects.filter(folder_id__in=default_folder_ids).update(folder=None)
    RecitationFolder.objects.filter(id__in=default_folder_ids).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("content", "0047_add_recitation_folder"),
    ]

    operations = [
        migrations.RunPython(create_default_folders, remove_default_folders),
    ]
