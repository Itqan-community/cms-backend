from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("content", "0049_recitation_track_folder_constraints"),
    ]

    operations = [
        migrations.AddField(
            model_name="recitationfolder",
            name="is_visible",
            field=models.BooleanField(
                db_index=True,
                default=True,
                help_text="When false, the folder is omitted from public/tenant APIs and its timings export is withdrawn.",
            ),
        ),
        migrations.AddIndex(
            model_name="recitationfolder",
            index=models.Index(
                condition=models.Q(("is_visible", True)),
                fields=["asset"],
                name="content_recitationfolder_visible_idx",
            ),
        ),
    ]
