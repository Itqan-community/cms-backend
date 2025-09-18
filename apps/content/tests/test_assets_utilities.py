from django.test import TestCase
from model_bakery import baker
from unittest.mock import patch

from apps.content.models import Asset, AssetAccess, AssetAccessRequest, LicenseChoice
from apps.publishers.models import Publisher
from apps.users.models import User
from apps.core.tests import BaseTestCase


class AssetUtilitiesTest(BaseTestCase):
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

    def test_asset_access_status_without_authentication_should_return_no_access(self):
        # Act (without authentication)
        response = self.client.get(f"/content/assets/{self.asset.id}/access-status/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        
        self.assertFalse(body["has_access"])
        self.assertFalse(body["requires_approval"])  # V1: Auto-approval

    @patch('apps.content.views.assets_utilities.user_has_access')
    def test_asset_access_status_with_no_access_should_return_no_access(self, mock_user_has_access):
        # Arrange
        mock_user_has_access.return_value = False

        # Act
        self.authenticate_user(self.user)
        response = self.client.get(f"/content/assets/{self.asset.id}/access-status/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        
        self.assertFalse(body["has_access"])
        self.assertFalse(body["requires_approval"])
        mock_user_has_access.assert_called_once_with(self.user, self.asset)

    @patch('apps.content.views.assets_utilities.user_has_access')
    def test_asset_access_status_with_access_should_return_access_granted(self, mock_user_has_access):
        # Arrange
        mock_user_has_access.return_value = True

        # Act
        self.authenticate_user(self.user)
        response = self.client.get(f"/content/assets/{self.asset.id}/access-status/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        
        self.assertTrue(body["has_access"])
        self.assertFalse(body["requires_approval"])  # V1: Auto-approval
        self.assertEqual(f"/content/assets/{self.asset.id}/download/", body["download_url"])
        mock_user_has_access.assert_called_once_with(self.user, self.asset)

    def test_asset_access_status_with_non_existent_asset_should_return_404(self):
        # Arrange
        non_existent_asset_id = 99999

        # Act
        self.authenticate_user(self.user)
        response = self.client.get(f"/content/assets/{non_existent_asset_id}/access-status/")

        # Assert
        self.assertEqual(404, response.status_code, response.content)

    def test_asset_access_status_should_include_all_required_fields(self):
        # Act
        response = self.client.get(f"/content/assets/{self.asset.id}/access-status/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        
        required_fields = ["has_access", "requires_approval", "download_url"]
        for field in required_fields:
            self.assertIn(field, body, f"Missing required field: {field}")

    def test_asset_access_status_field_types_should_match_expected_schema(self):
        # Act
        self.authenticate_user(self.user)
        response = self.client.get(f"/content/assets/{self.asset.id}/access-status/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()

        # Verify field types
        self.assertIsInstance(body["has_access"], bool)
        self.assertIsInstance(body["requires_approval"], bool)
        self.assertTrue(isinstance(body["download_url"], (str, type(None))))

    @patch('apps.content.views.assets_utilities.user_has_access')
    def test_asset_access_status_with_different_users_should_return_different_results(self, mock_user_has_access):
        # Arrange
        user_with_access = baker.make(User, email="access@example.com")
        user_without_access = baker.make(User, email="no-access@example.com")
        
        def mock_access_check(user, asset):
            return user == user_with_access
        
        mock_user_has_access.side_effect = mock_access_check

        # Act & Assert for user with access
        self.authenticate_user(user_with_access)
        response = self.client.get(f"/content/assets/{self.asset.id}/access-status/")
        
        self.assertEqual(200, response.status_code)
        body = response.json()
        self.assertTrue(body["has_access"])
        self.assertIsNotNone(body["download_url"])

        # Act & Assert for user without access
        self.authenticate_user(user_without_access)
        response = self.client.get(f"/content/assets/{self.asset.id}/access-status/")
        
        self.assertEqual(200, response.status_code)
        body = response.json()
        self.assertFalse(body["has_access"])

    def test_asset_access_status_v1_policy_should_always_return_no_approval_required(self):
        # Arrange - Test with both authenticated and unauthenticated users
        test_cases = [
            (None, "unauthenticated"),
            (self.user, "authenticated")
        ]

        for user, case_name in test_cases:
            with self.subTest(case=case_name):
                # Act
                if user:
                    self.authenticate_user(user)
                else:
                    self.client.logout()
                
                response = self.client.get(f"/content/assets/{self.asset.id}/access-status/")

                # Assert
                self.assertEqual(200, response.status_code, response.content)
                body = response.json()
                
                # V1 policy: No approval required (auto-approval)
                self.assertFalse(body["requires_approval"])

    def test_asset_access_status_with_invalid_id_format_should_return_400(self):
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
                response = self.client.get(f"/content/assets/{invalid_format}/access-status/")

                # Assert
                self.assertEqual(
                    400,
                    response.status_code,
                    f"Failed for format: {invalid_format}, response: {response.content}",
                )
