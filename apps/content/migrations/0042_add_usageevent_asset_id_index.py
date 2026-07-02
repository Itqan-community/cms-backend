# Generated for TD-001: add index on content_usageevent.asset_id

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("content", "0041_remove_contentissuereport_content_type_fields_and_add_asset"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="usageevent",
            index=models.Index(fields=["asset_id"], name="content_usa_asset_i_idx"),
        ),
    ]
