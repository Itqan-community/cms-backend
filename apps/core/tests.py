import base64
import secrets
from typing import Literal
from unittest.mock import patch

import boto3
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from moto import mock_aws
from oauth2_provider.models import AccessToken as OAuth2AccessToken, Application
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken as JWTAccessToken

from apps.users.models import User


class BaseTestCase(TestCase):
    client_class = APIClient
    client: APIClient

    @classmethod
    def setUpTestData(cls) -> None:
        cls.mock_storage()

    @classmethod
    def tearDownClass(cls) -> None:
        # Disable storage override
        try:
            cls._storage_override.disable()
        except Exception:
            pass
        # Stop moto mock to clean up between tests
        try:
            cls.mock_aws.stop()
        except Exception:
            pass

    @classmethod
    def mock_storage(cls):
        cls.mock_aws = mock_aws()
        cls.mock_aws.start()
        cls.bucket_name = "test-bucket"
        s3_client = boto3.client("s3", region_name="us-east-1")
        s3_client.create_bucket(Bucket=cls.bucket_name)
        cls._storage_override = override_settings(
            STORAGES={
                "default": {
                    "BACKEND": "django.core.files.storage.FileSystemStorage",
                },
                "staticfiles": {
                    "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
                },
            },
            MEDIA_ROOT=settings.MEDIA_ROOT,
            CLOUDFLARE_R2_BUCKET=cls.bucket_name,
            CLOUDFLARE_R2_ENDPOINT="http://localhost:5000",
            CLOUDFLARE_R2_ACCESS_KEY_ID="testing",
            CLOUDFLARE_R2_SECRET_ACCESS_KEY="testing",
        )
        cls._storage_override.enable()

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
            # Use AccessToken directly to avoid creating OutstandingToken entries during tests
            access_token = str(JWTAccessToken.for_user(user))
            kwargs["HTTP_AUTHORIZATION"] = f"Bearer {access_token}"

        headers = {
            "HTTP_ACCEPT_LANGUAGE": language,
        }

        for key, value in headers.items():
            if value and value is not None:
                kwargs[key] = value

        self.client.credentials(**kwargs)

    def authenticate_client(
        self,
        application: Application | None,
        user: User | None = None,
        grant_type: Literal["basic", "bearer"] = "bearer",
        language: Literal["en", "ar"] | None = "en",
        **kwargs,
    ):
        """
        if `application` is supplied with None, the authentication will be cleared
        if `application` is supplied with an `Application`, it will be authenticated
        using either Basic auth (client credentials) or Bearer token depending on `grant_type`.
        """
        if not kwargs:
            kwargs = {}

        if application is None:
            # Clear authentication
            kwargs.pop("HTTP_AUTHORIZATION", None)
        else:
            if grant_type == "bearer":
                # Generate OAuth2 access token
                token = OAuth2AccessToken.objects.create(
                    user=user or application.user,
                    application=application,
                    token=secrets.token_hex(20),
                    expires=timezone.now() + timezone.timedelta(days=1),
                    scope="read write",
                )
                auth_value = f"Bearer {token.token}"
            else:
                # Use Basic Auth with client_id and client_secret
                auth_str = f"{application.client_id}:{application.client_secret}"
                encoded_auth = base64.b64encode(auth_str.encode("ascii")).decode("ascii")
                auth_value = f"Basic {encoded_auth}"

            kwargs["HTTP_AUTHORIZATION"] = auth_value

        headers = {
            "HTTP_ACCEPT_LANGUAGE": language,
        }

        for key, value in headers.items():
            if value and value is not None:
                kwargs[key] = value

        self.client.credentials(**kwargs)

    def create_file(self, name: str, content: bytes, content_type: str) -> SimpleUploadedFile:
        return SimpleUploadedFile(name, content, content_type=content_type)
