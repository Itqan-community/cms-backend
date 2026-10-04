from model_bakery import baker

from apps.content.models import REVIEWED_CATEGORIES, Asset, AssetLanguage, AssetVersion


def publish(version: AssetVersion) -> AssetVersion:
    """Make ``version`` the one consumers are served for its language, as the
    portal's publish action does once a reviewed version is approved."""
    AssetLanguage.objects.filter(pk=version.asset_language_id).update(published_version=version)
    return version


def make_visible(assets: Asset | list[Asset]) -> Asset | list[Asset]:
    """Give each translation / tafsir an available language with a published
    version, so it is listed to consumers (``consumer_visible_q``). Other
    categories need nothing. Accepts one asset or a ``_quantity`` bake's list and
    returns what it was given."""
    for asset in assets if isinstance(assets, list) else [assets]:
        if asset.category in REVIEWED_CATEGORIES:
            publish(baker.make(AssetVersion, asset=asset))
    return assets
