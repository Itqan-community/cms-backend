from django.utils.translation import gettext_lazy as _
from rest_framework.exceptions import PermissionDenied

from apps.users.models import User


def enforce_publisher_membership(user: User, publisher_id: int) -> None:
    """
    Ensure the user is allowed to act on the given publisher.

    Staff users bypass the check. Otherwise the user must have a PublisherMember
    row for the given publisher_id, else PermissionDenied is raised.
    """
    if getattr(user, "is_staff", False):
        return
    if not user.publishers.filter(id=publisher_id).exists():
        raise PermissionDenied(_("You do not have access to this publisher."))
