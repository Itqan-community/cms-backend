from model_bakery import baker

from apps.content.models import Asset, AssetAccessRequest, AssetAccess, LicenseChoice
from apps.publishers.models import Publisher
from apps.users.models import User
from apps.core.tests import BaseTestCase


class AssetAccessTest(BaseTestCase):
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

    def test_request_asset_access_with_valid_data_should_return_201_with_access_granted(self):
        # Arrange
        data = {
            "purpose": "Academic research on Quranic studies",
            "intended_use": AssetAccessRequest.IntendedUseChoice.NON_COMMERCIAL
        }

        # Act
        self.authenticate_user(self.user)
        response = self.client.post(
            f"/content/assets/{self.asset.id}/request-access/", 
            data=data, 
            format='json'
        )

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        
        # Check request structure
        self.assertIn("request", body)
        request_data = body["request"]
        self.assertIn("id", request_data)
        self.assertEqual(self.asset.id, request_data["asset_id"])
        self.assertEqual("Academic research on Quranic studies", request_data["purpose"])
        self.assertEqual("non-commercial", request_data["intended_use"])
        self.assertEqual("approved", request_data["status"])  # V1: Auto-approval
        self.assertIn("created_at", request_data)
        
        # Check access structure
        self.assertIn("access", body)
        access_data = body["access"]
        self.assertIn("id", access_data)
        self.assertEqual(self.asset.id, access_data["asset_id"])
        self.assertTrue(access_data["is_active"])
        # expires_at can be None
        # download_url is None in current implementation

    def test_request_asset_access_with_commercial_use_should_return_201(self):
        # Arrange
        data = {
            "purpose": "Commercial application development",
            "intended_use": AssetAccessRequest.IntendedUseChoice.COMMERCIAL
        }

        # Act
        self.authenticate_user(self.user)
        response = self.client.post(
            f"/content/assets/{self.asset.id}/request-access/", 
            data=data, 
            format='json'
        )

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        
        self.assertEqual("commercial", body["request"]["intended_use"])
        self.assertEqual("approved", body["request"]["status"])

    def test_request_asset_access_with_invalid_intended_use_should_return_422(self):
        # Arrange
        data = {
            "purpose": "Test purpose",
            "intended_use": "invalid_use"  # Invalid enum value
        }

        # Act
        self.authenticate_user(self.user)
        response = self.client.post(
            f"/content/assets/{self.asset.id}/request-access/", 
            data=data, 
            format='json'
        )

        # Assert
        self.assertEqual(422, response.status_code, response.content)

    def test_request_asset_access_with_missing_purpose_should_return_422(self):
        # Arrange
        data = {
            # Missing purpose
            "intended_use": AssetAccessRequest.IntendedUseChoice.NON_COMMERCIAL
        }

        # Act
        self.authenticate_user(self.user)
        response = self.client.post(
            f"/content/assets/{self.asset.id}/request-access/", 
            data=data, 
            format='json'
        )

        # Assert
        self.assertEqual(422, response.status_code, response.content)

    def test_request_asset_access_for_non_existent_asset_should_return_404(self):
        # Arrange
        non_existent_asset_id = 99999
        data = {
            "purpose": "Test purpose",
            "intended_use": AssetAccessRequest.IntendedUseChoice.NON_COMMERCIAL
        }

        # Act
        self.authenticate_user(self.user)
        response = self.client.post(
            f"/content/assets/{non_existent_asset_id}/request-access/", 
            data=data, 
            format='json'
        )

        # Assert
        self.assertEqual(404, response.status_code, response.content)

    def test_request_asset_access_without_authentication_should_return_401(self):
        # Arrange
        data = {
            "purpose": "Test purpose",
            "intended_use": AssetAccessRequest.IntendedUseChoice.NON_COMMERCIAL
        }

        # Act (without authentication)
        response = self.client.post(
            f"/content/assets/{self.asset.id}/request-access/", 
            data=data, 
            format='json'
        )

        # Assert
        self.assertEqual(401, response.status_code, response.content)

    def test_request_asset_access_twice_should_return_existing_access(self):
        # Arrange
        data = {
            "purpose": "First request",
            "intended_use": AssetAccessRequest.IntendedUseChoice.NON_COMMERCIAL
        }

        # Act - First request
        self.authenticate_user(self.user)
        first_response = self.client.post(
            f"/content/assets/{self.asset.id}/request-access/", 
            data=data, 
            format='json'
        )
        
        # Act - Second request with different purpose
        data["purpose"] = "Second request"
        second_response = self.client.post(
            f"/content/assets/{self.asset.id}/request-access/", 
            data=data, 
            format='json'
        )

        # Assert
        self.assertEqual(200, first_response.status_code, first_response.content)
        self.assertEqual(200, second_response.status_code, second_response.content)
        
        # Both should return the same access (existing one)
        first_body = first_response.json()
        second_body = second_response.json()
        
        # The access ID should be the same (existing access returned)
        self.assertEqual(first_body["access"]["id"], second_body["access"]["id"])

    def test_request_asset_access_should_create_database_records(self):
        # Arrange
        data = {
            "purpose": "Database verification test",
            "intended_use": AssetAccessRequest.IntendedUseChoice.NON_COMMERCIAL
        }

        # Act
        self.authenticate_user(self.user)
        response = self.client.post(
            f"/content/assets/{self.asset.id}/request-access/", 
            data=data, 
            format='json'
        )

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        
        # Verify access request is created in database
        access_request = AssetAccessRequest.objects.filter(
            developer_user=self.user,
            asset=self.asset
        ).first()
        self.assertIsNotNone(access_request)
        self.assertEqual("Database verification test", access_request.developer_access_reason)
        self.assertEqual(AssetAccessRequest.IntendedUseChoice.NON_COMMERCIAL, access_request.intended_use)
        self.assertEqual(AssetAccessRequest.StatusChoice.APPROVED, access_request.status)
        
        # Verify access grant is created in database
        access_grant = AssetAccess.objects.filter(
            user=self.user,
            asset=self.asset
        ).first()
        self.assertIsNotNone(access_grant)
        self.assertTrue(access_grant.is_active)

    def test_request_asset_access_with_invalid_asset_id_format_should_return_400(self):
        # Arrange
        invalid_formats = [
            "not-a-number",
            "123.45",
            "abc123",
        ]
        data = {
            "purpose": "Test purpose",
            "intended_use": AssetAccessRequest.IntendedUseChoice.NON_COMMERCIAL
        }

        for invalid_format in invalid_formats:
            with self.subTest(invalid_format=invalid_format):
                # Act
                self.authenticate_user(self.user)
                response = self.client.post(
                    f"/content/assets/{invalid_format}/request-access/", 
                    data=data, 
                    format='json'
                )

                # Assert
                self.assertEqual(
                    400,
                    response.status_code,
                    f"Failed for format: {invalid_format}, response: {response.content}",
                )
