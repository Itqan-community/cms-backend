from django.http import HttpRequest

from apps.users.models import User


class Request(HttpRequest):
    auth : User
    user : User