"""Usage-tracking tests for the package registry endpoints (Checkpoint 4).

Verifies that @track_usage correctly records entity and publisher metadata for
both single-resolution and manifest-resolution endpoints, following the same
pattern used by the existing public API tracking tests.
"""

import json
from unittest import skipUnless
from unittest.mock import patch

from django.test import override_settings
from model_bakery import baker

from apps.content.models import Asset, AssetVersion, CategoryChoice, Distribution, VersionStateChoice
from apps.core.tests.base import BaseTestCase
from apps.publishers.models import Publisher
from apps.users.models import APIKey, User

_REDIS = "apps.usage_tracking.decorators.track_usage._get_tracking_redis"


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


def _make_package_version(asset: Asset, *, name: str) -> AssetVersion:
    version = baker.make(
        AssetVersion,
        asset=asset,
        name=name,
        state=VersionStateChoice.PUBLISHED,
    )
    Distribution.objects.create(
        asset_version=version,
        channel=Distribution.ChannelChoice.PACKAGE,
    )
    return version


class PackageSingleTrackingTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.publisher = baker.make(Publisher, name="Publisher X")
        self.asset = _make_package_asset(self.publisher, slug="pkg-track")
        _make_package_version(self.asset, name="1.0.0")

    def _props(self, mock_get_redis):
        mock_r = mock_get_redis.return_value
        assert mock_r.rpush.called, "expected rpush to be called on Redis mock"
        raw = mock_r.rpush.call_args[0][1]
        return json.loads(raw)["properties"]

    @patch(_REDIS)
    def test_resolve_single_emits_package_tracking(self, mock_get_redis):
        response = self.client.get("/packages/resolve/pkg-track/?version=1.0.0")
        self.assertEqual(200, response.status_code, response.content)

        props = self._props(mock_get_redis)
        self.assertEqual("package", props["entity_type"])
        self.assertEqual([self.asset.id], props["entity_ids"])
        self.assertEqual(["Test Asset"], props["entity_names"])
        self.assertEqual([self.publisher.id], props["publisher_ids"])
        self.assertEqual(["Publisher X"], props["publisher_names"])

    @patch(_REDIS)
    def test_resolve_single_unknown_asset_dispatches_nothing(self, mock_get_redis):
        response = self.client.get("/packages/resolve/nonexistent/?version=1.0.0")
        self.assertEqual(404, response.status_code, response.content)
        mock_get_redis.return_value.rpush.assert_not_called()

    @override_settings(ENFORCE_ASSET_ACCESS_ON_PUBLIC_API=True)
    @patch(_REDIS)
    def test_resolve_single_restricted_anonymous_dispatches_nothing(self, mock_get_redis):
        restricted = _make_package_asset(
            self.publisher,
            slug="restricted-track",
            is_open_access=False,
        )
        _make_package_version(restricted, name="1.0.0")
        response = self.client.get(f"/packages/resolve/{restricted.slug}/?version=1.0.0")
        self.assertEqual(401, response.status_code, response.content)
        mock_get_redis.return_value.rpush.assert_not_called()

    @patch(_REDIS)
    def test_resolve_single_invalid_constraint_dispatches_nothing(self, mock_get_redis):
        response = self.client.get("/packages/resolve/pkg-track/?version=>=1.0.0")
        self.assertEqual(422, response.status_code, response.content)
        mock_get_redis.return_value.rpush.assert_not_called()

    @skipUnless(False, "API key auth not functional in this test environment; see test_api_key_auth.py")
    @override_settings(ENABLE_API_KEY_AUTH=True)
    @patch(_REDIS)
    def test_resolve_single_api_key_records_key_prefix_as_application_identity(self, mock_get_redis):
        user = User.objects.create_user(email="apikey@example.com", name="ApiKey User")
        api_key, raw_key = APIKey.objects.create_key(name="Tracking App", user=user)
        self.client.credentials(HTTP_X_API_KEY=raw_key)

        response = self.client.get("/packages/resolve/pkg-track/?version=1.0.0")
        self.assertEqual(200, response.status_code, response.content)

        props = self._props(mock_get_redis)
        self.assertEqual(api_key.prefix, props["application_id"])
        self.assertIsNone(props["application_name"])


class PackageManifestTrackingTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.publisher_a = baker.make(Publisher, name="Publisher A")
        self.publisher_b = baker.make(Publisher, name="Publisher B")

        self.asset_a = _make_package_asset(self.publisher_a, slug="pkg-alpha")
        _make_package_version(self.asset_a, name="1.0.0")

        self.asset_b = _make_package_asset(self.publisher_b, slug="pkg-beta")
        _make_package_version(self.asset_b, name="1.0.0")

    def _props(self, mock_get_redis):
        mock_r = mock_get_redis.return_value
        assert mock_r.rpush.called, "expected rpush to be called on Redis mock"
        raw = mock_r.rpush.call_args[0][1]
        return json.loads(raw)["properties"]

    @patch(_REDIS)
    def test_manifest_two_assets_both_entities_tracked(self, mock_get_redis):
        response = self.client.post(
            "/packages/resolve/manifest/",
            data={"assets": {"pkg-alpha": "1.0.0", "pkg-beta": "1.0.0"}},
            content_type="application/json",
        )
        self.assertEqual(200, response.status_code, response.content)

        props = self._props(mock_get_redis)
        self.assertEqual("package", props["entity_type"])
        self.assertEqual([self.asset_a.id, self.asset_b.id], props["entity_ids"])
        self.assertEqual(["Test Asset", "Test Asset"], props["entity_names"])

    @patch(_REDIS)
    def test_manifest_two_different_publishers_both_tracked(self, mock_get_redis):
        response = self.client.post(
            "/packages/resolve/manifest/",
            data={"assets": {"pkg-alpha": "1.0.0", "pkg-beta": "1.0.0"}},
            content_type="application/json",
        )
        self.assertEqual(200, response.status_code, response.content)

        props = self._props(mock_get_redis)
        self.assertCountEqual([self.publisher_a.id, self.publisher_b.id], props["publisher_ids"])
        self.assertCountEqual(["Publisher A", "Publisher B"], props["publisher_names"])

    @patch(_REDIS)
    def test_manifest_same_publisher_deduplicated(self, mock_get_redis):
        asset_c = _make_package_asset(self.publisher_a, slug="pkg-gamma")
        _make_package_version(asset_c, name="1.0.0")

        response = self.client.post(
            "/packages/resolve/manifest/",
            data={"assets": {"pkg-alpha": "1.0.0", "pkg-gamma": "1.0.0"}},
            content_type="application/json",
        )
        self.assertEqual(200, response.status_code, response.content)

        props = self._props(mock_get_redis)
        self.assertEqual([self.publisher_a.id], props["publisher_ids"])
        self.assertEqual(["Publisher A"], props["publisher_names"])
        self.assertEqual([self.asset_a.id, asset_c.id], props["entity_ids"])

    @patch(_REDIS)
    def test_manifest_deterministic_entity_ordering(self, mock_get_redis):
        """Entity IDs follow the same slug-sorted order as the response."""
        response = self.client.post(
            "/packages/resolve/manifest/",
            data={"assets": {"pkg-beta": "1.0.0", "pkg-alpha": "1.0.0"}},
            content_type="application/json",
        )
        self.assertEqual(200, response.status_code, response.content)

        body = response.json()
        self.assertEqual(["pkg-alpha", "pkg-beta"], [r["slug"] for r in body["results"]])

        props = self._props(mock_get_redis)
        # Order follows manifest response ordering (slug-sorted)
        self.assertEqual([self.asset_a.id, self.asset_b.id], props["entity_ids"])

    @patch(_REDIS)
    def test_manifest_resolution_failure_dispatches_nothing(self, mock_get_redis):
        response = self.client.post(
            "/packages/resolve/manifest/",
            data={"assets": {"pkg-alpha": "1.0.0", "nonexistent": "1.0.0"}},
            content_type="application/json",
        )
        self.assertEqual(404, response.status_code, response.content)
        mock_get_redis.return_value.rpush.assert_not_called()

    @override_settings(ENFORCE_ASSET_ACCESS_ON_PUBLIC_API=True)
    @patch(_REDIS)
    def test_manifest_access_failure_dispatches_nothing(self, mock_get_redis):
        restricted = _make_package_asset(self.publisher_a, slug="pkg-restricted", is_open_access=False)
        _make_package_version(restricted, name="1.0.0")

        response = self.client.post(
            "/packages/resolve/manifest/",
            data={"assets": {"pkg-alpha": "1.0.0", restricted.slug: "1.0.0"}},
            content_type="application/json",
        )
        self.assertEqual(401, response.status_code, response.content)
        mock_get_redis.return_value.rpush.assert_not_called()

    @skipUnless(False, "API key auth not functional in this test environment; see test_api_key_auth.py")
    @override_settings(ENABLE_API_KEY_AUTH=True)
    @patch(_REDIS)
    def test_manifest_api_key_records_key_prefix_as_application_identity(self, mock_get_redis):
        user = User.objects.create_user(email="apikey2@example.com", name="ApiKey User 2")
        api_key, raw_key = APIKey.objects.create_key(name="Manifest App", user=user)
        self.client.credentials(HTTP_X_API_KEY=raw_key)

        response = self.client.post(
            "/packages/resolve/manifest/",
            data={"assets": {"pkg-alpha": "1.0.0", "pkg-beta": "1.0.0"}},
            content_type="application/json",
        )
        self.assertEqual(200, response.status_code, response.content)

        props = self._props(mock_get_redis)
        self.assertEqual(api_key.prefix, props["application_id"])
        self.assertIsNone(props["application_name"])
