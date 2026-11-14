from datetime import timedelta

from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from model_bakery import baker

from apps.content.models import (
    Asset,
    AssetLanguage,
    AssetTemplateChoice,
    AssetVersion,
    CategoryChoice,
    StatusChoice,
    VersionStateChoice,
)
from apps.core.permissions import PermissionChoice
from apps.core.tests.base import BaseTestCase
from apps.publishers.models import Publisher
from apps.users.models import User


class VersionListQueriesBaseTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.publisher = baker.make(Publisher, name="Publisher")
        self.asset = baker.make(
            Asset,
            category=CategoryChoice.TEXT,
            template=AssetTemplateChoice.AYAH,
            publisher=self.publisher,
            status=StatusChoice.READY,
            name="Asset",
            slug="list-asset",
            language="ar",
        )
        self.user = User.objects.create_user(email="reader@example.com", name="Reader", is_staff=True)
        self.give_permission(self.user, PermissionChoice.PORTAL_READ_TEXT_ASSET)
        self.give_permission(self.user, PermissionChoice.PORTAL_ACCESS_ALL_LANGUAGES)
        self.base_time = timezone.now() - timedelta(days=30)

    def make_version(self, minutes: int, language: str | None = "ar") -> AssetVersion:
        asset_language = None
        if language is not None:
            asset_language, _ = AssetLanguage.objects.get_or_create(
                asset=self.asset, language=language, defaults={"is_source": language == self.asset.language}
            )
        version = baker.make(
            AssetVersion,
            asset=self.asset,
            asset_language=asset_language,
            name=f"1.{minutes}",
            state=VersionStateChoice.PUBLISHED,
        )
        # `created_at` is auto_now_add and `save()` tags untagged versions with the source
        # language: set both after the insert so the order and legacy rows are explicit.
        AssetVersion.objects.filter(pk=version.pk).update(
            created_at=self.base_time + timedelta(minutes=minutes), asset_language=asset_language
        )
        return version

    def list_versions(self):
        return self.client.get(f"/portal/text-assets/{self.asset.slug}/versions/")


class TextAssetVersionListQueriesTest(VersionListQueriesBaseTest):
    def test_list_versions_where_more_versions_should_run_same_number_of_queries(self):
        # Arrange
        self.authenticate_user(self.user)
        # Both languages from the start: the list runs a few queries per language, never per row.
        for minutes in range(2):
            self.make_version(minutes, language="en" if minutes % 2 else "ar")
        with CaptureQueriesContext(connection) as few:
            self.list_versions()
        for minutes in range(2, 8):
            self.make_version(minutes, language="en" if minutes % 2 else "ar")

        # Act
        with CaptureQueriesContext(connection) as many:
            response = self.list_versions()

        # Assert
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["results"]), 8)
        self.assertEqual(len(many), len(few), [query["sql"] for query in many.captured_queries])

    def test_list_versions_where_several_languages_should_flag_latest_and_first_per_language(self):
        # Arrange
        self.authenticate_user(self.user)
        legacy = self.make_version(0, language=None)
        ar_first = self.make_version(1)
        en_first = self.make_version(2, language="en")
        ar_latest = self.make_version(3)
        en_latest = self.make_version(4, language="en")

        # Act
        response = self.list_versions()

        # Assert
        self.assertEqual(response.status_code, 200)
        flags = {row["id"]: (row["is_active"], row["is_first"]) for row in response.json()["results"]}
        self.assertEqual(
            flags,
            {
                # Legacy rows (no asset_language) are their own "first" group and never the head.
                legacy.id: (False, True),
                ar_first.id: (False, True),
                en_first.id: (False, True),
                ar_latest.id: (True, False),
                en_latest.id: (True, False),
            },
        )
