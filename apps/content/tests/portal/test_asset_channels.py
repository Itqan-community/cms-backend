from model_bakery import baker

from apps.content.models import Asset, AssetAccessRequest, AssetTemplateChoice, CategoryChoice, StatusChoice
from apps.core.permissions import PermissionChoice
from apps.core.tests.base import BaseTestCase
from apps.publishers.models import Publisher
from apps.users.models import User

CHANNELS = ("in_gallery", "in_public_api", "in_cli", "in_tenants")

# category, URL prefix, update permission, extra asset kwargs
ASSET_TYPES = [
    (
        CategoryChoice.TEXT,
        "text-assets",
        PermissionChoice.PORTAL_UPDATE_TEXT_ASSET,
        {"template": AssetTemplateChoice.AYAH},
    ),
    (CategoryChoice.MUSHAF, "mushafs", PermissionChoice.PORTAL_UPDATE_MUSHAF, {}),
    (CategoryChoice.FONT, "fonts", PermissionChoice.PORTAL_UPDATE_FONT, {}),
]


class AssetChannelsPortalTests(BaseTestCase):
    """Channel flags + the channel_has_active_consumers guard on text assets, mushafs and fonts.

    Recitations (JSON API) are covered in portal/recitations/test_recitations.py.
    """

    def setUp(self):
        super().setUp()
        self.publisher = baker.make(Publisher)
        self.user = User.objects.create_user(email="channels@example.com", name="Channels", is_staff=True)

    def _asset(self, category, kwargs):
        return baker.make(
            Asset,
            category=category,
            publisher=self.publisher,
            status=StatusChoice.READY,
            license="CC0",
            language="ar",
            name_en="Channel asset",
            name="Channel asset",
            **kwargs,
        )

    def _consumer(self, asset, status=AssetAccessRequest.StatusChoice.APPROVED):
        AssetAccessRequest.objects.create(
            developer_user=baker.make(User),
            asset=asset,
            status=status,
            developer_access_reason="reason",
            intended_use=AssetAccessRequest.IntendedUseChoice.NON_COMMERCIAL,
        )

    def _patch(self, prefix, asset, data):
        return self.client.patch(f"/portal/{prefix}/{asset.slug}/", data=data, format="multipart")

    def test_patch_channels_where_flags_sent_should_round_trip_on_all_types(self):
        for category, prefix, permission, kwargs in ASSET_TYPES:
            with self.subTest(prefix):
                # Arrange
                self.authenticate_user(self.user)
                self.give_permission(self.user, permission)
                asset = self._asset(category, kwargs)

                # Act
                response = self._patch(prefix, asset, {"in_gallery": False, "in_tenants": False})

                # Assert
                self.assertEqual(200, response.status_code, response.content)
                body = response.json()
                self.assertEqual(
                    (False, True, True, False),
                    tuple(body[c] for c in CHANNELS),
                )
                asset.refresh_from_db()
                self.assertEqual((False, True, True, False), tuple(getattr(asset, c) for c in CHANNELS))

    def test_patch_channels_where_publisher_has_no_website_should_accept_in_tenants_on_all_types(self):
        # The "Publisher website" checkbox is hidden for publishers without a domain, but the API
        # still accepts and stores in_tenants as sent: no 4xx and no silent flip.
        self.assertFalse(self.publisher.domains.exists())
        for category, prefix, permission, kwargs in ASSET_TYPES:
            with self.subTest(prefix):
                # Arrange
                self.authenticate_user(self.user)
                self.give_permission(self.user, permission)
                asset = self._asset(category, kwargs)
                Asset.objects.filter(pk=asset.pk).update(in_tenants=False)

                # Act
                response = self._patch(prefix, asset, {"in_tenants": True})

                # Assert
                self.assertEqual(200, response.status_code, response.content)
                asset.refresh_from_db()
                self.assertTrue(asset.in_tenants)

    def test_put_channels_where_flags_omitted_should_default_to_true_on_all_types(self):
        for category, prefix, permission, kwargs in ASSET_TYPES:
            with self.subTest(prefix):
                # Arrange
                self.authenticate_user(self.user)
                self.give_permission(self.user, permission)
                asset = self._asset(category, kwargs)
                Asset.objects.filter(pk=asset.pk).update(in_cli=False)
                payload = {
                    "name_en": "Put name",
                    "license": "CC0",
                    "language": "ar",
                    "publisher_id": self.publisher.id,
                    "in_public_api": False,
                }

                # Act
                response = self.client.put(f"/portal/{prefix}/{asset.slug}/", data=payload, format="multipart")

                # Assert
                self.assertEqual(200, response.status_code, response.content)
                asset.refresh_from_db()
                self.assertEqual((True, False, True, True), tuple(getattr(asset, c) for c in CHANNELS))

    def test_patch_channels_where_turning_off_with_consumers_should_return_409_with_counts_on_all_types(self):
        for category, prefix, permission, kwargs in ASSET_TYPES:
            with self.subTest(prefix):
                # Arrange
                self.authenticate_user(self.user)
                self.give_permission(self.user, permission)
                asset = self._asset(category, kwargs)
                self._consumer(asset, AssetAccessRequest.StatusChoice.APPROVED)
                self._consumer(asset, AssetAccessRequest.StatusChoice.PENDING)

                # Act
                response = self._patch(prefix, asset, {"in_public_api": False, "in_cli": False})

                # Assert
                self.assertEqual(409, response.status_code, response.content)
                body = response.json()
                self.assertEqual("channel_has_active_consumers", body["error_name"])
                self.assertEqual(
                    {"approved_count": 1, "pending_count": 1, "channels": ["in_public_api", "in_cli"]},
                    body["extra"],
                )
                asset.refresh_from_db()
                self.assertTrue(asset.in_public_api)
                self.assertTrue(asset.in_cli)

    def test_patch_channels_where_confirmed_should_allow_turning_off_on_all_types(self):
        for category, prefix, permission, kwargs in ASSET_TYPES:
            with self.subTest(prefix):
                # Arrange
                self.authenticate_user(self.user)
                self.give_permission(self.user, permission)
                asset = self._asset(category, kwargs)
                self._consumer(asset)

                # Act
                response = self._patch(prefix, asset, {"in_gallery": False, "confirm_channel_change": True})

                # Assert
                self.assertEqual(200, response.status_code, response.content)
                asset.refresh_from_db()
                self.assertFalse(asset.in_gallery)

    def test_patch_channels_where_turning_on_with_consumers_should_not_need_confirm(self):
        for category, prefix, permission, kwargs in ASSET_TYPES:
            with self.subTest(prefix):
                # Arrange
                self.authenticate_user(self.user)
                self.give_permission(self.user, permission)
                asset = self._asset(category, kwargs)
                Asset.objects.filter(pk=asset.pk).update(in_gallery=False)
                self._consumer(asset)

                # Act
                response = self._patch(prefix, asset, {"in_gallery": True})

                # Assert
                self.assertEqual(200, response.status_code, response.content)
                asset.refresh_from_db()
                self.assertTrue(asset.in_gallery)

    def test_patch_channels_where_no_consumers_should_not_return_409(self):
        for category, prefix, permission, kwargs in ASSET_TYPES:
            with self.subTest(prefix):
                # Arrange
                self.authenticate_user(self.user)
                self.give_permission(self.user, permission)
                asset = self._asset(category, kwargs)
                self._consumer(asset, AssetAccessRequest.StatusChoice.REJECTED)

                # Act
                response = self._patch(prefix, asset, {"in_tenants": False})

                # Assert
                self.assertEqual(200, response.status_code, response.content)
                asset.refresh_from_db()
                self.assertFalse(asset.in_tenants)
