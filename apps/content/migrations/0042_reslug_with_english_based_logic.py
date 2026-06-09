from django.db import migrations

from apps.core.slugs import slugify_name


def _reslug_unique(model, db_alias, default_prefix):
    """Re-derive English-based slugs for a model with a globally unique slug."""
    taken: set[str] = set()
    for obj in model.objects.using(db_alias).iterator(chunk_size=1000):
        base_slug = slugify_name(getattr(obj, "name_en", None), getattr(obj, "name_ar", None))
        base_slug = base_slug or f"{default_prefix}-{obj.pk}"
        slug = base_slug
        counter = 1
        while slug in taken:
            slug = f"{base_slug[:40]}-{counter}"
            counter += 1
        taken.add(slug)
        if obj.slug != slug:
            obj.slug = slug
            obj.save(update_fields=["slug"])


def reslug_english_based(apps, schema_editor):
    db_alias = schema_editor.connection.alias

    Asset = apps.get_model("content", "Asset")
    Reciter = apps.get_model("content", "Reciter")
    Qiraah = apps.get_model("content", "Qiraah")
    Riwayah = apps.get_model("content", "Riwayah")

    _reslug_unique(Asset, db_alias, "asset")
    _reslug_unique(Reciter, db_alias, "reciter")
    _reslug_unique(Qiraah, db_alias, "qiraah")

    # Riwayah slug is not globally unique (scoped by qiraah), mirroring the
    # model's own save(): no collision handling.
    for riwayah in Riwayah.objects.using(db_alias).iterator(chunk_size=1000):
        slug = slugify_name(getattr(riwayah, "name_en", None), getattr(riwayah, "name_ar", None))
        slug = slug or f"riwayah-{riwayah.pk}"
        if riwayah.slug != slug:
            riwayah.slug = slug
            riwayah.save(update_fields=["slug"])


def noop_reverse(apps, schema_editor):
    """The previous slugs cannot be reconstructed; leave the new ones in place."""


class Migration(migrations.Migration):

    dependencies = [
        ("content", "0041_remove_contentissuereport_content_type_fields_and_add_asset"),
    ]

    operations = [
        migrations.RunPython(reslug_english_based, noop_reverse),
    ]
