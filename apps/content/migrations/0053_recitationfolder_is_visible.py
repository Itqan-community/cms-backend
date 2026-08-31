from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("content", "0052_merge_20260826_1701"),
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
    ]
