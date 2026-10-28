# Marqoom naming: the history tables follow content's ``sura`` -> ``surah`` rename.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("simple_history", "0006_group_template_ranges"),
        ("quran", "0002_rename_sura_to_surah"),
    ]

    operations = [
        migrations.RenameField(model_name="historicalassetversionentry", old_name="sura", new_name="surah"),
        migrations.RenameField(model_name="historicalassetversionchange", old_name="sura", new_name="surah"),
        migrations.AlterField(
            model_name="historicalassetversionchange",
            name="surah",
            field=models.ForeignKey(
                blank=True,
                db_constraint=False,
                help_text="Canonical surah (1-114) — set only for surah-template assets",
                null=True,
                on_delete=django.db.models.deletion.DO_NOTHING,
                related_name="+",
                to="quran.surah",
            ),
        ),
        migrations.AlterField(
            model_name="historicalassetversionentry",
            name="surah",
            field=models.ForeignKey(
                blank=True,
                db_constraint=False,
                help_text="Canonical surah (1-114) — set only for surah-template assets",
                null=True,
                on_delete=django.db.models.deletion.DO_NOTHING,
                related_name="+",
                to="quran.surah",
            ),
        ),
    ]
