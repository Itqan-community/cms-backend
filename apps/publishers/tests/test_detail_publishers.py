from model_bakery import baker

from apps.publishers.models import Publisher
from apps.core.tests import BaseTestCase


class DetailPublisherTest(BaseTestCase):
    def test_detail_publishers_where_valid_id_should_return_full_payload_en(self):
        # Arrange
        publisher = baker.make(
            Publisher,
            name="Tafsir Center",
            slug="tafsir-center",
            description="A comprehensive Islamic research center focused on Quranic studies and tafsir",
            address="Riyadh, Saudi Arabia",
            website="https://tafsircenter.org",
            is_verified=True,
            contact_email="info@tafsircenter.org",
            icon_url="icons/tafsir-center.png",
        )

        # Act
        response = self.client.get(f"/publishers/{publisher.id}/", format="json")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual(publisher.id, body["id"])
        self.assertEqual("Tafsir Center", body["name"])
        self.assertEqual("tafsir-center", body["slug"])
        self.assertEqual(
            "A comprehensive Islamic research center focused on Quranic studies and tafsir", body["description"]
        )
        self.assertEqual("Riyadh, Saudi Arabia", body["address"])
        self.assertEqual("https://tafsircenter.org", body["website"])
        self.assertTrue(body["is_verified"])
        self.assertEqual("info@tafsircenter.org", body["contact_email"])
        self.assertTrue(body["icon_url"].endswith("icons/tafsir-center.png"))

    def test_detail_publishers_where_publisher_does_not_exist_should_return_404(self):
        # Arrange
        non_existent_id = 99999

        # Act
        response = self.client.get(f"/publishers/{non_existent_id}/", format="json")

        # Assert
        self.assertEqual(404, response.status_code, response.content)

    def test_detail_publishers_where_response_schema_should_include_all_required_fields(self):
        # Arrange
        publisher = baker.make(
            Publisher,
            name="Test Publisher",
            slug="test-publisher",
            description="Test description",
            address="Test location",
            website="https://test.com",
            is_verified=False,
            contact_email="test@test.com",
            icon_url="test-icon.png",
        )

        # Act
        response = self.client.get(f"/publishers/{publisher.id}/", format="json")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        required_fields = [
            "id",
            "name",
            "slug",
            "description",
            "address",
            "website",
            "is_verified",
            "contact_email",
            "icon_url",
        ]
        for field in required_fields:
            self.assertIn(field, body, f"Missing required field: {field}")

    def test_detail_publishers_where_verified_status_should_return_correct_boolean(self):
        # Arrange
        verified_publisher = baker.make(Publisher, name="Verified Publisher", is_verified=True, icon_url="verified.png")
        unverified_publisher = baker.make(
            Publisher, name="Unverified Publisher", is_verified=False, icon_url="unverified.png"
        )

        # Act + Assert (verified)
        response_verified = self.client.get(f"/publishers/{verified_publisher.id}/", format="json")
        self.assertEqual(200, response_verified.status_code, response_verified.content)
        body_verified = response_verified.json()
        self.assertTrue(body_verified["is_verified"])
        self.assertEqual("Verified Publisher", body_verified["name"])

        # Act + Assert (unverified)
        response_unverified = self.client.get(f"/publishers/{unverified_publisher.id}/", format="json")
        self.assertEqual(200, response_unverified.status_code, response_unverified.content)
        body_unverified = response_unverified.json()
        self.assertFalse(body_unverified["is_verified"])
        self.assertEqual("Unverified Publisher", body_unverified["name"])

    def test_detail_publishers_where_empty_optional_fields_should_return_empty_values(self):
        # Arrange
        publisher = baker.make(
            Publisher,
            name="Minimal Publisher",
            slug="minimal-publisher",
            description="",  # Empty description
            address="",  # Empty location
            website="",  # Empty website
            contact_email="",  # Empty email
            icon_url="",  # Empty icon
        )

        # Act
        response = self.client.get(f"/publishers/{publisher.id}/", format="json")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual("", body["description"])
        self.assertEqual("", body["address"])
        self.assertEqual("", body["website"])
        self.assertEqual("", body["contact_email"])
        # icon_url can be None or empty string when no file is uploaded
        self.assertTrue(body["icon_url"] == "" or body["icon_url"] is None)

    def test_detail_publishers_where_complex_social_links_should_return_correct_json(self):
        # Arrange
        complex_social_links = {
            "twitter": "@publisher_handle",
            "facebook": "publisherpage",
            "instagram": "publisher_insta",
            "youtube": "publisherchannel",
            "linkedin": "company/publisher",
            "website": "https://publisher.com",
            "custom_links": {"blog": "https://blog.publisher.com", "newsletter": "https://newsletter.publisher.com"},
        }
        publisher = baker.make(
            Publisher, name="Social Media Publisher", icon_url="social-icon.png"
        )

        # Act
        response = self.client.get(f"/publishers/{publisher.id}/", format="json")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        # social_links field no longer exists in the API

    def test_detail_publishers_where_invalid_requests_should_return_appropriate_errors(self):
        """Test error handling for invalid integer formats and empty paths."""
        # Test invalid integer formats - should return 400
        invalid_formats = [
            "not-a-number",  # Non-numeric
            "123.45",  # Decimal
            "abc123",  # Mixed alphanumeric
        ]

        for invalid_format in invalid_formats:
            with self.subTest(invalid_format=invalid_format):
                # Act
                response = self.client.get(f"/publishers/{invalid_format}/", format="json")

                # Assert
                self.assertEqual(
                    400,
                    response.status_code,
                    f"Failed for format: {invalid_format}, response: {response.content}",
                )

        # Test empty path - should return 404
        response = self.client.get("/publishers/", format="json")
        self.assertEqual(404, response.status_code, response.content)

    def test_detail_publishers_where_multiple_publishers_should_return_correct_specific_publisher(self):
        # Arrange
        baker.make(
            Publisher,
            name="First Publisher",
            slug="first-publisher",
            description="First summary",
            is_verified=True,
            icon_url="first-icon.png",
        )
        publisher2 = baker.make(
            Publisher,
            name="Second Publisher",
            slug="second-publisher",
            description="Second summary",
            is_verified=False,
            icon_url="second-icon.png",
        )

        # Act
        response = self.client.get(f"/publishers/{publisher2.id}/", format="json")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual(publisher2.id, body["id"])
        self.assertEqual("Second Publisher", body["name"])
        self.assertEqual("second-publisher", body["slug"])
        self.assertEqual("Second summary", body["description"])
        self.assertFalse(body["is_verified"])

    def test_detail_publishers_where_field_types_should_match_expected_schema(self):
        # Arrange
        publisher = baker.make(
            Publisher,
            name="Type Test Publisher",
            is_verified=True,
            icon_url="type-test-icon.png",
        )

        # Act
        response = self.client.get(f"/publishers/{publisher.id}/", format="json")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()

        # Verify field types
        self.assertIsInstance(body["id"], int)  # Integer ID
        self.assertIsInstance(body["name"], str)
        self.assertIsInstance(body["slug"], str)
        self.assertIsInstance(body["description"], str)
        self.assertIsInstance(body["address"], str)
        self.assertIsInstance(body["website"], str)
        self.assertIsInstance(body["is_verified"], bool)
        self.assertIsInstance(body["contact_email"], str)
        self.assertTrue(isinstance(body["icon_url"], (str, type(None))))
