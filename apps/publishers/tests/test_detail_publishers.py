from uuid import uuid4

from model_bakery import baker

from apps.content.models import Publisher
from apps.core.tests import BaseTestCase


class DetailPublisherTest(BaseTestCase):
    def test_detail_publishers_where_valid_id_should_return_full_payload_en(self):
        # Arrange
        publisher = baker.make(
            Publisher,
            name="Tafsir Center",
            slug="tafsir-center",
            summary="Leading Islamic research organization",
            description="A comprehensive Islamic research center focused on Quranic studies and tafsir",
            location="Riyadh, Saudi Arabia",
            website="https://tafsircenter.org",
            verified=True,
            contact_email="info@tafsircenter.org",
            icon_url="icons/tafsir-center.png",
            social_links={"twitter": "@tafsircenter", "facebook": "tafsircenter"},
        )

        # Act
        response = self.client.get(f"/content/publishers/{publisher.id}/", format="json")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual(str(publisher.id), body["id"])
        self.assertEqual("Tafsir Center", body["name"])
        self.assertEqual("tafsir-center", body["slug"])
        self.assertEqual("Leading Islamic research organization", body["summary"])
        self.assertEqual(
            "A comprehensive Islamic research center focused on Quranic studies and tafsir", body["description"]
        )
        self.assertEqual("Riyadh, Saudi Arabia", body["location"])
        self.assertEqual("https://tafsircenter.org", body["website"])
        self.assertTrue(body["verified"])
        self.assertEqual("info@tafsircenter.org", body["contact_email"])
        self.assertTrue(body["icon_url"].endswith("icons/tafsir-center.png"))
        self.assertEqual({"twitter": "@tafsircenter", "facebook": "tafsircenter"}, body["social_links"])

    def test_detail_publishers_where_publisher_does_not_exist_should_return_404(self):
        # Arrange
        non_existent_id = uuid4()

        # Act
        response = self.client.get(f"/content/publishers/{non_existent_id}/", format="json")

        # Assert
        self.assertEqual(404, response.status_code, response.content)

    def test_detail_publishers_where_response_schema_should_include_all_required_fields(self):
        # Arrange
        publisher = baker.make(
            Publisher,
            name="Test Publisher",
            slug="test-publisher",
            summary="Test summary",
            description="Test description",
            location="Test location",
            website="https://test.com",
            verified=False,
            contact_email="test@test.com",
            icon_url="test-icon.png",
            social_links={"test": "test"},
        )

        # Act
        response = self.client.get(f"/content/publishers/{publisher.id}/", format="json")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        required_fields = [
            "id",
            "name",
            "slug",
            "summary",
            "description",
            "location",
            "website",
            "verified",
            "contact_email",
            "icon_url",
            "social_links",
        ]
        for field in required_fields:
            self.assertIn(field, body, f"Missing required field: {field}")

    def test_detail_publishers_where_verified_status_should_return_correct_boolean(self):
        # Arrange
        verified_publisher = baker.make(Publisher, name="Verified Publisher", verified=True, icon_url="verified.png")
        unverified_publisher = baker.make(
            Publisher, name="Unverified Publisher", verified=False, icon_url="unverified.png"
        )

        # Act + Assert (verified)
        response_verified = self.client.get(f"/content/publishers/{verified_publisher.id}/", format="json")
        self.assertEqual(200, response_verified.status_code, response_verified.content)
        body_verified = response_verified.json()
        self.assertTrue(body_verified["verified"])
        self.assertEqual("Verified Publisher", body_verified["name"])

        # Act + Assert (unverified)
        response_unverified = self.client.get(f"/content/publishers/{unverified_publisher.id}/", format="json")
        self.assertEqual(200, response_unverified.status_code, response_unverified.content)
        body_unverified = response_unverified.json()
        self.assertFalse(body_unverified["verified"])
        self.assertEqual("Unverified Publisher", body_unverified["name"])

    def test_detail_publishers_where_empty_optional_fields_should_return_empty_values(self):
        # Arrange
        publisher = baker.make(
            Publisher,
            name="Minimal Publisher",
            slug="minimal-publisher",
            summary="",  # Empty summary
            description="",  # Empty description
            location="",  # Empty location
            website="",  # Empty website
            contact_email="",  # Empty email
            icon_url="",  # Empty icon
            social_links={},  # Empty social links
        )

        # Act
        response = self.client.get(f"/content/publishers/{publisher.id}/", format="json")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual("", body["summary"])
        self.assertEqual("", body["description"])
        self.assertEqual("", body["location"])
        self.assertEqual("", body["website"])
        self.assertEqual("", body["contact_email"])
        # icon_url can be None or empty string when no file is uploaded
        self.assertTrue(body["icon_url"] == "" or body["icon_url"] is None)
        self.assertEqual({}, body["social_links"])

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
            Publisher, name="Social Media Publisher", social_links=complex_social_links, icon_url="social-icon.png"
        )

        # Act
        response = self.client.get(f"/content/publishers/{publisher.id}/", format="json")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual(complex_social_links, body["social_links"])

    def test_detail_publishers_where_invalid_requests_should_return_appropriate_errors(self):
        """Test error handling for invalid UUID formats and empty paths."""
        # Test invalid UUID formats - should return 400
        invalid_formats = [
            "123",  # Too short
            "not-a-uuid-at-all",  # Not UUID format
            "12345678-1234-1234-1234-1234567890123",  # Too long
            "12345678-1234-1234-1234-12345678901",  # Invalid characters
        ]

        for invalid_format in invalid_formats:
            with self.subTest(invalid_format=invalid_format):
                # Act
                response = self.client.get(f"/content/publishers/{invalid_format}/", format="json")

                # Assert
                self.assertEqual(
                    400,
                    response.status_code,
                    f"Failed for format: {invalid_format}, response: {response.content}",
                )

        # Test empty path - should return 404
        response = self.client.get("/content/publishers//", format="json")
        self.assertEqual(404, response.status_code, response.content)

    def test_detail_publishers_where_multiple_publishers_should_return_correct_specific_publisher(self):
        # Arrange
        baker.make(
            Publisher,
            name="First Publisher",
            slug="first-publisher",
            summary="First summary",
            verified=True,
            icon_url="first-icon.png",
        )
        publisher2 = baker.make(
            Publisher,
            name="Second Publisher",
            slug="second-publisher",
            summary="Second summary",
            verified=False,
            icon_url="second-icon.png",
        )

        # Act
        response = self.client.get(f"/content/publishers/{publisher2.id}/", format="json")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual(str(publisher2.id), body["id"])
        self.assertEqual("Second Publisher", body["name"])
        self.assertEqual("second-publisher", body["slug"])
        self.assertEqual("Second summary", body["summary"])
        self.assertFalse(body["verified"])

    def test_detail_publishers_where_field_types_should_match_expected_schema(self):
        # Arrange
        publisher = baker.make(
            Publisher,
            name="Type Test Publisher",
            verified=True,
            social_links={"test": "value"},
            icon_url="type-test-icon.png",
        )

        # Act
        response = self.client.get(f"/content/publishers/{publisher.id}/", format="json")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()

        # Verify field types
        self.assertIsInstance(body["id"], str)  # UUID as string
        self.assertIsInstance(body["name"], str)
        self.assertIsInstance(body["slug"], str)
        self.assertIsInstance(body["summary"], str)
        self.assertIsInstance(body["description"], str)
        self.assertIsInstance(body["location"], str)
        self.assertIsInstance(body["website"], str)
        self.assertIsInstance(body["verified"], bool)
        self.assertIsInstance(body["contact_email"], str)
        self.assertTrue(isinstance(body["icon_url"], (str, type(None))))
        self.assertIsInstance(body["social_links"], dict)
