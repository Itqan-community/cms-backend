from django.core import mail
from model_bakery import baker

from apps.content.models import Asset, AssetAccess, AssetAccessRequest, AssetVersion
from apps.content.services.asset_version_notifier import AssetVersionNotifier
from apps.core.tests.base import BaseTestCase
from apps.users.models import User


class TestAssetVersionNotifier(BaseTestCase):
    def test_notify_new_version_with_subscribers_should_send_email(self):
        # Arrange
        asset = baker.make(Asset, name="Test Asset", category="mushaf", reciter=None, riwayah=None, qiraah=None)
        user = baker.make(User, email="subscriber@example.com")
        request = baker.make(AssetAccessRequest, developer_user=user, asset=asset, status="approved")
        baker.make(AssetAccess, asset_access_request=request, user=user, asset=asset, effective_license="CC0")
        baker.make(AssetVersion, asset=asset, name="1.0.0")  # prior version so this is an update
        version = baker.make(AssetVersion, asset=asset, name="2.0.0", summary="Major update")

        # Act
        AssetVersionNotifier().notify_new_version(version.pk)

        # Assert
        self.assertGreaterEqual(len(mail.outbox), 1)
        recipients = [email for m in mail.outbox for email in m.to]
        self.assertIn("subscriber@example.com", recipients)
        found = any("New Update for Test Asset" in m.subject for m in mail.outbox)
        self.assertTrue(found)

    def test_notify_new_version_without_subscribers_should_not_send_email(self):
        # Arrange
        asset = baker.make(Asset, category="mushaf", reciter=None, riwayah=None, qiraah=None)
        baker.make(AssetVersion, asset=asset, name="1.0.0")  # prior version
        version = baker.make(AssetVersion, asset=asset, name="2.0.0")

        # Act
        AssetVersionNotifier().notify_new_version(version.pk)

        # Assert
        self.assertEqual(len(mail.outbox), 0)

    def test_notify_first_version_should_not_send_email(self):
        # Arrange — no prior versions exist; this is the initial publish
        asset = baker.make(Asset, name="Test Asset", category="mushaf", reciter=None, riwayah=None, qiraah=None)
        user = baker.make(User, email="subscriber@example.com")
        request = baker.make(AssetAccessRequest, developer_user=user, asset=asset, status="approved")
        baker.make(AssetAccess, asset_access_request=request, user=user, asset=asset, effective_license="CC0")
        version = baker.make(AssetVersion, asset=asset, name="1.0.0")

        # Act
        AssetVersionNotifier().notify_new_version(version.pk)

        # Assert
        self.assertEqual(len(mail.outbox), 0)

    def test_notify_new_version_with_invalid_id_should_skip_gracefully(self):
        # Act — no exception expected
        AssetVersionNotifier().notify_new_version(asset_version_id=999999)

        # Assert
        self.assertEqual(len(mail.outbox), 0)
