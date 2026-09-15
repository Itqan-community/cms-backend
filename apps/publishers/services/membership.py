from django.utils.translation import gettext_lazy as _
from rest_framework.exceptions import PermissionDenied

from apps.publishers.models import MemberLanguage, PublisherMember
from apps.users.models import User


def enforce_publisher_membership(user: User, publisher_id: int) -> None:
    """
    Ensure user may act on the given publisher.
    Itqan (is_staff) bypass. Otherwise user must have ACTIVE PublisherMember row.
    """
    if getattr(user, "is_staff", False):
        return
    is_active_member = PublisherMember.objects.filter(
        user=user, publisher_id=publisher_id, status=PublisherMember.StatusChoice.ACTIVE
    ).exists()
    if not is_active_member:
        raise PermissionDenied(_("You do not have access to this publisher."))


def member_languages(user: User, publisher_id: int) -> set[str]:
    """The languages this user is assigned to work in for this publisher.

    Scoped to the user's ACTIVE membership in *that* publisher, so an assignment
    made for one publisher never grants access to another publisher's content.
    An empty set means the user works in no languages there; the bypass permission,
    not an empty assignment, is how someone is granted every language.
    """
    return set(
        MemberLanguage.objects.filter(
            member__user=user,
            member__publisher_id=publisher_id,
            member__status=PublisherMember.StatusChoice.ACTIVE,
        ).values_list("language", flat=True)
    )


def get_user_member_publisher_ids(user: User) -> list[int]:
    """Publisher ids of the user's ACTIVE memberships (a user may belong to several)."""
    return list(
        PublisherMember.objects.filter(user=user, status=PublisherMember.StatusChoice.ACTIVE).values_list(
            "publisher_id", flat=True
        )
    )


def enforce_member_scope(user: User, member: PublisherMember) -> None:
    """
    Verify user has access to the given member's publisher. Staff bypass.
    Raises PermissionDenied if user has no ACTIVE membership there.
    """
    if getattr(user, "is_staff", False):
        return
    if member.publisher_id not in get_user_member_publisher_ids(user):
        raise PermissionDenied(_("You do not have access to this member."))
