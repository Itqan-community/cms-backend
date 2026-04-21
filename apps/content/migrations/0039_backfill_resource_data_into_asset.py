from django.db import migrations
from django.utils.text import slugify

from apps.content.models import CategoryChoice, StatusChoice


def _generate_unique_slug(Asset, base_name):
    base_slug = slugify(base_name[:50], allow_unicode=True) or "asset"
    slug = base_slug
    counter = 1
    while Asset.objects.filter(slug=slug).exists():
        slug = f"{base_slug[:40]}-{counter}"
        counter += 1
    return slug


def forwards(apps, schema_editor):
    Resource = apps.get_model("content", "Resource")
    Asset = apps.get_model("content", "Asset")
    Reciter = apps.get_model("content", "Reciter")
    Riwayah = apps.get_model("content", "Riwayah")
    Qiraah = apps.get_model("content", "Qiraah")
    ContentIssueReport = apps.get_model("content", "ContentIssueReport")
    UsageEvent = apps.get_model("content", "UsageEvent")
    ContentType = apps.get_model("contenttypes", "ContentType")

    reciter = Reciter.objects.first()
    riwayah = Riwayah.objects.first()
    qiraah = Qiraah.objects.first()

    # 1. Create placeholder Asset for orphan Resources (Resources with zero Assets)
    orphan_resources = Resource.objects.filter(assets__isnull=True).iterator()
    orphan_asset_ids_by_resource = {}
    for resource in orphan_resources:
        placeholder = Asset.objects.create(
            resource=resource,
            publisher_id=resource.publisher_id,
            status=StatusChoice.DRAFT,
            name_ar=resource.name_ar,
            name_en=resource.name_en,
            name=resource.name,
            slug=_generate_unique_slug(Asset, resource.name),
            description=resource.description,
            description_en=resource.description_en,
            description_ar=resource.description_ar,
            long_description="",
            category=resource.category,
            license=resource.license,
            file_size="",
            format="",
            encoding="UTF-8",
            version="",
            language="",
            is_external=resource.is_external,
            external_url=resource.external_url,
            reciter =reciter if resource.category==CategoryChoice.RECITATION else None,
            riwayah=riwayah if resource.category==CategoryChoice.RECITATION else None,
            qiraah=qiraah if resource.category==CategoryChoice.RECITATION else None,
        )
        orphan_asset_ids_by_resource[resource.id] = placeholder.id

    # 2. Backfill Asset.publisher_id and Asset.status for all remaining (non-orphan) Assets
    for asset in Asset.objects.filter(publisher__isnull=True).select_related("resource").iterator():
        asset.publisher_id = asset.resource.publisher_id
        asset.status = asset.resource.status
        asset.save(update_fields=["publisher_id", "status"])

    # 3. Remap ContentIssueReport rows referencing Resource -> first Asset of that Resource
    try:
        resource_ct = ContentType.objects.get(app_label="content", model="resource")
        asset_ct = ContentType.objects.get(app_label="content", model="asset")
    except ContentType.DoesNotExist:
        resource_ct = None

    if resource_ct is not None:
        reports = ContentIssueReport.objects.filter(content_type=resource_ct)
        for report in reports.iterator():
            first_asset = (
                Asset.objects.filter(resource_id=report.object_id).order_by("id").values_list("id", flat=True).first()
            )
            if first_asset is None:
                # Shouldn't happen after step 1 (every Resource now has at least one Asset), but guard anyway
                report.delete()
                continue
            report.content_type = asset_ct
            report.object_id = first_asset
            report.save(update_fields=["content_type", "object_id"])

    # 4. Delete UsageEvent rows where subject_kind='resource'
    UsageEvent.objects.filter(subject_kind="resource").delete()


def backwards(apps, schema_editor):
    # Data migration is not reversible:
    # - We cannot tell orphan-derived Assets apart from real ones after the fact
    # - Dropped UsageEvent rows are gone
    # - ContentIssueReport remapping loses the original resource linkage
    # Running backwards is a no-op; schema revert is handled by other migrations.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("content", "0038_expand_asset_for_resource_removal"),
        ("contenttypes", "0002_remove_content_type_name"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
