# Marqoom naming: "sura" / "aya" become "surah" / "ayah". Renames only: no data
# is copied, and the index and constraint are renamed in place rather than rebuilt.

from django.db import migrations, models


class Migration(migrations.Migration):
    # After every migration that still points at "quran.sura", so a fresh
    # database never renames the model before they run.
    dependencies = [
        ("quran", "0001_initial"),
        ("content", "0011_group_templates"),
        ("simple_history", "0006_group_template_ranges"),
    ]

    operations = [
        migrations.RenameModel(old_name="Sura", new_name="Surah"),
        migrations.RenameField(model_name="surah", old_name="ayas_count", new_name="ayahs_count"),
        migrations.RenameField(model_name="ayah", old_name="sura", new_name="surah"),
        migrations.RenameField(model_name="ayah", old_name="number_in_sura", new_name="number_in_surah"),
        migrations.RenameField(model_name="word", old_name="sura", new_name="surah"),
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    "ALTER INDEX quran_ayah_sura_id_f783bf_idx RENAME TO quran_ayah_surah_i_8a587a_idx",
                    "ALTER INDEX quran_ayah_surah_i_8a587a_idx RENAME TO quran_ayah_sura_id_f783bf_idx",
                ),
                migrations.RunSQL(
                    "ALTER TABLE quran_ayah RENAME CONSTRAINT unique_ayah_per_sura TO unique_ayah_per_surah",
                    "ALTER TABLE quran_ayah RENAME CONSTRAINT unique_ayah_per_surah TO unique_ayah_per_sura",
                ),
            ],
            state_operations=[
                migrations.RemoveIndex(model_name="ayah", name="quran_ayah_sura_id_f783bf_idx"),
                migrations.AddIndex(
                    model_name="ayah",
                    index=models.Index(fields=["surah", "number_in_surah"], name="quran_ayah_surah_i_8a587a_idx"),
                ),
                migrations.RemoveConstraint(model_name="ayah", name="unique_ayah_per_sura"),
                migrations.AddConstraint(
                    model_name="ayah",
                    constraint=models.UniqueConstraint(
                        fields=("surah", "number_in_surah"), name="unique_ayah_per_surah"
                    ),
                ),
            ],
        ),
        migrations.AlterField(
            model_name="ayah",
            name="number_in_surah",
            field=models.PositiveSmallIntegerField(help_text="Ayah number within its surah (1-based)"),
        ),
        migrations.AlterField(
            model_name="surah",
            name="ayahs_count",
            field=models.PositiveSmallIntegerField(help_text="Number of ayahs in this surah"),
        ),
        migrations.AlterField(
            model_name="surah",
            name="id",
            field=models.PositiveSmallIntegerField(
                help_text="Canonical surah number (1-114)", primary_key=True, serialize=False
            ),
        ),
        migrations.AlterField(
            model_name="surah",
            name="name",
            field=models.CharField(help_text="Arabic name of the surah", max_length=64),
        ),
        migrations.AlterField(
            model_name="surah",
            name="revelation_order",
            field=models.PositiveSmallIntegerField(help_text="Order in which the surah was revealed"),
        ),
        migrations.AlterField(
            model_name="surah",
            name="revelation_type",
            field=models.CharField(
                choices=[("Meccan", "Meccan"), ("Medinan", "Medinan")],
                help_text="Whether the surah was revealed in Mecca or Medina",
                max_length=8,
            ),
        ),
        migrations.AlterField(
            model_name="surah",
            name="rukus_count",
            field=models.PositiveSmallIntegerField(help_text="Number of rukus (sections) in this surah"),
        ),
        migrations.AlterField(
            model_name="surah",
            name="start_offset",
            field=models.PositiveSmallIntegerField(help_text="Cumulative number of ayahs in all preceding surahs"),
        ),
    ]
