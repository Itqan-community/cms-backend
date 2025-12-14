from typing import Literal
from unittest.mock import patch

import boto3
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from moto import mock_aws
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

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
            access_token = str(AccessToken.for_user(user))
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
