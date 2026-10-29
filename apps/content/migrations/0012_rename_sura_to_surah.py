# Marqoom naming: the entry / change ``sura`` unit becomes ``surah``. Renames
# only: no data is copied, and constraints are renamed in place rather than rebuilt.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("content", "0011_group_templates"),
        ("quran", "0002_rename_sura_to_surah"),
    ]

    operations = [
        migrations.RenameField(model_name="assetversionentry", old_name="sura", new_name="surah"),
        migrations.AlterField(
            model_name="assetversionentry",
            name="surah",
            field=models.ForeignKey(
                blank=True,
                help_text="Canonical surah (1-114) — set only for surah-template assets",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="+",
                to="quran.surah",
            ),
        ),
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    "ALTER TABLE content_assetversionentry RENAME CONSTRAINT unique_entry_per_version_sura_column TO unique_entry_per_version_surah_column",
                    "ALTER TABLE content_assetversionentry RENAME CONSTRAINT unique_entry_per_version_surah_column TO unique_entry_per_version_sura_column",
                ),
            ],
            # Postgres tracks the renamed column inside the check constraint, so
            # only Django's copy of its condition needs updating.
            state_operations=[
                migrations.RemoveConstraint(model_name="assetversionentry", name="entry_exactly_one_unit"),
                migrations.AddConstraint(
                    model_name="assetversionentry",
                    constraint=models.CheckConstraint(
                        condition=models.Q(
                            models.Q(
                                ("ayah__isnull", True),
                                ("from_ayah__isnull", True),
                                ("from_word__isnull", True),
                                ("page_no__isnull", True),
                                ("surah__isnull", False),
                                ("to_ayah__isnull", True),
                                ("to_word__isnull", True),
                                ("word__isnull", True),
                            ),
                            models.Q(
                                ("ayah__isnull", False),
                                ("from_ayah__isnull", True),
                                ("from_word__isnull", True),
                                ("page_no__isnull", True),
                                ("surah__isnull", True),
                                ("to_ayah__isnull", True),
                                ("to_word__isnull", True),
                                ("word__isnull", True),
                            ),
                            models.Q(
                                ("ayah__isnull", True),
                                ("from_ayah__isnull", True),
                                ("from_word__isnull", True),
                                ("page_no__isnull", True),
                                ("surah__isnull", True),
                                ("to_ayah__isnull", True),
                                ("to_word__isnull", True),
                                ("word__isnull", False),
                            ),
                            models.Q(
                                ("ayah__isnull", True),
                                ("from_ayah__isnull", True),
                                ("from_word__isnull", True),
                                ("page_no__isnull", False),
                                ("surah__isnull", True),
                                ("to_ayah__isnull", True),
                                ("to_word__isnull", True),
                                ("word__isnull", True),
                            ),
                            models.Q(
                                ("ayah__isnull", True),
                                ("from_ayah__isnull", False),
                                ("from_word__isnull", True),
                                ("page_no__isnull", True),
                                ("surah__isnull", True),
                                ("to_ayah__isnull", False),
                                ("to_word__isnull", True),
                                ("word__isnull", True),
                            ),
                            models.Q(
                                ("ayah__isnull", True),
                                ("from_ayah__isnull", True),
                                ("from_word__isnull", False),
                                ("page_no__isnull", True),
                                ("surah__isnull", True),
                                ("to_ayah__isnull", True),
                                ("to_word__isnull", False),
                                ("word__isnull", True),
                            ),
                            _connector="OR",
                        ),
                        name="entry_exactly_one_unit",
                    ),
                ),
                migrations.RemoveConstraint(
                    model_name="assetversionentry", name="unique_entry_per_version_sura_column"
                ),
                migrations.AddConstraint(
                    model_name="assetversionentry",
                    constraint=models.UniqueConstraint(
                        fields=("version", "surah", "column"), name="unique_entry_per_version_surah_column"
                    ),
                ),
            ],
        ),
        migrations.RenameField(model_name="assetversionchange", old_name="sura", new_name="surah"),
        migrations.AlterField(
            model_name="assetversionchange",
            name="surah",
            field=models.ForeignKey(
                blank=True,
                help_text="Canonical surah (1-114) — set only for surah-template assets",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="+",
                to="quran.surah",
            ),
        ),
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    "ALTER TABLE content_assetversionchange RENAME CONSTRAINT unique_change_per_version_sura_column TO unique_change_per_version_surah_column",
                    "ALTER TABLE content_assetversionchange RENAME CONSTRAINT unique_change_per_version_surah_column TO unique_change_per_version_sura_column",
                ),
            ],
            # Postgres tracks the renamed column inside the check constraint, so
            # only Django's copy of its condition needs updating.
            state_operations=[
                migrations.RemoveConstraint(model_name="assetversionchange", name="change_exactly_one_unit"),
                migrations.AddConstraint(
                    model_name="assetversionchange",
                    constraint=models.CheckConstraint(
                        condition=models.Q(
                            models.Q(
                                ("ayah__isnull", True),
                                ("from_ayah__isnull", True),
                                ("from_word__isnull", True),
                                ("page_no__isnull", True),
                                ("surah__isnull", False),
                                ("to_ayah__isnull", True),
                                ("to_word__isnull", True),
                                ("word__isnull", True),
                            ),
                            models.Q(
                                ("ayah__isnull", False),
                                ("from_ayah__isnull", True),
                                ("from_word__isnull", True),
                                ("page_no__isnull", True),
                                ("surah__isnull", True),
                                ("to_ayah__isnull", True),
                                ("to_word__isnull", True),
                                ("word__isnull", True),
                            ),
                            models.Q(
                                ("ayah__isnull", True),
                                ("from_ayah__isnull", True),
                                ("from_word__isnull", True),
                                ("page_no__isnull", True),
                                ("surah__isnull", True),
                                ("to_ayah__isnull", True),
                                ("to_word__isnull", True),
                                ("word__isnull", False),
                            ),
                            models.Q(
                                ("ayah__isnull", True),
                                ("from_ayah__isnull", True),
                                ("from_word__isnull", True),
                                ("page_no__isnull", False),
                                ("surah__isnull", True),
                                ("to_ayah__isnull", True),
                                ("to_word__isnull", True),
                                ("word__isnull", True),
                            ),
                            models.Q(
                                ("ayah__isnull", True),
                                ("from_ayah__isnull", False),
                                ("from_word__isnull", True),
                                ("page_no__isnull", True),
                                ("surah__isnull", True),
                                ("to_ayah__isnull", False),
                                ("to_word__isnull", True),
                                ("word__isnull", True),
                            ),
                            models.Q(
                                ("ayah__isnull", True),
                                ("from_ayah__isnull", True),
                                ("from_word__isnull", False),
                                ("page_no__isnull", True),
                                ("surah__isnull", True),
                                ("to_ayah__isnull", True),
                                ("to_word__isnull", False),
                                ("word__isnull", True),
                            ),
                            _connector="OR",
                        ),
                        name="change_exactly_one_unit",
                    ),
                ),
                migrations.RemoveConstraint(
                    model_name="assetversionchange", name="unique_change_per_version_sura_column"
                ),
                migrations.AddConstraint(
                    model_name="assetversionchange",
                    constraint=models.UniqueConstraint(
                        fields=("version", "surah", "column"), name="unique_change_per_version_surah_column"
                    ),
                ),
            ],
        ),
    ]
