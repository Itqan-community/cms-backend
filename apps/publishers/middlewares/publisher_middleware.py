import functools
from typing import Protocol

from django.core.cache import cache
from django.db.models import Q
from django.http import JsonResponse
from rest_framework import status

from apps.publishers.models import Domain, Publisher


class PublisherMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):

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
        domain = get_publisher_domain(request)
        request.publisher_domain = domain
        request.publisher = domain.publisher if domain else None
        request.publisher_q = functools.partial(publisher_q, request.publisher)
        if domain is None:
            return None
        return True


def remove_www(hostname):
    """
    Removes www. from the beginning of the address. Only for
    routing purposes. www.test.com/login/ and test.com/login/ should
    find the same tenant.
    """
    if hostname.startswith("www."):
        return hostname[4:]

    return hostname


def get_publisher_domain(request) -> Domain | None:
    """
    Retrieve a domain based on the Host header
    """
    host: str = remove_www(request.get_host().split(":")[0])
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


def publisher_q(publisher: Publisher, lookup: str = "publisher") -> Q:
    """
    returns a Q object base on the publisher in the request, if any.
    useful for frequent filtering
    """
    return Q(**{lookup: publisher}) if publisher else Q()
