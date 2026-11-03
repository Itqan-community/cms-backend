# Naming: the history tables follow content's ``RecitationFolder`` -> ``RecitationQuality`` rename.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("simple_history", "0009_alter_historicalpublishermember_group"),
        ("content", "0013_rename_recitation_folder_to_quality"),
    ]

    operations = [
        migrations.RenameModel(old_name="HistoricalRecitationFolder", new_name="HistoricalRecitationQuality"),
        migrations.RenameField(model_name="historicalrecitationsurahtrack", old_name="folder", new_name="quality"),
        migrations.AlterModelOptions(
            name="historicalrecitationquality",
            options={
                "get_latest_by": ("history_date", "history_id"),
                "ordering": ("-history_date", "-history_id"),
                "verbose_name": "historical recitation quality",
                "verbose_name_plural": "historical recitation qualities",
            },
        ),
        migrations.AlterField(
            model_name="historicalrecitationquality",
            name="asset",
            field=models.ForeignKey(
                blank=True,
                db_constraint=False,
                help_text="Parent Asset representing the recitation set",
                null=True,
                on_delete=django.db.models.deletion.DO_NOTHING,
                related_name="+",
                to="content.asset",
            ),
        ),
        migrations.AlterField(
            model_name="historicalrecitationquality",
            name="is_default",
            field=models.BooleanField(
                default=False,
                help_text="The quality served when the API caller does not specify one. Exactly one per asset.",
            ),
        ),
        migrations.AlterField(
            model_name="historicalrecitationquality",
            name="is_visible",
            field=models.BooleanField(
                db_index=True,
                default=True,
                help_text="When false, the quality is omitted from public/tenant APIs and its timings export is withdrawn.",
            ),
        ),
        migrations.AlterField(
            model_name="historicalrecitationquality",
            name="name",
            field=models.CharField(
                help_text="Quality/variant name e.g. 'Clear', 'With echo', '128kbps'", max_length=255
            ),
        ),
        migrations.AlterField(
            model_name="historicalrecitationquality",
            name="name_ar",
            field=models.CharField(
                blank=True,
                help_text="Quality/variant name e.g. 'Clear', 'With echo', '128kbps'",
                max_length=255,
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name="historicalrecitationquality",
            name="name_en",
            field=models.CharField(
                blank=True,
                help_text="Quality/variant name e.g. 'Clear', 'With echo', '128kbps'",
                max_length=255,
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name="historicalrecitationquality",
            name="slug",
            field=models.SlugField(
                allow_unicode=True,
                default="",
                help_text="URL-friendly slug, unique per asset. Used as the ?quality= API query value.",
            ),
        ),
        migrations.AlterField(
            model_name="historicalrecitationsurahtrack",
            name="quality",
            field=models.ForeignKey(
                blank=True,
                db_constraint=False,
                help_text="Quality (variant) this track belongs to",
                null=True,
                on_delete=django.db.models.deletion.DO_NOTHING,
                related_name="+",
                to="content.recitationquality",
            ),
        ),
    ]
