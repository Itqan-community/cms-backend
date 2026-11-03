# Per-asset distribution channels replace the single ``restricted_for_tenant`` flag.
# Every existing asset starts with all four channels on (the defaults), by decision:
# the old flag is deliberately not mapped onto the new ones.

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("content", "0013_rename_recitation_folder_to_quality"),
    ]

    operations = [
        migrations.AddField(
            model_name="asset",
            name="in_gallery",
            field=models.BooleanField(
                default=True,
                help_text="Distribution channel: shown on the CMS website (assets gallery, detail, download).",
            ),
        ),
        migrations.AddField(
            model_name="asset",
            name="in_public_api",
            field=models.BooleanField(
                default=True,
                help_text="Distribution channel: served by the public developers API (and its recommendations).",
            ),
        ),
        migrations.AddField(
            model_name="asset",
            name="in_cli",
            field=models.BooleanField(
                default=True,
                help_text="Distribution channel: published in the itqan CLI package registry.",
            ),
        ),
        migrations.AddField(
            model_name="asset",
            name="in_tenants",
            field=models.BooleanField(
                default=True,
                help_text="Distribution channel: served by the publisher tenant API.",
            ),
        ),
        migrations.RemoveField(
            model_name="asset",
            name="restricted_for_tenant",
        ),
    ]
