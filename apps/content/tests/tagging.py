"""Tag text assets in tests: factories can't set a many-to-many field."""

from apps.content.models import Asset, AssetTag


def tagged(asset: Asset, *slugs: str) -> Asset:
    asset.tags.set(AssetTag.objects.filter(slug__in=slugs))
    return asset
