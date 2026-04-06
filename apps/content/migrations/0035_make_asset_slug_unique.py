from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("content", "0034_populate_asset_slug"),
    ]

    operations = [
        migrations.AlterField(
            model_name="asset",
            name="slug",
            field=models.SlugField(
                allow_unicode=True, help_text="URL-friendly slug for the asset", unique=True
            ),
        ),
    ]
