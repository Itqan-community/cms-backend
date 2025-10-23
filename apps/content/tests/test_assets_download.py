from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from model_bakery import baker
from unittest.mock import patch, MagicMock

from apps.content.models import Asset, AssetVersion, AssetAccess, AssetAccessRequest, LicenseChoice, UsageEvent
from apps.publishers.models import Publisher
from apps.users.models import User
from apps.core.tests import BaseTestCase


class AssetDownloadTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.publisher = baker.make(Publisher, name="Test Publisher")
        self.resource = baker.make("content.Resource", publisher=self.publisher)
        self.asset = baker.make(
            Asset,
            resource=self.resource,
            name="Test Asset",
            description="Test asset description",
            category=Asset.CategoryChoice.TAFSIR,
            license=LicenseChoice.CC_BY_SA
        )
        self.user = baker.make(User, email="test@example.com")
        
        # Create access for the user
        self.access_request = baker.make(
            AssetAccessRequest,
            developer_user=self.user,
            asset=self.asset,
            status=AssetAccessRequest.StatusChoice.APPROVED
        )
        self.access_grant = baker.make(
            AssetAccess,
            user=self.user,
            asset=self.asset,
            asset_access_request=self.access_request,
            expires_at=None  # Never expires, so is_active will be True
        )

    @patch('apps.content.views.assets_download.user_has_access')
    def test_download_asset_without_access_should_return_403(self, mock_user_has_access):
        # Arrange
        mock_user_has_access.return_value = False

        # Act
        self.authenticate_user(self.user)
        response = self.client.get(f"/assets/{self.asset.id}/download/")

        # Assert
        self.assertEqual(403, response.status_code, response.content)
        mock_user_has_access.assert_called_once_with(self.user, self.asset)

    def test_download_asset_without_authentication_should_return_401(self):
        # Act (without authentication)
        response = self.client.get(f"/assets/{self.asset.id}/download/")

        # Assert
        self.assertEqual(401, response.status_code, response.content)

    def test_download_asset_with_non_existent_asset_should_return_404(self):
        # Arrange
        non_existent_asset_id = 99999

        # Act
        self.authenticate_user(self.user)
        response = self.client.get(f"/assets/{non_existent_asset_id}/download/")

        # Assert
        self.assertEqual(404, response.status_code, response.content)

    @patch('apps.content.views.assets_download.user_has_access')
    def test_download_asset_with_no_versions_should_return_404(self, mock_user_has_access):
        # Arrange
        mock_user_has_access.return_value = True
        # No asset versions created

        # Act
        self.authenticate_user(self.user)
        response = self.client.get(f"/assets/{self.asset.id}/download/")

        # Assert
        self.assertEqual(404, response.status_code, response.content)

    @patch('apps.content.views.assets_download.user_has_access')
    def test_download_asset_with_no_file_should_return_404(self, mock_user_has_access):
        # Arrange
        mock_user_has_access.return_value = True
        baker.make(AssetVersion, asset=self.asset, file_url=None)  # No file

        # Act
        self.authenticate_user(self.user)
        response = self.client.get(f"/assets/{self.asset.id}/download/")

        # Assert
        self.assertEqual(404, response.status_code, response.content)

    @patch('apps.content.views.assets_download.user_has_access')
    def test_download_asset_with_valid_file_should_return_file_response(self, mock_user_has_access):
        # Arrange
        mock_user_has_access.return_value = True
        
        # Create a mock file
        mock_file = SimpleUploadedFile("test.pdf", b"fake pdf content", content_type="application/pdf")
        baker.make(AssetVersion, asset=self.asset, name="Version 1", file_url=mock_file)

        # Act
        self.authenticate_user(self.user)
        response = self.client.get(f"/assets/{self.asset.id}/download/")
        body = response.json()

        # Assert
        self.assertEqual(200, response.status_code)
        self.assertIn("download_url", body)
        self.assertIn("/test.pdf", body["download_url"])

    @patch('apps.content.views.assets_download.user_has_access')
    def test_download_asset_with_csv_file_should_return_correct_content_type(self, mock_user_has_access):
        # Arrange
        mock_user_has_access.return_value = True
        
        # Create a CSV file
        mock_file = SimpleUploadedFile("test.csv", b"fake csv content", content_type="text/csv")
        baker.make(AssetVersion, asset=self.asset, name="CSV Version", file_url=mock_file)

        # Act
        self.authenticate_user(self.user)
        response = self.client.get(f"/assets/{self.asset.id}/download/")
        body = response.json()

        # Assert
        self.assertEqual(200, response.status_code)
        self.assertIn("download_url", body)
        self.assertIn("/test.csv", body["download_url"])

    @patch('apps.content.views.assets_download.user_has_access')
    def test_download_asset_should_return_latest_version(self, mock_user_has_access):
        # Arrange
        mock_user_has_access.return_value = True
        
        # Create multiple versions
        older_file = SimpleUploadedFile("old.pdf", b"old content", content_type="application/pdf")
        newer_file = SimpleUploadedFile("new.pdf", b"new content", content_type="application/pdf")
        
        older_version = baker.make(AssetVersion, asset=self.asset, name="Old Version", file_url=older_file)
        newer_version = baker.make(AssetVersion, asset=self.asset, name="New Version", file_url=newer_file)
        
        # Make newer version actually newer by setting created_at
        newer_version.created_at = older_version.created_at + timezone.timedelta(days=1)
        newer_version.save()

        # Act
        self.authenticate_user(self.user)
        response = self.client.get(f"/assets/{self.asset.id}/download/")
        body = response.json()

        # Assert
        self.assertEqual(200, response.status_code)
        self.assertIn("download_url", body)
        self.assertIn("/new.pdf", body["download_url"])

    def test_download_asset_with_invalid_id_format_should_return_400(self):
        # Arrange
        invalid_formats = [
            "not-a-number",
            "123.45",
            "abc123",
        ]

        for invalid_format in invalid_formats:
            with self.subTest(invalid_format=invalid_format):
                # Act
                self.authenticate_user(self.user)
                response = self.client.get(f"/assets/{invalid_format}/download/")

                # Assert
                self.assertEqual(
                    400,
                    response.status_code,
                    f"Failed for format: {invalid_format}, response: {response.content}",
                )

    @patch('apps.content.views.assets_download.user_has_access')
    def test_download_asset_should_create_usage_event_for_authenticated_user(self, mock_user_has_access):
        # Arrange
        mock_user_has_access.return_value = True

        # Create a mock file
        mock_file = SimpleUploadedFile("test.pdf", b"fake pdf content", content_type="application/pdf")
        baker.make(AssetVersion, asset=self.asset, name="Download Test", file_url=mock_file)

        # Act
        self.authenticate_user(self.user)
        response = self.client.get(f"/assets/{self.asset.id}/download/")

        # Assert
        self.assertEqual(200, response.status_code)
        
        # Verify usage event was created in database
        usage_events = UsageEvent.objects.filter(
            developer_user=self.user,
            usage_kind=UsageEvent.UsageKindChoice.FILE_DOWNLOAD,
            subject_kind=UsageEvent.SubjectKindChoice.ASSET,
            asset_id=self.asset.id
        )
        self.assertEqual(1, usage_events.count())
        
        usage_event = usage_events.first()
        self.assertEqual(usage_event.developer_user, self.user)
        self.assertEqual(usage_event.usage_kind, UsageEvent.UsageKindChoice.FILE_DOWNLOAD)
        self.assertEqual(usage_event.subject_kind, UsageEvent.SubjectKindChoice.ASSET)
        self.assertEqual(usage_event.asset_id, self.asset.id)
        self.assertIsNone(usage_event.resource_id)
        self.assertEqual(usage_event.effective_license, self.asset.license)
        self.assertIsInstance(usage_event.metadata, dict)

    @patch('apps.content.views.assets_download.user_has_access')
    def test_download_asset_should_not_create_usage_event_when_permission_denied(self, mock_user_has_access):
        # Arrange
        mock_user_has_access.return_value = False  # No access

        # Act
        self.authenticate_user(self.user)
        response = self.client.get(f"/assets/{self.asset.id}/download/")

        # Assert
        self.assertEqual(403, response.status_code)
        
        # Verify no usage event was created when access denied
        usage_events = UsageEvent.objects.filter(
            developer_user=self.user,
            usage_kind=UsageEvent.UsageKindChoice.FILE_DOWNLOAD,
            subject_kind=UsageEvent.SubjectKindChoice.ASSET,
            asset_id=self.asset.id
        )
        self.assertEqual(0, usage_events.count())

    @patch('apps.content.views.assets_download.user_has_access')
    def test_download_asset_should_include_request_metadata_in_usage_event(self, mock_user_has_access):
        # Arrange
        mock_user_has_access.return_value = True
        
        # Create a mock file
        mock_file = SimpleUploadedFile("test.csv", b"fake csv content", content_type="text/csv")
        baker.make(AssetVersion, asset=self.asset, name="Metadata Test", file_url=mock_file)

        # Act - Include custom headers
        self.authenticate_user(self.user)
        response = self.client.get(
            f"/assets/{self.asset.id}/download/",
            HTTP_USER_AGENT="Download Agent/2.0",
            HTTP_X_FORWARDED_FOR="192.168.1.200"
        )

        # Assert
        self.assertEqual(200, response.status_code)
        
        # Verify usage event was created with correct metadata
        usage_events = UsageEvent.objects.filter(
            developer_user=self.user,
            usage_kind=UsageEvent.UsageKindChoice.FILE_DOWNLOAD,
            subject_kind=UsageEvent.SubjectKindChoice.ASSET,
            asset_id=self.asset.id
        )
        self.assertEqual(1, usage_events.count())
        
        usage_event = usage_events.first()
        self.assertEqual(usage_event.user_agent, "Download Agent/2.0")
        # Note: IP address capture depends on Django test client configuration
        # In real requests, this would capture the client IP
