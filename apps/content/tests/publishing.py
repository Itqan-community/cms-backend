from apps.content.models import AssetLanguage, AssetVersion


def publish(version: AssetVersion) -> AssetVersion:
    """Make ``version`` the one consumers are served for its language, as the
    portal's publish action does once a reviewed version is approved."""
    AssetLanguage.objects.filter(pk=version.asset_language_id).update(published_version=version)
    return version
