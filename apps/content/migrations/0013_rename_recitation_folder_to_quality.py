# Naming: a recitation "folder" (a variant of a recitation asset, e.g. with echo or a different
# audio quality) becomes a "quality". Renames only: the table, column and constraints are
# renamed in place and no data is copied.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("content", "0012_rename_sura_to_surah"),
    ]

    operations = [
        migrations.RenameModel(old_name="RecitationFolder", new_name="RecitationQuality"),
        migrations.RenameField(model_name="recitationsurahtrack", old_name="folder", new_name="quality"),
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    "ALTER TABLE content_recitationquality RENAME CONSTRAINT folder_unique_slug_per_asset TO quality_unique_slug_per_asset",
                    "ALTER TABLE content_recitationquality RENAME CONSTRAINT quality_unique_slug_per_asset TO folder_unique_slug_per_asset",
                ),
                migrations.RunSQL(
                    "ALTER INDEX folder_one_default_per_asset RENAME TO quality_one_default_per_asset",
                    "ALTER INDEX quality_one_default_per_asset RENAME TO folder_one_default_per_asset",
                ),
            ],
            state_operations=[
                migrations.RemoveConstraint(model_name="recitationquality", name="folder_unique_slug_per_asset"),
                migrations.AddConstraint(
                    model_name="recitationquality",
                    constraint=models.UniqueConstraint(fields=("asset", "slug"), name="quality_unique_slug_per_asset"),
                ),
                migrations.RemoveConstraint(model_name="recitationquality", name="folder_one_default_per_asset"),
                migrations.AddConstraint(
                    model_name="recitationquality",
                    constraint=models.UniqueConstraint(
                        condition=models.Q(("is_default", True)),
                        fields=("asset",),
                        name="quality_one_default_per_asset",
                    ),
                ),
            ],
        ),
        migrations.AlterModelOptions(name="recitationquality", options={"verbose_name_plural": "recitation qualities"}),
        migrations.RenameIndex(
            model_name="recitationquality",
            new_name="content_rec_asset_i_0c0486_idx",
            old_name="content_rec_asset_i_664f9a_idx",
        ),
        # RenameField does not rewrite the field list of Meta.indexes in migration state, so
        # the state sees a different index; the database index itself is only renamed.
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    "ALTER INDEX content_rec_folder__29f620_idx RENAME TO content_rec_quality_113b33_idx",
                    "ALTER INDEX content_rec_quality_113b33_idx RENAME TO content_rec_folder__29f620_idx",
                ),
            ],
            state_operations=[
                migrations.RemoveIndex(model_name="recitationsurahtrack", name="content_rec_folder__29f620_idx"),
                migrations.AddIndex(
                    model_name="recitationsurahtrack",
                    index=models.Index(fields=["quality", "surah_number"], name="content_rec_quality_113b33_idx"),
                ),
            ],
        ),
        migrations.AlterField(
            model_name="recitationquality",
            name="asset",
            field=models.ForeignKey(
                help_text="Parent Asset representing the recitation set",
                on_delete=django.db.models.deletion.CASCADE,
                related_name="recitation_qualities",
                to="content.asset",
            ),
        ),
        migrations.AlterField(
            model_name="recitationquality",
            name="is_default",
            field=models.BooleanField(
                default=False,
                help_text="The quality served when the API caller does not specify one. Exactly one per asset.",
            ),
        ),
        migrations.AlterField(
            model_name="recitationquality",
            name="is_visible",
            field=models.BooleanField(
                db_index=True,
                default=True,
                help_text="When false, the quality is omitted from public/tenant APIs and its timings export is withdrawn.",
            ),
        ),
        migrations.AlterField(
            model_name="recitationquality",
            name="name",
            field=models.CharField(
                help_text="Quality/variant name e.g. 'Clear', 'With echo', '128kbps'", max_length=255
            ),
        ),
        migrations.AlterField(
            model_name="recitationquality",
            name="name_ar",
            field=models.CharField(
                help_text="Quality/variant name e.g. 'Clear', 'With echo', '128kbps'", max_length=255, null=True
            ),
        ),
        migrations.AlterField(
            model_name="recitationquality",
            name="name_en",
            field=models.CharField(
                help_text="Quality/variant name e.g. 'Clear', 'With echo', '128kbps'", max_length=255, null=True
            ),
        ),
        migrations.AlterField(
            model_name="recitationquality",
            name="slug",
            field=models.SlugField(
                allow_unicode=True,
                default="",
                help_text="URL-friendly slug, unique per asset. Used as the ?quality= API query value.",
            ),
        ),
        migrations.AlterField(
            model_name="recitationsurahtrack",
            name="quality",
            field=models.ForeignKey(
                help_text="Quality (variant) this track belongs to",
                on_delete=django.db.models.deletion.CASCADE,
                related_name="tracks",
                to="content.recitationquality",
            ),
        ),
    ]
