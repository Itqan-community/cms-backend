from django.core import mail
from model_bakery import baker

from apps.content.models import Asset, AssetAccess, AssetAccessRequest, Resource, ResourceVersion
from apps.content.services.resource import ResourceService
from apps.core.tests import BaseTestCase
from apps.users.models import User


class TestResourceService(BaseTestCase):
    def test_create_version_should_send_email_to_subscribed_users(self):
        # Arrange
        resource = baker.make(Resource, name="Test Resource")
        asset = baker.make(
            Asset,
            resource=resource,
            category="mushaf",
            reciter=None,
            riwayah=None,
            qiraah=None,
        )

        user1 = baker.make(User, email="user1@example.com")
        user2 = baker.make(User, email="user2@example.com")
        baker.make(User, email="user3@example.com")  # No access

        # Grant access to user1 and user2
        request1 = baker.make(AssetAccessRequest, developer_user=user1, asset=asset, status="approved")
        baker.make(AssetAccess, asset_access_request=request1, user=user1, asset=asset, effective_license="CC0")

        request2 = baker.make(AssetAccessRequest, developer_user=user2, asset=asset, status="approved")
        baker.make(AssetAccess, asset_access_request=request2, user=user2, asset=asset, effective_license="CC0")

        service = ResourceService()
        resource_version = ResourceVersion(resource=resource, semvar="1.1.0", summary="New version summary")

        # Act
        service.create_version(resource_version)

        # Assert
        self.assertIsNotNone(resource_version.pk)

        # Verify emails
        self.assertGreaterEqual(len(mail.outbox), 1)

        recipients = []
        for m in mail.outbox:
            recipients.extend(m.to)

        self.assertIn("user1@example.com", recipients)
        self.assertIn("user2@example.com", recipients)
        self.assertNotIn("user3@example.com", recipients)

        found = False
        for m in mail.outbox:
            if "New Update for Test Resource" in m.subject:
                found = True
                self.assertIn("1.1.0", m.body)
                self.assertIn("New version summary", m.body)
                break
        self.assertTrue(found)

    def test_create_version_no_email_if_no_subscribers(self):
        # Arrange
        resource = baker.make(Resource)
        # Create an asset explicitly to avoid issues, but no access grants
        baker.make(
            Asset,
            resource=resource,
            category="mushaf",
            reciter=None,
            riwayah=None,
            qiraah=None,
        )

        service = ResourceService()
        resource_version = ResourceVersion(resource=resource, semvar="1.1.0")

        # Act
        service.create_version(resource_version)

        # Assert
        self.assertEqual(len(mail.outbox), 0)
