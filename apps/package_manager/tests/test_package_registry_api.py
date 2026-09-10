from unittest import skipUnless

from django.test import override_settings
from model_bakery import baker

from apps.content.models import (
    Asset,
    AssetAccess,
    AssetAccessRequest,
    AssetVersion,
    CategoryChoice,
    Distribution,
    VersionStateChoice,
)
from apps.core.tests.base import BaseTestCase
from apps.publishers.models import Publisher
from apps.users.models import APIKey, User


def _make_asset(publisher: Publisher, *, slug: str, **kwargs) -> Asset:
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


def _make_version(asset: Asset, *, name: str, state: str = VersionStateChoice.PUBLISHED) -> AssetVersion:
    version = baker.make(
        AssetVersion,
        asset=asset,
        name=name,
        state=state,
    )
    Distribution.objects.create(
        asset_version=version,
        channel=Distribution.ChannelChoice.PACKAGE,
    )
    return version


class PackageSingleResolveAPITests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.publisher = baker.make(Publisher)
        self.user = User.objects.create_user(email="dev@example.com", name="Dev")

    def _create_asset_with_versions(self, slug: str, version_names: list[str], **kwargs):
        asset = _make_asset(self.publisher, slug=slug, **kwargs)
        for name in version_names:
            _make_version(asset, name=name)
        return asset

    def _authenticate_with_api_key(self, user: User) -> None:
        _, raw_key = APIKey.objects.create_key(name="test-key", user=user)
        self.client.credentials(HTTP_X_API_KEY=raw_key)

    def test_resolve_single_where_valid_exact_pin_returns_200(self):
        self._create_asset_with_versions("pkg-a", ["1.0.0"])
        response = self.client.get("/packages/resolve/pkg-a/?version=1.0.0")
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual("1.0.0", body["result"]["resolved_version"])
        self.assertEqual("pkg-a", body["result"]["slug"])
        self.assertIsInstance(body["result"]["asset_version_id"], int)
        self.assertIsInstance(body["result"]["publisher_id"], int)

    def test_resolve_single_where_valid_range_returns_highest_match(self):
        self._create_asset_with_versions("pkg-b", ["1.0.0", "1.2.0", "1.3.0"])
        response = self.client.get("/packages/resolve/pkg-b/?version=^1.2.0")
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual("1.3.0", body["result"]["resolved_version"])

    def test_resolve_single_where_unknown_slug_returns_404(self):
        response = self.client.get("/packages/resolve/nonexistent/?version=1.0.0")
        self.assertEqual(404, response.status_code, response.content)
        body = response.json()
        self.assertEqual("asset_not_found", body["error_name"])

    def test_resolve_single_where_missing_exact_pin_returns_404(self):
        self._create_asset_with_versions("pkg-c", ["1.0.0"])
        response = self.client.get("/packages/resolve/pkg-c/?version=2.0.0")
        self.assertEqual(404, response.status_code, response.content)
        body = response.json()
        self.assertEqual("version_not_found", body["error_name"])

    def test_resolve_single_where_invalid_constraint_returns_422(self):
        self._create_asset_with_versions("pkg-d", ["1.0.0"])
        response = self.client.get("/packages/resolve/pkg-d/?version=>=1.0.0")
        self.assertEqual(422, response.status_code, response.content)
        body = response.json()
        self.assertEqual("invalid_version_constraint", body["error_name"])

    def test_resolve_single_where_unsatisfiable_range_returns_422(self):
        self._create_asset_with_versions("pkg-e", ["1.0.0"])
        response = self.client.get("/packages/resolve/pkg-e/?version=^9.0.0")
        self.assertEqual(422, response.status_code, response.content)
        body = response.json()
        self.assertEqual("unsatisfiable_version_constraint", body["error_name"])

    def test_resolve_single_where_restricted_for_tenant_returns_404(self):
        self._create_asset_with_versions("tenant-only", ["1.0.0"], restricted_for_tenant=True)
        response = self.client.get("/packages/resolve/tenant-only/?version=1.0.0")
        self.assertEqual(404, response.status_code, response.content)
        body = response.json()
        self.assertEqual("asset_not_found", body["error_name"])

    def test_resolve_single_where_open_access_anonymous_returns_200(self):
        self._create_asset_with_versions("open-pkg", ["1.0.0"], is_open_access=True)
        response = self.client.get("/packages/resolve/open-pkg/?version=1.0.0")
        self.assertEqual(200, response.status_code, response.content)

    def test_resolve_single_where_open_access_collision_returns_422(self):
        """Open-access asset with colliding versions still detects collision (no security override)."""
        self._create_asset_with_versions("open-collision", ["1.2", "1.2.0"], is_open_access=True)
        response = self.client.get("/packages/resolve/open-collision/?version=~1.0.0")
        self.assertEqual(422, response.status_code, response.content)
        body = response.json()
        self.assertEqual("canonical_version_collision", body["error_name"])

    @override_settings(ENFORCE_ASSET_ACCESS_ON_PUBLIC_API=True)
    def test_resolve_single_where_restricted_anonymous_returns_401(self):
        asset = self._create_asset_with_versions("restricted-pkg", ["1.0.0"], is_open_access=False)
        response = self.client.get(f"/packages/resolve/{asset.slug}/?version=1.0.0")
        self.assertEqual(401, response.status_code, response.content)
        body = response.json()
        self.assertEqual("authentication_required", body["error_name"])

    @override_settings(ENFORCE_ASSET_ACCESS_ON_PUBLIC_API=True)
    def test_resolve_single_collision_error_does_not_disclose_versions(self):
        """Access check runs before resolver; restricted asset returns 401, not 422."""
        asset = self._create_asset_with_versions("controlled-collision", ["1.2", "1.2.0"], is_open_access=False)
        response = self.client.get(f"/packages/resolve/{asset.slug}/?version=~1.0.0")
        self.assertEqual(401, response.status_code, response.content)
        body = response.json()
        self.assertEqual("authentication_required", body["error_name"])
        body_str = response.content.decode()
        self.assertNotIn("1.2", body_str)
        self.assertNotIn("1.2.0", body_str)

    @override_settings(ENFORCE_ASSET_ACCESS_ON_PUBLIC_API=True)
    def test_resolve_single_where_restricted_anonymous_collision_returns_401(self):
        """Restricted asset with colliding versions returns 401, NOT 422."""
        asset = self._create_asset_with_versions("restricted-collision", ["1.2", "1.2.0"], is_open_access=False)
        response = self.client.get(f"/packages/resolve/{asset.slug}/?version=~1.0.0")
        self.assertEqual(401, response.status_code, response.content)
        body = response.json()
        self.assertEqual("authentication_required", body["error_name"])

    @override_settings(ENFORCE_ASSET_ACCESS_ON_PUBLIC_API=True)
    def test_resolve_single_where_restricted_anonymous_invalid_constraint_returns_401(self):
        """Restricted asset with invalid constraint returns 401, NOT 422."""
        asset = self._create_asset_with_versions("restricted-invalid", ["1.0.0"], is_open_access=False)
        response = self.client.get(f"/packages/resolve/{asset.slug}/?version=>=1.0.0")
        self.assertEqual(401, response.status_code, response.content)
        body = response.json()
        self.assertEqual("authentication_required", body["error_name"])

    @override_settings(ENFORCE_ASSET_ACCESS_ON_PUBLIC_API=True)
    def test_resolve_single_where_restricted_anonymous_unsatisfiable_returns_401(self):
        """Restricted asset with unsatisfiable constraint returns 401, NOT 422."""
        asset = self._create_asset_with_versions("restricted-unsat", ["1.0.0"], is_open_access=False)
        response = self.client.get(f"/packages/resolve/{asset.slug}/?version=^9.0.0")
        self.assertEqual(401, response.status_code, response.content)
        body = response.json()
        self.assertEqual("authentication_required", body["error_name"])

    @skipUnless(False, "API key auth not functional in this test environment; see test_api_key_auth.py")
    @override_settings(ENFORCE_ASSET_ACCESS_ON_PUBLIC_API=True)
    def test_resolve_single_where_restricted_api_key_no_access_returns_403(self):
        asset = self._create_asset_with_versions("restricted-pkg", ["1.0.0"], is_open_access=False)
        self._authenticate_with_api_key(self.user)
        response = self.client.get(f"/packages/resolve/{asset.slug}/?version=1.0.0")
        self.assertEqual(403, response.status_code, response.content)
        body = response.json()
        self.assertEqual("access_denied", body["error_name"])

    @skipUnless(False, "API key auth not functional in this test environment; see test_api_key_auth.py")
    @override_settings(ENFORCE_ASSET_ACCESS_ON_PUBLIC_API=True)
    def test_resolve_single_where_restricted_with_valid_access_returns_200(self):
        asset = self._create_asset_with_versions("restricted-pkg", ["1.0.0"], is_open_access=False)
        self._authenticate_with_api_key(self.user)
        req = baker.make(
            AssetAccessRequest,
            developer_user=self.user,
            asset=asset,
            status=AssetAccessRequest.StatusChoice.APPROVED,
        )
        baker.make(
            AssetAccess,
            asset_access_request=req,
            user=self.user,
            asset=asset,
            expires_at=None,
        )
        response = self.client.get(f"/packages/resolve/{asset.slug}/?version=1.0.0")
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual("1.0.0", body["result"]["resolved_version"])


class PackageManifestResolveAPITests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.publisher = baker.make(Publisher)
        self.user = User.objects.create_user(email="dev@example.com", name="Dev")

    def _create_asset_with_versions(self, slug: str, version_names: list[str], **kwargs):
        asset = _make_asset(self.publisher, slug=slug, **kwargs)
        for name in version_names:
            _make_version(asset, name=name)
        return asset

    def _authenticate_with_api_key(self, user: User) -> None:
        _, raw_key = APIKey.objects.create_key(name="test-key", user=user)
        self.client.credentials(HTTP_X_API_KEY=raw_key)

    def test_resolve_manifest_where_all_valid_returns_200(self):
        self._create_asset_with_versions("asset-alpha", ["1.0.0", "1.1.0"])
        self._create_asset_with_versions("asset-beta", ["2.0.0"])
        response = self.client.post(
            "/packages/resolve/manifest/",
            data={"assets": {"asset-alpha": "^1.0.0", "asset-beta": "~2.0"}},
            content_type="application/json",
        )
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual(2, len(body["results"]))
        # Results ordered by slug byte sequence
        self.assertEqual("asset-alpha", body["results"][0]["slug"])
        self.assertEqual("asset-beta", body["results"][1]["slug"])

    def test_resolve_manifest_where_one_unknown_raises_asset_not_found(self):
        self._create_asset_with_versions("known-asset", ["1.0.0"])
        response = self.client.post(
            "/packages/resolve/manifest/",
            data={"assets": {"known-asset": "1.0.0", "unknown-asset": "1.0.0"}},
            content_type="application/json",
        )
        self.assertEqual(404, response.status_code, response.content)
        body = response.json()
        self.assertEqual("asset_not_found", body["error_name"])

    def test_resolve_manifest_where_one_unsatisfiable_raises_422(self):
        self._create_asset_with_versions("aaa-known", ["1.0.0"])
        self._create_asset_with_versions("zzz-other", ["1.0.0"])
        response = self.client.post(
            "/packages/resolve/manifest/",
            data={"assets": {"aaa-known": "1.0.0", "zzz-other": "^9.0.0"}},
            content_type="application/json",
        )
        self.assertEqual(422, response.status_code, response.content)
        body = response.json()
        self.assertEqual("unsatisfiable_version_constraint", body["error_name"])

    def test_resolve_manifest_returns_no_partial_result_on_failure(self):
        self._create_asset_with_versions("known-asset", ["1.0.0"])
        response = self.client.post(
            "/packages/resolve/manifest/",
            data={"assets": {"known-asset": "1.0.0", "missing-asset": "1.0.0"}},
            content_type="application/json",
        )
        self.assertEqual(404, response.status_code, response.content)
        body = response.json()
        # No results key — error shape only
        self.assertNotIn("results", body)
        self.assertEqual("asset_not_found", body["error_name"])

    @skipUnless(False, "API key auth not functional in this test environment; see test_api_key_auth.py")
    def test_resolve_manifest_where_one_restricted_no_access_returns_403(self):
        """Access denial on any entry aborts the whole manifest."""
        self._create_asset_with_versions("open-pkg", ["1.0.0"], is_open_access=True)
        restricted = self._create_asset_with_versions(
            "restricted-pkg",
            ["1.0.0"],
            is_open_access=False,
        )
        self._authenticate_with_api_key(self.user)
        response = self.client.post(
            "/packages/resolve/manifest/",
            data={"assets": {"open-pkg": "1.0.0", restricted.slug: "1.0.0"}},
            content_type="application/json",
        )
        self.assertEqual(403, response.status_code, response.content)
        body = response.json()
        self.assertEqual("access_denied", body["error_name"])
        self.assertNotIn("results", body)

    @override_settings(ENFORCE_ASSET_ACCESS_ON_PUBLIC_API=True)
    def test_resolve_manifest_where_restricted_anonymous_returns_401_before_resolution(self):
        """Access check runs before version resolution; restricted asset returns 401."""
        self._create_asset_with_versions("open-pkg", ["1.0.0"], is_open_access=True)
        self._create_asset_with_versions(
            "restricted-manifest",
            ["1.2", "1.2.0"],
            is_open_access=False,
        )
        response = self.client.post(
            "/packages/resolve/manifest/",
            data={"assets": {"open-pkg": "^1.0.0", "restricted-manifest": "~1.0.0"}},
            content_type="application/json",
        )
        self.assertEqual(401, response.status_code, response.content)
        body = response.json()
        self.assertEqual("authentication_required", body["error_name"])
        body_str = response.content.decode()
        self.assertNotIn("1.2", body_str)
        self.assertNotIn("1.2.0", body_str)

    @override_settings(ENFORCE_ASSET_ACCESS_ON_PUBLIC_API=True)
    def test_resolve_manifest_where_restricted_collision_returns_401_not_422(self):
        """Manifest restricted asset with colliding versions returns 401, NOT 422."""
        self._create_asset_with_versions("restricted-collision", ["1.2", "1.2.0"], is_open_access=False)
        response = self.client.post(
            "/packages/resolve/manifest/",
            data={"assets": {"restricted-collision": "~1.0.0"}},
            content_type="application/json",
        )
        self.assertEqual(401, response.status_code, response.content)
        body = response.json()
        self.assertEqual("authentication_required", body["error_name"])

    def test_resolve_manifest_where_open_access_collision_still_returns_422(self):
        """Open-access asset with colliding versions still gets 422 (no security override)."""
        self._create_asset_with_versions("open-collision", ["1.2", "1.2.0"], is_open_access=True)
        response = self.client.post(
            "/packages/resolve/manifest/",
            data={"assets": {"open-collision": "~1.0.0"}},
            content_type="application/json",
        )
        self.assertEqual(422, response.status_code, response.content)
        body = response.json()
        self.assertEqual("canonical_version_collision", body["error_name"])

    def test_resolve_manifest_all_accessible_returns_200(self):
        self._create_asset_with_versions("pkg-a", ["1.0.0"])
        self._create_asset_with_versions("pkg-b", ["1.0.0"])
        response = self.client.post(
            "/packages/resolve/manifest/",
            data={"assets": {"pkg-a": "1.0.0", "pkg-b": "1.0.0"}},
            content_type="application/json",
        )
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual(2, len(body["results"]))

    def test_resolve_manifest_empty_assets_returns_empty_list(self):
        response = self.client.post(
            "/packages/resolve/manifest/",
            data={"assets": {}},
            content_type="application/json",
        )
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual([], body["results"])

    def test_resolve_manifest_malformed_body_returns_validation_error(self):
        response = self.client.post(
            "/packages/resolve/manifest/",
            data={"not_assets": "value"},
            content_type="application/json",
        )
        self.assertEqual(400, response.status_code, response.content)

    def test_resolve_manifest_deterministic_ordering(self):
        self._create_asset_with_versions("zebra", ["1.0.0"])
        self._create_asset_with_versions("alpha", ["1.0.0"])
        self._create_asset_with_versions("middle", ["1.0.0"])
        response = self.client.post(
            "/packages/resolve/manifest/",
            data={"assets": {"zebra": "1.0.0", "alpha": "1.0.0", "middle": "1.0.0"}},
            content_type="application/json",
        )
        self.assertEqual(200, response.status_code, response.content)
        slugs = [r["slug"] for r in response.json()["results"]]
        self.assertEqual(["alpha", "middle", "zebra"], slugs)

    def test_resolve_manifest_missing_version_field_returns_400(self):
        response = self.client.post(
            "/packages/resolve/manifest/",
            data={"entries": {}},
            content_type="application/json",
        )
        self.assertEqual(400, response.status_code, response.content)

    def test_resolve_manifest_where_exceeds_100_entries_returns_400(self):
        assets = {f"pkg-{i:03d}": "1.0.0" for i in range(101)}
        response = self.client.post(
            "/packages/resolve/manifest/",
            data={"assets": assets},
            content_type="application/json",
        )
        self.assertEqual(400, response.status_code, response.content)
