from unittest.mock import patch

from model_bakery import baker

from apps.content.models import Asset, AssetAccess, AssetAccessRequest, CategoryChoice, LicenseChoice, UsageEvent
from apps.content.services.usage import create_usage_event, log_api_access, log_asset_download, log_asset_view
from apps.content.tasks import create_usage_event_task
from apps.core.tests.base import BaseTestCase
from apps.publishers.models import Publisher
from apps.users.models import User


class TestUsageService(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.user = baker.make(User)
        self.publisher = baker.make(Publisher)
        self.asset = baker.make(
            Asset,
            publisher=self.publisher,
            name="Holy Quran Tafsir",
            category=CategoryChoice.TAFSIR,
            file_size="15.5 MB",
            format="mp3",
            license=LicenseChoice.CC_BY,
        )
        self.asset_access_request = baker.make(
            AssetAccessRequest,
            developer_user=self.user,
            asset=self.asset,
        )
        self.asset_access = baker.make(
            AssetAccess,
            asset_access_request=self.asset_access_request,
            user=self.user,
            asset=self.asset,
            effective_license=LicenseChoice.CC_BY,
        )

    def test_create_usage_event_where_asset_access_is_provided_should_persist_expected_event(self):
        # Arrange
        ip_address = "127.0.0.1"
        user_agent = "TestAgent/1.0"

        # Act
        result = create_usage_event(
            asset_access=self.asset_access,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        # Assert
        usage_event = UsageEvent.objects.get()
        self.assertEqual(result, usage_event)
        self.assertEqual(usage_event.developer_user, self.user)
        self.assertEqual(usage_event.usage_kind, UsageEvent.UsageKindChoice.FILE_DOWNLOAD)
        self.assertEqual(usage_event.asset_id, self.asset.id)
        self.assertEqual(
            usage_event.metadata,
            {
                "asset_name": self.asset.name,
                "asset_title": self.asset.name,
                "file_size": self.asset.file_size,
                "format": self.asset.format,
                "license": self.asset_access.effective_license,
                "access_id": self.asset_access.id,
            },
        )
        self.assertEqual(usage_event.ip_address, ip_address)
        self.assertEqual(usage_event.user_agent, user_agent)

    def test_log_asset_view_where_asset_is_provided_should_persist_view_event_with_asset_name(self):
        # Arrange
        ip_address = "192.168.1.1"
        user_agent = "Mozilla/5.0"

        # Act
        result = log_asset_view(
            user=self.user,
            asset=self.asset,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        # Assert
        usage_event = UsageEvent.objects.get()
        self.assertEqual(result, usage_event)
        self.assertEqual(usage_event.developer_user, self.user)
        self.assertEqual(usage_event.usage_kind, UsageEvent.UsageKindChoice.VIEW)
        self.assertEqual(usage_event.asset_id, self.asset.id)
        self.assertEqual(
            usage_event.metadata,
            {
                "asset_title": self.asset.name,
                "asset_name": self.asset.name,
                "category": self.asset.category,
            },
        )
        self.assertEqual(usage_event.ip_address, ip_address)
        self.assertEqual(usage_event.user_agent, user_agent)

    def test_log_api_access_where_asset_is_provided_should_persist_api_access_event(self):
        # Arrange
        api_endpoint = f"/api/v1/assets/{self.asset.id}/"
        ip_address = "10.0.0.1"
        user_agent = "CustomClient/2.0"

        # Act
        result = log_api_access(
            user=self.user,
            api_endpoint=api_endpoint,
            ip_address=ip_address,
            user_agent=user_agent,
            asset=self.asset,
        )

        # Assert
        usage_event = UsageEvent.objects.get()
        self.assertEqual(result, usage_event)
        self.assertEqual(usage_event.developer_user, self.user)
        self.assertEqual(usage_event.usage_kind, UsageEvent.UsageKindChoice.API_ACCESS)
        self.assertEqual(usage_event.asset_id, self.asset.id)
        self.assertEqual(
            usage_event.metadata,
            {
                "api_endpoint": api_endpoint,
                "asset_title": self.asset.name,
                "asset_name": self.asset.name,
            },
        )
        self.assertEqual(usage_event.ip_address, ip_address)
        self.assertEqual(usage_event.user_agent, user_agent)

    def test_log_api_access_where_asset_is_not_provided_should_return_none_without_persisting_event(self):
        # Arrange
        api_endpoint = "/api/v1/health/"

        # Act
        result = log_api_access(
            user=self.user,
            api_endpoint=api_endpoint,
            asset=None,
        )

        # Assert
        self.assertIsNone(result)
        self.assertFalse(UsageEvent.objects.exists())

    def test_log_asset_download_where_asset_is_provided_should_dispatch_task_with_expected_payload(self):
        # Arrange
        ip_address = "172.16.0.1"
        user_agent = "Downloader/1.0"
        expected_payload = {
            "developer_user_id": self.user.id,
            "usage_kind": "file_download",
            "asset_id": self.asset.id,
            "metadata": {
                "asset_title": self.asset.name,
                "asset_name": self.asset.name,
                "file_size": self.asset.file_size,
                "format": self.asset.format,
                "category": self.asset.category,
            },
            "ip_address": ip_address,
            "user_agent": user_agent,
        }

        # Act
        with patch.object(
            create_usage_event_task,
            create_usage_event_task.delay.__name__,
        ) as mock_delay:
            result = log_asset_download(
                user=self.user,
                asset=self.asset,
                ip_address=ip_address,
                user_agent=user_agent,
            )

        # Assert
        self.assertIsNone(result)
        mock_delay.assert_called_once_with(expected_payload)
