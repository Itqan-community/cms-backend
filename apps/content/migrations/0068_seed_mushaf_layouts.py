from django.apps.registry import Apps
from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.models import Q

# The standard printings a page-based asset can follow: (English name, Arabic name, pages).
LAYOUTS = [
    ("Madinah Mushaf", "مصحف المدينة", 604),
    ("Shamarly Mushaf", "مصحف الشمرلي", 522),
]


def seed_mushaf_layouts(apps: Apps, schema_editor: BaseDatabaseSchemaEditor | None) -> None:
    """Create the standard layouts so the page-template selector is never empty.

    A layout already present under either name is left untouched, so an admin's
    edits survive and re-running never duplicates.
    """
    MushafLayout = apps.get_model("content", "MushafLayout")
    for name_en, name_ar, page_count in LAYOUTS:
        exists = MushafLayout.objects.filter(
            Q(name=name_en) | Q(name_en=name_en) | Q(name_ar=name_ar)
        ).exists()
        if not exists:
            MushafLayout.objects.create(
                name=name_en, name_en=name_en, name_ar=name_ar, page_count=page_count
            )


class Migration(migrations.Migration):
    dependencies = [("content", "0067_validate_entry_unit_constraints")]

    # Reversing is a no-op: page-based assets may already reference these layouts.
    operations = [migrations.RunPython(seed_mushaf_layouts, migrations.RunPython.noop)]
