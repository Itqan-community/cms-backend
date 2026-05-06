import functools
from typing import TYPE_CHECKING, Protocol

from django.core.cache import cache
from django.db.models import Q
from django.http import HttpRequest, HttpResponse, JsonResponse
from rest_framework import status

from apps.publishers.models import Domain, Publisher

if TYPE_CHECKING:
    from apps.core.ninja_utils.request import Request


class PublisherMiddleware:
    def __init__(self, get_response) -> None:
        self.get_response = get_response

    def __call__(self, request: "Request") -> HttpResponse | JsonResponse:

        active = self.is_publisher_active(request)
        if active is None:
            pass
        elif not active:
            return JsonResponse(
                {"error": "Publisher's page is closed for maintenance, please try again later"},
                status=status.HTTP_423_LOCKED,
            )

        return self.get_response(request)

    @staticmethod
    def is_publisher_active(request) -> bool | None:
        """modifies the request and adds publisher objects"""
        domain = get_publisher_domain(request, "X-Tenant") or get_publisher_domain(request, "Origin")
        request.publisher_domain = domain
        request.publisher = domain.publisher if domain else None
        request.publisher_q = functools.partial(publisher_q, request.publisher)
        request.user_publisher_q = lambda lookup="publisher": user_publisher_q(request.user, lookup)
        if domain is None:
            return None
        if not domain.is_active:
            return False
        return True


def remove_www(hostname: str) -> str:
    """
    Removes www. from the beginning of the address. Only for
    routing purposes. www.test.com/login/ and test.com/login/ should
    find the same tenant.
    """
    if hostname.startswith("www."):
        return hostname[4:]
    return hostname


def get_publisher_domain(request: HttpRequest, header_name: str) -> Domain | None:
    """
    Retrieve a domain based on the Host header
    """

    referer = (
        request.headers.get(header_name).rstrip("/").replace("https://", "").replace("http://", "")
        if request.headers.get(header_name)
        else None
    )
    if not referer:
        return None

    host: str = remove_www(referer.split(":")[0])
    if host:
        result = cache.get(f"x_tenant-{host}")
        if not result:
            result = Domain.objects.filter(domain=host).select_related("publisher").first()
            cache.set(f"x_tenant-{host}", result, timeout=60 * 5)
        return result
    return None


class PublisherQ(Protocol):
    """Protocol for publisher_q to be used in type hinting, for the Request Object."""

    def __call__(self, lookup: str = "publisher") -> Q: ...


def publisher_q(publisher: Publisher | None, lookup: str = "publisher") -> Q:
    """
    returns a Q object base on the publisher in the request, if any.
    useful for frequent filtering
    """
    return Q(**{lookup: publisher}) if publisher else Q()


class UserPublisherQ(Protocol):
    """Protocol for user_publisher_q used in type hinting on the Request object."""

    def __call__(self, lookup: str = "publisher_id") -> Q: ...


def user_publisher_q(user, lookup: str = "publisher_id") -> Q:
    """
    Returns a Q object that scopes a queryset to the publishers the user belongs to.

    - Anonymous users: matches nothing.
    - Staff users: matches everything (Q()).
    - Otherwise: matches rows where the `<lookup>` field is in the user's PublisherMember set.
      Users with no memberships match nothing.

    `lookup` is the full ORM lookup path to the publisher id (e.g. "publisher_id",
    "asset__publisher_id", "id" when filtering Publisher itself).

    The membership ID list is cached on the user instance for the request lifetime.
    """
    if user is None or not getattr(user, "is_authenticated", False):
        return Q(pk__in=[])
    if getattr(user, "is_staff", False):
        return Q()

    publisher_ids = getattr(user, "_cached_publisher_ids", None)
    if publisher_ids is None:
        publisher_ids = list(user.publishers.values_list("id", flat=True))
        user._cached_publisher_ids = publisher_ids

    if not publisher_ids:
        return Q(pk__in=[])
    return Q(**{f"{lookup}__in": publisher_ids})
