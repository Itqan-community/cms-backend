from django.db import migrations
from django.db.models import Max


def initialize_cursor(apps, schema_editor):
    """Start the Django fold-in at deploy time: older UsageEvent rows carry the proxy IP, and rows
    written after the deploy (views, downloads, CLI installs) must not be skipped by a later first run."""
    UsageImportState = apps.get_model("usage_tracking", "UsageImportState")
    if UsageImportState.objects.filter(key="django_foldin", cursor__isnull=False).exists():
        return
    UsageEvent = apps.get_model("content", "UsageEvent")
    TrafficEvent = apps.get_model("usage_tracking", "TrafficEvent")
    UsageImportState.objects.update_or_create(
        key="django_foldin",
        defaults={
            "cursor": UsageEvent.objects.aggregate(top=Max("id"))["top"] or 0,
            "traffic_cursor": TrafficEvent.objects.aggregate(top=Max("id"))["top"] or 0,
        },
    )


class Migration(migrations.Migration):
    dependencies = [
        ("usage_tracking", "0004_usage_import_state_cursors"),
        ("content", "0007_publish_newest_mushaf_and_font_versions"),
    ]

    operations = [migrations.RunPython(initialize_cursor, migrations.RunPython.noop)]
