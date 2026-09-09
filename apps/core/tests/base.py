import base64
import secrets
from typing import Literal

import boto3
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from moto import mock_aws
from oauth2_provider.models import AccessToken as OAuth2AccessToken, Application
from rest_framework.test import APIClient

from apps.core.permissions import PermissionChoice
from apps.publishers.models import Domain
from apps.users.models import User


@override_settings(CELERY_TASK_ALWAYS_EAGER=True)
class BaseTestCase(TestCase):
    client_class = APIClient
    client: APIClient

    @classmethod
    def setUpTestData(cls) -> None:
        # Register the cleanup *before* starting the mock so that a partial
        # failure in mock_storage() is still undone. Class cleanups run after
        # TestCase.tearDownClass(), which restores Django's default class
        # teardown: roll back the class-level transaction (cls_atomics) and
        # close the DB connections between test classes (see issue #469).
        cls.addClassCleanup(cls.teardown_storage)
        cls.mock_storage()

    @classmethod
    def teardown_storage(cls) -> None:
        """Undo mock_storage().

        Intentionally runs via addClassCleanup instead of an overridden
        tearDownClass: Django's TestCase.tearDownClass() rolls back the
        class-level transaction and closes the DB connections between test
        classes. Overriding it without calling super() (the previous
        behavior) leaked an open transaction and kept a single connection
        alive for the entire test session.
        """
        storage_override = getattr(cls, "_storage_override", None)
        if storage_override is not None:
            storage_override.disable()
        mock_aws = getattr(cls, "mock_aws", None)
        if mock_aws is not None:
            mock_aws.stop()

        super().tearDownClass()

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

    def authenticate_user(
        self,
        user: User | None,
        language: Literal["en", "ar"] | None = "en",
        domain: Domain | None = None,
        **kwargs,
    ):
        """
        if `user` is supplied with None, the authentication will be cleared
        if `user` is supplied with a `User`, it will be authenticated using JWT tokens
        """
        if not kwargs:
            kwargs = {}

        if domain is None:
            kwargs.pop("HTTP_ORIGIN", None)
        else:
            kwargs["HTTP_ORIGIN"] = domain.domain
            settings.ALLOWED_HOSTS.append(domain.domain)

        if user is None:
            # Clear authentication
            # kwargs.pop("HTTP_X_SESSION_TOKEN", None)
            kwargs.pop("HTTP_AUTHORIZATION", None)
        else:
            self.client.force_login(user=user)
            # token = create_access_token(user, session=self.client.session, claims={})
            kwargs["HTTP_X_SESSION_TOKEN"] = self.client.session.session_key
            # self.client.cookies.clear()

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

    def give_permission(self, user: User, codename: PermissionChoice) -> None:
        from django.contrib.auth.models import Permission

        user.user_permissions.add(Permission.objects.get(codename=codename))

    def remove_permission(self, user: User, codename: PermissionChoice) -> None:
        from django.contrib.auth.models import Permission

        user.user_permissions.remove(Permission.objects.get(codename=codename))
