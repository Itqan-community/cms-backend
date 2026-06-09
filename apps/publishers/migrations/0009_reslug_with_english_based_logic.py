from django.db import migrations

from apps.core.slugs import slugify_name


def reslug_english_based(apps, schema_editor):
    db_alias = schema_editor.connection.alias
    Publisher = apps.get_model("publishers", "Publisher")

    taken: set[str] = set()
    for publisher in Publisher.objects.using(db_alias).iterator(chunk_size=1000):
        base_slug = slugify_name(getattr(publisher, "name_en", None), getattr(publisher, "name_ar", None))
        base_slug = base_slug or f"publisher-{publisher.pk}"
        slug = base_slug
        counter = 1
        while slug in taken:
            slug = f"{base_slug[:40]}-{counter}"
            counter += 1
        taken.add(slug)
        if publisher.slug != slug:
            publisher.slug = slug
            publisher.save(update_fields=["slug"])


def noop_reverse(apps, schema_editor):
    """The previous slugs cannot be reconstructed; leave the new ones in place."""


class Migration(migrations.Migration):

    dependencies = [
        ("publishers", "0008_publisher_mixpanel_board_url"),
    ]

    operations = [
        migrations.RunPython(reslug_english_based, noop_reverse),
    ]
