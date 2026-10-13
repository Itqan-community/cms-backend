from django.db import migrations, models


def publish_newest_versions(apps, schema_editor):
    """Mushafs and fonts now serve an explicitly published version. Pin each of
    their languages to its newest committed version — what consumers were served
    until now — so nothing they see changes."""
    AssetLanguage = apps.get_model("content", "AssetLanguage")
    AssetVersion = apps.get_model("content", "AssetVersion")
    renditions = AssetLanguage.objects.filter(
        asset__category__in=["mushaf", "font"], published_version__isnull=True
    ).select_related("asset")
    for rendition in renditions:
        # Rows that predate per-language renditions carry no language: they belong to the source.
        language_q = models.Q(asset_language=rendition)
        if rendition.is_source:
            language_q |= models.Q(asset_language__isnull=True)
        newest = (
            AssetVersion.objects.filter(language_q, asset_id=rendition.asset_id, state="published")
            .order_by("-created_at", "-pk")
            .first()
        )
        if newest is None:
            continue
        AssetLanguage.objects.filter(pk=rendition.pk).update(published_version=newest)
        AssetVersion.objects.filter(pk=newest.pk, first_published_at__isnull=True).update(
            first_published_at=models.F("created_at")
        )


class Migration(migrations.Migration):

    dependencies = [
        ("content", "0006_assetversion_package_availability"),
    ]

    operations = [
        migrations.RunPython(publish_newest_versions, migrations.RunPython.noop),
    ]
