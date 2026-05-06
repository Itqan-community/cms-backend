from django.http import HttpRequest

from apps.publishers.middlewares.publisher_middleware import PublisherQ
from apps.publishers.models import Domain, Publisher
from apps.users.models import User


class Request(HttpRequest):
    """
    Used for type hinting in django-ninja endpoints to have better autocompletion
    """

    auth: User
    user: User
    publisher_domain: Domain | None
    publisher: Publisher | None
    publisher_q: PublisherQ
