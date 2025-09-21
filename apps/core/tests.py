from typing import Literal
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.users.models import User


class BaseTestCase(TestCase):
    client_class = APIClient
    client: APIClient

    @classmethod
    def patch_on_commit(cls):
        patcher = patch("django.db.transaction.on_commit", side_effect=lambda f: f())
        patcher.start()
        cls.addClassCleanup(patcher.stop)

    def authenticate_user(
        self,
        user: User | None,
        language: Literal["en", "ar"] | None = "en",
        **kwargs,
    ):
        """
        if `user` is supplied with None, the authentication will be cleared
        if `user` is supplied with a `User`, it will be authenticated using JWT tokens
        """
        if not kwargs:
            kwargs = {}

        if user is None:
            # Clear authentication
            kwargs.pop("HTTP_AUTHORIZATION", None)
        else:
            # Generate JWT token for the user
            refresh = RefreshToken.for_user(user)
            access_token = str(refresh.access_token)
            kwargs["HTTP_AUTHORIZATION"] = f"Bearer {access_token}"

        headers = {
            "HTTP_ACCEPT_LANGUAGE": language,
        }

        for key, value in headers.items():
            if value and value is not None:
                kwargs[key] = value

        self.client.credentials(**kwargs)

    def create_file(self, name: str, content: bytes, content_type: str) -> SimpleUploadedFile:
        return SimpleUploadedFile(name, content, content_type=content_type)
