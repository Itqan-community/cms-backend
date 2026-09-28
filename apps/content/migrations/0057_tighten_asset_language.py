from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("content", "0056_backfill_asset_languages")]

    operations = [
        migrations.RemoveConstraint(
            model_name="assetversion",
            name="unique_draft_version_per_asset",
        ),
        migrations.AddConstraint(
            model_name="assetversion",
            constraint=models.UniqueConstraint(
                condition=models.Q(("state", "draft")),
                fields=("asset", "asset_language"),
                name="unique_draft_version_per_asset_language",
            ),
        ),
    ]
