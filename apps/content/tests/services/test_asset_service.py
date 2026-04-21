from django.core import mail
from model_bakery import baker

from apps.content.models import Asset, AssetAccess, AssetAccessRequest, AssetVersion
from apps.content.services.asset import AssetService
from apps.core.tests import BaseTestCase
from apps.users.models import User


class TestAssetService(BaseTestCase):
    def test_create_version_when_there_are_subscribed_users_should_send_email(self):
        # Arrange
        asset = baker.make(
            Asset,
            name="Test Asset",
            category="mushaf",
            reciter=None,
            riwayah=None,
            qiraah=None,
        )

        user1 = baker.make(User, email="user1@example.com")

        # Grant access to user1
        request = baker.make(AssetAccessRequest, developer_user=user1, asset=asset, status="approved")
        baker.make(AssetAccess, asset_access_request=request, user=user1, asset=asset, effective_license="CC0")

        service = AssetService()
        asset_version = AssetVersion(
            asset=asset,
            name="1.0.0",
            summary="Asset update summary",
        )

        # Act
        service.create_version(asset_version)

        # Assert
        self.assertIsNotNone(asset_version.pk)
        self.assertGreaterEqual(len(mail.outbox), 1)

        recipients = []
        for m in mail.outbox:
            recipients.extend(m.to)

        self.assertIn("user1@example.com", recipients)

        found = False
        for m in mail.outbox:
            if "New Update for Test Asset" in m.subject:
                found = True
                self.assertIn("1.0.0", m.body)
                self.assertIn("Asset update summary", m.body)
                break
        self.assertTrue(found)

    def test_create_version_when_no_subscribers_should_not_send_emails(self):
        # Arrange
        asset = baker.make(
            Asset,
            category="mushaf",
            reciter=None,
            riwayah=None,
            qiraah=None,
        )

        service = AssetService()
        asset_version = AssetVersion(asset=asset, name="Asset V1")

        # Act
        service.create_version(asset_version)

        # Assert
        self.assertEqual(len(mail.outbox), 0)
