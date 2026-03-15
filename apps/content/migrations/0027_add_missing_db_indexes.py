from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("content", "0026_reciter_bio_ar_reciter_bio_en_riwayah_bio_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddIndex(
            model_name="assetaccessrequest",
            index=models.Index(
                fields=["developer_user", "asset"],
                name="content_accessreq_user_asset_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="usageevent",
            index=models.Index(
                fields=["developer_user", "usage_kind"],
                name="content_usageevent_user_kind_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="usageevent",
            index=models.Index(
                fields=["created_at", "usage_kind"],
                name="content_usageevent_created_kind_idx",
            ),
        ),
    ]
