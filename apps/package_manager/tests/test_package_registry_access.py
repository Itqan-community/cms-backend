"""The caller's access in GET /packages/ and the key check at GET /packages/me/."""

from datetime import timedelta

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.utils import timezone
from model_bakery import baker

from apps.content.models import (
    Asset,
    AssetAccess,
    AssetAccessRequest,
    AssetTemplateChoice,
    AssetVersion,
    StatusChoice,
    VersionStateChoice,
)
from apps.core.tests.base import BaseTestCase
from apps.publishers.models import Publisher
from apps.users.models import APIKey, User


@override_settings(ENFORCE_ASSET_ACCESS_ON_PUBLIC_API=True, FRONTEND_BASE_URL="https://cms.example")
class PackageCatalogAccessTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.publisher = baker.make(Publisher, name="Publisher")
        self.user = User.objects.create_user(email="dev@example.com", name="Dev")

    def _gated_asset(self, slug: str = "gated") -> Asset:
        asset = Asset.objects.create(
            name=slug.title(),
            slug=slug,
            publisher=self.publisher,
            category="tafsir",
            template=AssetTemplateChoice.AYAH,
            license="CC0",
            file_size="1 MB",
            format="csv",
            description="desc",
            language="ar",
            status=StatusChoice.READY,
            is_open_access=False,
        )
        version = baker.make(
            AssetVersion,
            asset=asset,
            asset_language=asset.get_or_create_source_language(),
            name="1.0.0",
            state=VersionStateChoice.PUBLISHED,
        )
        version.file_url = SimpleUploadedFile(name=f"{slug}.csv", content=b"x")
        version.save()
        return asset

    def _request(self, asset: Asset, status: str) -> AssetAccessRequest:
        return baker.make(AssetAccessRequest, developer_user=self.user, asset=asset, status=status)

    def _grant(self, asset: Asset, *, expires_at=None) -> AssetAccess:
        request = self._request(asset, AssetAccessRequest.StatusChoice.APPROVED)
        return baker.make(AssetAccess, asset_access_request=request, user=self.user, asset=asset, expires_at=expires_at)

    def _catalog_item(self, *, with_key: bool) -> dict:
        headers = {}
        if with_key:
            _, raw_key = APIKey.objects.create_key(name="cli", user=self.user)
            headers["x-api-key"] = raw_key
        response = self.client.get("/packages/", headers=headers)
        self.assertEqual(200, response.status_code, response.content)
        return response.json()["results"][0]

    def test_list_packages_where_anonymous_and_asset_gated_should_report_none_with_request_url(self):
        # Arrange
        asset = self._gated_asset()

        # Act
        item = self._catalog_item(with_key=False)

        # Assert
        self.assertEqual("none", item["access"])
        self.assertEqual(f"https://cms.example/gallery/asset/{asset.pk}", item["access_request_url"])

    def test_list_packages_where_key_has_active_grant_should_report_granted(self):
        # Arrange
        self._grant(self._gated_asset())

        # Act
        item = self._catalog_item(with_key=True)

        # Assert
        self.assertEqual("granted", item["access"])

    def test_list_packages_where_grant_expired_should_report_none(self):
        # Arrange
        self._grant(self._gated_asset(), expires_at=timezone.now() - timedelta(days=1))

        # Act
        item = self._catalog_item(with_key=True)

        # Assert
        self.assertEqual("none", item["access"])

    def test_list_packages_where_latest_request_pending_should_report_pending(self):
        # Arrange
        asset = self._gated_asset()
        self._request(asset, AssetAccessRequest.StatusChoice.REJECTED)
        self._request(asset, AssetAccessRequest.StatusChoice.PENDING)

        # Act
        item = self._catalog_item(with_key=True)

        # Assert
        self.assertEqual("pending", item["access"])

    def test_list_packages_where_request_rejected_should_report_rejected(self):
        # Arrange
        self._request(self._gated_asset(), AssetAccessRequest.StatusChoice.REJECTED)

        # Act
        item = self._catalog_item(with_key=True)

        # Assert
        self.assertEqual("rejected", item["access"])

    def test_list_packages_where_another_user_has_grant_should_report_none(self):
        # Arrange
        asset = self._gated_asset()
        other = User.objects.create_user(email="other@example.com", name="Other")
        request = baker.make(
            AssetAccessRequest, developer_user=other, asset=asset, status=AssetAccessRequest.StatusChoice.APPROVED
        )
        baker.make(AssetAccess, asset_access_request=request, user=other, asset=asset)

        # Act
        item = self._catalog_item(with_key=True)

        # Assert
        self.assertEqual("none", item["access"])

    @override_settings(ENFORCE_ASSET_ACCESS_ON_PUBLIC_API=False)
    def test_list_packages_where_access_not_enforced_should_report_open(self):
        # Arrange
        self._gated_asset()

        # Act
        item = self._catalog_item(with_key=False)

        # Assert
        self.assertEqual("open", item["access"])


class PackageAccountTests(BaseTestCase):
    def test_get_package_account_where_valid_key_should_return_owner(self):
        # Arrange
        user = User.objects.create_user(email="dev@example.com", name="Dev")
        _, raw_key = APIKey.objects.create_key(name="cli", user=user)

        # Act
        response = self.client.get("/packages/me/", headers={"x-api-key": raw_key})

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual({"name": "Dev", "email": "dev@example.com"}, response.json())

    def test_get_package_account_where_no_key_should_return_401(self):
        # Arrange / Act
        response = self.client.get("/packages/me/")

        # Assert
        self.assertEqual(401, response.status_code, response.content)
        self.assertEqual("authentication_required", response.json()["error_name"])

    def test_get_package_account_where_key_is_invalid_should_return_401(self):
        # Arrange / Act
        response = self.client.get("/packages/me/", headers={"x-api-key": "not-a-key"})

        # Assert
        self.assertEqual(401, response.status_code, response.content)
        self.assertEqual("authentication_required", response.json()["error_name"])
