from model_bakery import baker

from apps.content.models import License
from apps.core.tests import BaseTestCase


class ListLicenseTest(BaseTestCase):
    def test_list_licenses_should_return_all_available_licenses(self):
        # Arrange
        baker.make(License, name="MIT License", code="MIT", short_name="MIT")

        # Act
        response = self.client.get("/content/licenses/", format="json")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        response_body = response.json()
        self.assertEqual(1, len(response_body["results"]))
        self.assertEqual("MIT License", response_body["results"][0]["name"])
        self.assertEqual("MIT", response_body["results"][0]["code"])
        self.assertEqual("MIT", response_body["results"][0]["short_name"])

    def test_list_licenses_filter_by_code_should_return_filtered_licenses(self):
        # Arrange
        baker.make(License, name="MIT License", code="MIT", short_name="MIT")
        baker.make(License, name="Apache License 2.0", code="Apache-2.0", short_name="Apache 2.0")

        # Act
        response = self.client.get("/content/licenses/", data={"code": "MIT"}, format="json")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        response_body = response.json()
        self.assertEqual(1, len(response_body["results"]))
        self.assertEqual("MIT License", response_body["results"][0]["name"])
        self.assertEqual("MIT", response_body["results"][0]["code"])

    def test_list_licenses_filter_by_multiple_codes_should_return_filtered_licenses(self):
        # Arrange
        baker.make(License, name="MIT License", code="MIT", short_name="MIT")
        baker.make(License, name="Apache License 2.0", code="Apache-2.0", short_name="Apache 2.0")
        baker.make(License, name="GPL v3", code="GPL-3.0", short_name="GPL 3.0")

        # Act
        response = self.client.get(
            "/content/licenses/?code=MIT&code=Apache-2.0",
            format="json",
        )

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        response_body = response.json()
        self.assertEqual(2, len(response_body["results"]))
        codes = [license["code"] for license in response_body["results"]]
        self.assertIn("MIT", codes)
        self.assertIn("Apache-2.0", codes)

    def test_list_licenses_filter_by_is_default_true_should_return_default_licenses(self):
        # Arrange
        baker.make(License, name="Default License", code="DEFAULT", short_name="Default", is_default=True)
        baker.make(License, name="Regular License", code="REGULAR", short_name="Regular", is_default=False)

        # Act
        response = self.client.get("/content/licenses/", data={"is_default": True}, format="json")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        response_body = response.json()
        self.assertEqual(1, len(response_body["results"]))
        self.assertEqual("Default License", response_body["results"][0]["name"])
        self.assertTrue(response_body["results"][0]["is_default"])

    def test_list_licenses_filter_by_is_default_false_should_return_non_default_licenses(self):
        # Arrange
        baker.make(License, name="Default License", code="DEFAULT", short_name="Default", is_default=True)
        baker.make(License, name="Regular License", code="REGULAR", short_name="Regular", is_default=False)

        # Act
        response = self.client.get("/content/licenses/", data={"is_default": False}, format="json")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        response_body = response.json()
        self.assertEqual(1, len(response_body["results"]))
        self.assertEqual("Regular License", response_body["results"][0]["name"])
        self.assertFalse(response_body["results"][0]["is_default"])

    def test_list_licenses_order_by_code_ascending_should_return_sorted_licenses(self):
        # Arrange
        baker.make(License, name="License C", code="C", short_name="C")
        baker.make(License, name="License A", code="A", short_name="A")
        baker.make(License, name="License B", code="B", short_name="B")

        # Act
        response = self.client.get("/content/licenses/", data={"ordering": "code"}, format="json")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        response_body = response.json()
        self.assertEqual(3, len(response_body["results"]))
        self.assertEqual("A", response_body["results"][0]["code"])
        self.assertEqual("B", response_body["results"][1]["code"])
        self.assertEqual("C", response_body["results"][2]["code"])

    def test_list_licenses_when_search_should_return_filtered_licenses_by_all_fields(self):
        """Test search functionality across code, name, short_name fields and partial matches."""
        # Arrange
        baker.make(License, name="MIT License", code="MIT", short_name="MIT")
        baker.make(License, name="Apache License 2.0", code="Apache-2.0", short_name="Apache")
        baker.make(License, name="GPL License v3", code="GPL-3.0", short_name="GPL v3")
        baker.make(License, name="Creative Commons Attribution 4.0", code="CC-BY-4.0", short_name="CC BY 4.0")
        baker.make(License, name="Creative Commons ShareAlike 4.0", code="CC-SA-4.0", short_name="CC SA 4.0")

        # Test search by code
        response = self.client.get("/content/licenses/", data={"search": "MIT"}, format="json")
        self.assertEqual(200, response.status_code, response.content)
        response_body = response.json()
        self.assertEqual(1, len(response_body["results"]))
        self.assertEqual("MIT License", response_body["results"][0]["name"])

        # Test search by name
        response = self.client.get("/content/licenses/", data={"search": "Apache"}, format="json")
        self.assertEqual(200, response.status_code, response.content)
        response_body = response.json()
        self.assertEqual(1, len(response_body["results"]))
        self.assertEqual("Apache License 2.0", response_body["results"][0]["name"])

        # Test search by short_name
        response = self.client.get("/content/licenses/", data={"search": "GPL"}, format="json")
        self.assertEqual(200, response.status_code, response.content)
        response_body = response.json()
        self.assertEqual(1, len(response_body["results"]))
        self.assertEqual("GPL License v3", response_body["results"][0]["name"])

        # Test partial match
        response = self.client.get("/content/licenses/", data={"search": "Creative"}, format="json")
        self.assertEqual(200, response.status_code, response.content)
        response_body = response.json()
        self.assertEqual(2, len(response_body["results"]))
        names = [license["name"] for license in response_body["results"]]
        self.assertIn("Creative Commons Attribution 4.0", names)
        self.assertIn("Creative Commons ShareAlike 4.0", names)

    def test_list_licenses_with_combined_filters_should_return_filtered_licenses(self):
        # Arrange
        baker.make(License, name="Default MIT", code="MIT", short_name="MIT", is_default=True)
        baker.make(License, name="Default Apache", code="Apache-2.0", short_name="Apache", is_default=True)
        baker.make(License, name="Regular GPL", code="GPL-3.0", short_name="GPL", is_default=False)

        # Act
        response = self.client.get("/content/licenses/", data={"is_default": True, "search": "MIT"}, format="json")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        response_body = response.json()
        self.assertEqual(1, len(response_body["results"]))
        self.assertEqual("Default MIT", response_body["results"][0]["name"])
        self.assertTrue(response_body["results"][0]["is_default"])

    def test_list_licenses_response_structure_should_match_expected_schema(self):
        # Arrange
        baker.make(License, name="Test License", code="TEST", short_name="Test", is_default=False)

        # Act
        response = self.client.get("/content/licenses/", format="json")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        response_body = response.json()
        self.assertIn("results", response_body)
        self.assertEqual(1, len(response_body["results"]))

        license_data = response_body["results"][0]
        required_fields = ["id", "code", "name", "short_name", "is_default"]
        for field in required_fields:
            self.assertIn(field, license_data, f"Missing required field: {field}")

        # Verify field types
        self.assertIsInstance(license_data["id"], str)  # UUID as string
        self.assertIsInstance(license_data["code"], str)
        self.assertIsInstance(license_data["name"], str)
        self.assertIsInstance(license_data["short_name"], str)
        self.assertIsInstance(license_data["is_default"], bool)
