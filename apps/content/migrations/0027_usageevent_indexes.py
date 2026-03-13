"""Add missing database indexes on high-query fields.

UsageEvent: composite indexes for stats aggregation queries that filter by
created_at + usage_kind and developer_user + usage_kind. Also individual
indexes on asset_id and resource_id which are PositiveIntegerFields (not FKs)
and thus lack Django's automatic FK indexing.

Uses AddIndexConcurrently to avoid blocking writes during index creation
on PostgreSQL. Requires atomic = False.
"""

from django.contrib.postgres.operations import AddIndexConcurrently
from django.db import migrations, models


class Migration(migrations.Migration):

    atomic = False

    dependencies = [
        ("content", "0026_reciter_bio_ar_reciter_bio_en_riwayah_bio_and_more"),
    ]

    operations = [
        AddIndexConcurrently(
            model_name="usageevent",
            index=models.Index(
                fields=["created_at", "usage_kind"],
                name="usageevent_created_kind_idx",
            ),
        ),
        AddIndexConcurrently(
            model_name="usageevent",
            index=models.Index(
                fields=["developer_user", "usage_kind"],
                name="usageevent_user_kind_idx",
            ),
        ),
        AddIndexConcurrently(
            model_name="usageevent",
            index=models.Index(
                fields=["asset_id"],
                name="usageevent_asset_id_idx",
            ),
        ),
        AddIndexConcurrently(
            model_name="usageevent",
            index=models.Index(
                fields=["resource_id"],
                name="usageevent_resource_id_idx",
            ),
        ),
    ]
