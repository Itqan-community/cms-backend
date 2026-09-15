"""Per-language authorization for an asset's renditions.

A publisher member works only in the languages assigned to their membership
(``publishers.MemberLanguage``). This module is the single place that rule is
evaluated, so editing and reviewing cannot drift apart.

Layering: the assignment lookup lives in ``publishers`` and knows nothing about
content; the bypass needs the asset in order to enumerate its languages, so it
lives here. That keeps the dependency pointing ``content -> publishers``.
"""

from __future__ import annotations

from django.db.models import Q
from django.utils.translation import gettext as _

from apps.content.models import Asset, AssetVersion
from apps.core.ninja_utils.errors import ItqanError
from apps.core.permission_utils import check_permission
from apps.core.permissions import PermissionChoice
from apps.publishers.models import MemberLanguage, PublisherMember
from apps.publishers.services.membership import member_languages
from apps.users.models import User

__all__ = [
    "allowed_languages",
    "assign_language_to_member",
    "filter_versions_to_allowed",
    "require_language",
    "require_version_id",
    "require_version_language",
]


def _asset_languages(asset: Asset) -> set[str]:
    """Every language on the asset, including the source.

    The source is included deliberately: it is a rendition like any other and is
    gated like any other, so a member assigned only 'fr' cannot edit the original.
    """
    languages = set(asset.languages.values_list("language", flat=True))
    # An asset whose source rendition row has not been materialised yet still has
    # a source language on the asset itself.
    languages.add(asset.language)
    return languages


def allowed_languages(user: User, asset: Asset) -> set[str]:
    """The languages of ``asset`` this user may work in.

    Holders of ``PORTAL_ACCESS_ALL_LANGUAGES`` are treated as assigned to every
    language on the asset. The permission grants no editing or reviewing rights of
    its own — what the user may DO in those languages is still decided by their
    ``PORTAL_UPDATE_*`` / ``PORTAL_REVIEW_CONTENT`` permissions.
    """
    if check_permission(user, PermissionChoice.PORTAL_ACCESS_ALL_LANGUAGES):
        return _asset_languages(asset)
    return member_languages(user, asset.publisher_id)


def require_language(user: User, asset: Asset, language: str) -> None:
    """Raise 403 ``language_not_assigned`` unless the user may work in ``language``."""
    if language not in allowed_languages(user, asset):
        raise ItqanError(
            error_name="language_not_assigned",
            message=_("You are not assigned to the language {language}.").format(language=language),
            status_code=403,
        )


def assign_language_to_member(user: User, asset: Asset, language: str) -> None:
    """Assign ``language`` to this user's membership in the asset's publisher.

    Called when a member adds a language to an asset: without it they would create
    a language they are immediately unable to edit. A no-op when the user has no
    active membership in that publisher (Itqan staff acting across publishers),
    and idempotent when the assignment already exists.
    """
    member = PublisherMember.objects.filter(
        user=user, publisher_id=asset.publisher_id, status=PublisherMember.StatusChoice.ACTIVE
    ).first()
    if member is None:
        return
    MemberLanguage.objects.get_or_create(member=member, language=language)


def require_version_language(user: User, asset: Asset, version: AssetVersion) -> None:
    """Gate a version-scoped operation by the language that version belongs to.

    Version-scoped endpoints take an id rather than a language, so without this
    an unassigned language's content would be reachable by id alone — filtering
    the language list would then be decorative rather than a control.
    """
    require_language(user, asset, version.resolved_language)


def require_version_id(user: User, asset: Asset, version_id: int) -> None:
    """``require_version_language`` for a version identified only by id.

    A version id that does not belong to this asset is left alone: the endpoint's
    own lookup reports that as a 404, and pre-empting it here would turn a missing
    version into a misleading 403.
    """
    version = AssetVersion.objects.filter(pk=version_id, asset=asset).select_related("asset_language", "asset").first()
    if version is not None:
        require_version_language(user, asset, version)


def filter_versions_to_allowed(user: User, asset: Asset, versions):
    """Narrow a version queryset to the languages this user may work in.

    Legacy versions carry no ``asset_language`` and belong to the source, so they
    are included exactly when the source language is allowed.
    """
    allowed = allowed_languages(user, asset)
    language_q = Q(asset_language__language__in=allowed)
    if asset.language in allowed:
        language_q |= Q(asset_language__isnull=True)
    return versions.filter(language_q)
