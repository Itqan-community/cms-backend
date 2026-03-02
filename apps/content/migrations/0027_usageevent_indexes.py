"""Add missing database indexes on high-query fields.

UsageEvent: composite indexes for stats aggregation queries that filter by
created_at + usage_kind and developer_user + usage_kind. Also individual
indexes on asset_id and resource_id which are PositiveIntegerFields (not FKs)
and thus lack Django's automatic FK indexing.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("content", "0026_reciter_bio_ar_reciter_bio_en_riwayah_bio_and_more"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="usageevent",
            index=models.Index(
                fields=["created_at", "usage_kind"],
                name="usageevent_created_kind_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="usageevent",
            index=models.Index(
                fields=["developer_user", "usage_kind"],
                name="usageevent_user_kind_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="usageevent",
            index=models.Index(
                fields=["asset_id"],
                name="usageevent_asset_id_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="usageevent",
            index=models.Index(
                fields=["resource_id"],
                name="usageevent_resource_id_idx",
            ),
        ),
    ]
