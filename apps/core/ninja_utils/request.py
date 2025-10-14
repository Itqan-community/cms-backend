from django.http import HttpRequest

from apps.users.models import User


class Request(HttpRequest):
    """
    Used for type hinting in django-ninja endpoints to have better autocompletion
    """
    auth : User
    user : User