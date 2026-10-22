"""Give every translation / tafsir its default ``text`` column and point its cells at it.

Entries and changes are updated in id batches outside one big transaction, so a
production-size entries table is never locked as a whole. Committed versions get
``column_keys = ["text"]`` — the layout their files already have.
"""

from django.db import migrations

BATCH = 50_000
TEXT_CATEGORIES = ("translation", "tafsir")


def _backfill_cells(cursor, table: str) -> None:
    cursor.execute(f"SELECT MIN(id), MAX(id) FROM {table} WHERE column_id IS NULL")  # nosec B608
    low, high = cursor.fetchone()
    if low is None:
        return
    for start in range(low, high + 1, BATCH):
        cursor.execute(
            f"""
            UPDATE {table} AS cell
            SET column_id = col.id
            FROM content_assetversion AS version
            JOIN content_assetcolumn AS col ON col.asset_id = version.asset_id AND col.key = 'text'
            WHERE cell.version_id = version.id
              AND cell.column_id IS NULL
              AND cell.id BETWEEN %s AND %s
            """,  # nosec B608
            [start, start + BATCH - 1],
        )


def backfill(apps, schema_editor):
    Asset = apps.get_model("content", "Asset")
    AssetColumn = apps.get_model("content", "AssetColumn")
    AssetVersion = apps.get_model("content", "AssetVersion")

    missing = Asset.objects.filter(category__in=TEXT_CATEGORIES).exclude(columns__isnull=False)
    AssetColumn.objects.bulk_create(
        [AssetColumn(asset_id=asset_id, key="text", order=0) for asset_id in missing.values_list("id", flat=True)],
        batch_size=1000,
    )
    with schema_editor.connection.cursor() as cursor:
        _backfill_cells(cursor, "content_assetversionentry")
        _backfill_cells(cursor, "content_assetversionchange")
    AssetVersion.objects.filter(asset__category__in=TEXT_CATEGORIES, state="published", column_keys=[]).update(
        column_keys=["text"]
    )


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("content", "0008_asset_columns"),
    ]

    operations = [
        migrations.RunPython(backfill, migrations.RunPython.noop),
    ]
