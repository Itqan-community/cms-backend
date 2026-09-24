from django.apps.registry import Apps
from django.db import migrations, router
from django.db.backends.base.schema import BaseDatabaseSchemaEditor


def fix_word_positions(apps: Apps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    """Renumber every ayah's words 1..n in word-id (reading) order.

    ``import_quran`` used to store the source CSV's ``aya_index`` — the ayah's
    number within its sura — as ``position_in_ayah``, so every word of an ayah
    shared one position. One set-based UPDATE fixes all ~77k rows and only
    touches rows whose position is wrong, so re-running changes nothing.
    """
    Word = apps.get_model("quran", "Word")
    if not router.allow_migrate_model(schema_editor.connection.alias, Word):
        return
    table = schema_editor.quote_name(Word._meta.db_table)
    # Only the model's own quoted table name is interpolated; no user input.
    sql = (
        f"UPDATE {table} AS w SET position_in_ayah = ranked.position "  # nosec B608
        "FROM (SELECT id, ROW_NUMBER() OVER (PARTITION BY ayah_id ORDER BY id) AS position "
        f"FROM {table}) AS ranked "
        "WHERE w.id = ranked.id AND w.position_in_ayah <> ranked.position"
    )
    schema_editor.execute(sql)


class Migration(migrations.Migration):
    dependencies = [("quran", "0001_initial")]

    # The previous values were wrong, so there is nothing to restore on reverse.
    operations = [migrations.RunPython(fix_word_positions, migrations.RunPython.noop)]
