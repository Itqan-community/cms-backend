"""Download reference tests for the package registry endpoints (Checkpoint 5).

Verifies that the `download_url` field on PackageVersionOut correctly exposes
the existing AssetVersion.file_url after access checks pass, and returns null
when no file is present.
"""

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from model_bakery import baker

from apps.content.models import (
    Asset,
    AssetVersion,
    CategoryChoice,
    Distribution,
    VersionStateChoice,
)
from apps.core.tests.base import BaseTestCase
from apps.publishers.models import Publisher
from apps.users.models import User


def _make_package_asset(publisher: Publisher, *, slug: str, **kwargs) -> Asset:
    return Asset.objects.create(
        name="Test Asset",
        slug=slug,
        publisher=publisher,
        category=CategoryChoice.MUSHAF,
        license="CC0",
        file_size="1 MB",
        format="pdf",
        description="desc",
        language="en",
        **kwargs,
    )


def _make_version_with_file(
    asset: Asset, *, name: str, has_file: bool = True, filename: str = "file.pdf"
) -> AssetVersion:
    version = baker.make(
        AssetVersion,
        asset=asset,
        name=name,
        state=VersionStateChoice.PUBLISHED,
    )
    if has_file:
        version.file_url = SimpleUploadedFile(name=filename, content=b"dummy")
        version.save()
    Distribution.objects.create(
        asset_version=version,
        channel=Distribution.ChannelChoice.PACKAGE,
    )
    return version


class PackageDownloadUrlTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.publisher = baker.make(Publisher)
        self.user = User.objects.create_user(email="dev@example.com", name="Dev")

    def _create_asset_with_version(self, slug: str, version_name: str, *, has_file: bool = True):
        asset = _make_package_asset(self.publisher, slug=slug)
        version = _make_version_with_file(asset, name=version_name, has_file=has_file, filename=f"{slug}.pdf")
        return asset, version

    def test_single_asset_with_file_url_returns_download_reference(self):
        asset, version = self._create_asset_with_version("pkg-with-file", "1.0.0", has_file=True)
        response = self.client.get("/packages/resolve/pkg-with-file/?version=1.0.0")
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertIsNotNone(body["result"]["download_url"])
        self.assertEqual(version.pk, body["result"]["asset_version_id"])

    def test_single_asset_without_file_url_returns_null(self):
        asset, version = self._create_asset_with_version("pkg-no-file", "1.0.0", has_file=False)
        response = self.client.get("/packages/resolve/pkg-no-file/?version=1.0.0")
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertIsNone(body["result"]["download_url"])
        self.assertEqual(version.pk, body["result"]["asset_version_id"])

    def test_single_asset_download_url_uses_project_storage_behavior(self):
        """The download_url must be the actual FileField URL, not a fabricated path."""
        asset, version = self._create_asset_with_version("pkg-verify-url", "1.0.0", has_file=True)
        response = self.client.get("/packages/resolve/pkg-verify-url/?version=1.0.0")
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        # Must be the real FileField URL — matches what Django/storage produces,
        # not a made-up "/packages/..." prefix.
        url = body["result"]["download_url"]
        self.assertTrue(url.startswith("/media/"), f"unexpected URL format: {url}")

    def test_manifest_mixed_file_and_no_file_returns_correct_references(self):
        asset_a, version_a = self._create_asset_with_version("pkg-has-file", "1.0.0", has_file=True)
        asset_b, version_b = self._create_asset_with_version("pkg-no-file", "1.0.0", has_file=False)

        response = self.client.post(
            "/packages/resolve/manifest/",
            data={"assets": {"pkg-has-file": "1.0.0", "pkg-no-file": "1.0.0"}},
            content_type="application/json",
        )
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual(2, len(body["results"]))
        by_slug = {r["slug"]: r for r in body["results"]}
        self.assertIsNotNone(by_slug["pkg-has-file"]["download_url"])
        self.assertIsNone(by_slug["pkg-no-file"]["download_url"])

    @override_settings(ENFORCE_ASSET_ACCESS_ON_PUBLIC_API=True)
    def test_restricted_asset_returns_no_download_url_in_response(self):
        asset, version = self._create_asset_with_version("restricted-pkg", "1.0.0", has_file=True)
        asset.is_open_access = False
        asset.save()
        response = self.client.get(f"/packages/resolve/{asset.slug}/?version=1.0.0")
        self.assertEqual(401, response.status_code, response.content)
        body = response.json()
        self.assertNotIn("result", body)
        self.assertNotIn("download_url", str(body))

    @override_settings(ENFORCE_ASSET_ACCESS_ON_PUBLIC_API=True)
    def test_manifest_with_one_restricted_item_returns_no_partial_result(self):
        asset_a, version_a = self._create_asset_with_version("open-pkg", "1.0.0", has_file=True)
        asset_b, version_b = self._create_asset_with_version("restricted-pkg", "1.0.0", has_file=True)
        asset_b.is_open_access = False
        asset_b.save()

        response = self.client.post(
            "/packages/resolve/manifest/",
            data={"assets": {"open-pkg": "1.0.0", asset_b.slug: "1.0.0"}},
            content_type="application/json",
        )
        self.assertEqual(401, response.status_code, response.content)
        body = response.json()
        self.assertNotIn("results", body)
        self.assertNotIn("download_url", str(body))
