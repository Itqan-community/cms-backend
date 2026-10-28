from django.db import migrations
from django.db.models import F


def backfill_name_translations(apps, schema_editor):
    """Existing roles only had one name; use it for both languages until an admin edits them."""
    PublisherGroup = apps.get_model("publishers", "PublisherGroup")
    PublisherGroup.objects.filter(name_en__isnull=True).update(name_en=F("name"))
    PublisherGroup.objects.filter(name_ar__isnull=True).update(name_ar=F("name"))


class Migration(migrations.Migration):
    # Its own migration: Postgres refuses ALTER TABLE in the transaction that updated the rows
    # ("pending trigger events"), so the constraints come in the next migration.
    dependencies = [
        ("publishers", "0005_publishergroup_name_translations"),
    ]

    operations = [
        migrations.RunPython(backfill_name_translations, migrations.RunPython.noop),
    ]
