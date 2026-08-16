import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """
    Make RecitationSurahTrack.folder required and move uniqueness onto the folder.

    Safe only because 0048 already gave every existing track a folder. Uniqueness
    moves from (asset, surah_number) to (folder, surah_number) so one asset can
    publish the same surah once per variant. The (asset, surah_number) index is
    kept as a plain index — it is no longer unique, but queries still filter by asset.

    ROLLBACK WARNING: reversing this migration restores the (asset, surah_number)
    unique index, which fails as soon as any asset has a second folder holding a
    surah the default folder also has — i.e. as soon as the feature is actually
    used. Postgres refuses the index and leaves the data untouched, so nothing is
    lost, but rolling back past this point requires deleting the extra variants
    first. Treat this migration as forward-only once variants exist in production.
    """

    dependencies = [
        ("content", "0048_backfill_default_recitation_folders"),
    ]

    operations = [
        # Drop the old uniqueness first: it would otherwise block adding a second
        # variant of the same surah, and AlterUniqueTogether must run before the
        # replacement index is introduced.
        migrations.AlterUniqueTogether(
            name="recitationsurahtrack",
            unique_together=set(),
        ),
        migrations.AlterField(
            model_name="recitationsurahtrack",
            name="folder",
            field=models.ForeignKey(
                help_text="Folder (variant) this track belongs to",
                on_delete=django.db.models.deletion.CASCADE,
                related_name="tracks",
                to="content.recitationfolder",
            ),
        ),
        migrations.AlterUniqueTogether(
            name="recitationsurahtrack",
            unique_together={("folder", "surah_number")},
        ),
        migrations.AddIndex(
            model_name="recitationsurahtrack",
            index=models.Index(fields=["folder", "surah_number"], name="content_rec_folder__29f620_idx"),
        ),
    ]
