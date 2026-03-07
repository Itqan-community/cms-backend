from model_bakery import baker

from apps.core.tests import BaseTestCase
from apps.publishers.models import Publisher
from apps.users.models import User


class PublisherCreateTest(BaseTestCase):
    """Tests for the publisher creation endpoint."""

    def setUp(self):
        """Set up test fixtures."""
        super().setUp()
        self.user = baker.make(User, email="test@example.com", is_active=True)

    def test_create_publisher_should_return_201(self):
        """Test creating a publisher with valid data returns 201."""
        self.authenticate_user(self.user)
        response = self.client.post(
            "/portal/publishers/",
            data={
                "name": "Test Publisher",
                "description": "A test publisher.",
                "country": "Saudi Arabia",
            },
            content_type="application/json",
        )
        self.assertEqual(201, response.status_code, response.content)
        body = response.json()
        self.assertEqual("Test Publisher", body["name"])
        self.assertTrue(body["slug"])

    def test_create_publisher_where_name_blank_should_return_422(self):
        """Test creating a publisher with blank name returns validation error."""
        self.authenticate_user(self.user)
        response = self.client.post(
            "/portal/publishers/",
            data={"name": "   "},
            content_type="application/json",
        )
        self.assertEqual(422, response.status_code, response.content)

    def test_create_publisher_where_name_exists_should_return_409(self):
        """Test creating a publisher with duplicate name returns 409."""
        self.authenticate_user(self.user)
        baker.make(Publisher, name="Existing Publisher")
        response = self.client.post(
            "/portal/publishers/",
            data={"name": "Existing Publisher"},
            content_type="application/json",
        )
        self.assertEqual(409, response.status_code, response.content)
        body = response.json()
        self.assertEqual("PUBLISHER_ALREADY_EXISTS", body["error_name"])

    def test_create_publisher_where_unauthenticated_should_return_401(self):
        """Test creating a publisher without auth returns 401."""
        response = self.client.post(
            "/portal/publishers/",
            data={"name": "Test"},
            content_type="application/json",
        )
        self.assertEqual(401, response.status_code, response.content)


class PublisherListTest(BaseTestCase):
    """Tests for the publisher list endpoint."""

    def test_list_publishers_should_return_all_publishers(self):
        """Test listing publishers returns paginated results."""
        baker.make(Publisher, name="Publisher A")
        baker.make(Publisher, name="Publisher B")
        response = self.client.get("/portal/publishers/")
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertIn("results", body)
        self.assertEqual(2, len(body["results"]))

    def test_list_publishers_where_filter_by_country_should_return_filtered(self):
        """Test filtering publishers by country."""
        baker.make(Publisher, name="P1", country="Saudi Arabia")
        baker.make(Publisher, name="P2", country="Egypt")
        response = self.client.get("/portal/publishers/?country=Saudi")
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual(1, len(body["results"]))


class PublisherGetTest(BaseTestCase):
    """Tests for the publisher detail endpoint."""

    def test_get_publisher_should_return_publisher(self):
        """Test retrieving a publisher by ID returns the publisher."""
        publisher = baker.make(Publisher, name="Test Publisher")
        response = self.client.get(f"/portal/publishers/{publisher.id}/")
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual("Test Publisher", body["name"])

    def test_get_publisher_where_not_found_should_return_404(self):
        """Test retrieving a non-existent publisher returns 404."""
        response = self.client.get("/portal/publishers/99999/")
        self.assertEqual(404, response.status_code, response.content)
        body = response.json()
        self.assertEqual("PUBLISHER_NOT_FOUND", body["error_name"])


class PublisherUpdateTest(BaseTestCase):
    """Tests for the publisher update endpoints."""

    def setUp(self):
        """Set up test fixtures."""
        super().setUp()
        self.user = baker.make(User, email="test@example.com", is_active=True)

    def test_update_publisher_partial_should_return_updated(self):
        """Test partially updating a publisher returns the updated publisher."""
        self.authenticate_user(self.user)
        publisher = baker.make(Publisher, name="Old Name")
        response = self.client.patch(
            f"/portal/publishers/{publisher.id}/",
            data={"country": "Egypt"},
            content_type="application/json",
        )
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual("Egypt", body["country"])

    def test_update_publisher_where_not_found_should_return_404(self):
        """Test updating a non-existent publisher returns 404."""
        self.authenticate_user(self.user)
        response = self.client.patch(
            "/portal/publishers/99999/",
            data={"name": "New Name"},
            content_type="application/json",
        )
        self.assertEqual(404, response.status_code, response.content)

    def test_update_publisher_where_blank_name_should_return_422(self):
        """Test updating a publisher with blank name returns validation error."""
        self.authenticate_user(self.user)
        publisher = baker.make(Publisher, name="Test")
        response = self.client.patch(
            f"/portal/publishers/{publisher.id}/",
            data={"name": "   "},
            content_type="application/json",
        )
        self.assertEqual(422, response.status_code, response.content)

    def test_update_publisher_full_should_return_updated(self):
        """Test fully updating a publisher returns the updated publisher."""
        self.authenticate_user(self.user)
        publisher = baker.make(Publisher, name="Old Name")
        response = self.client.put(
            f"/portal/publishers/{publisher.id}/",
            data={"name": "New Name", "description": "Updated desc"},
            content_type="application/json",
        )
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual("New Name", body["name"])


class PublisherDeleteTest(BaseTestCase):
    """Tests for the publisher delete endpoint."""

    def setUp(self):
        """Set up test fixtures."""
        super().setUp()
        self.user = baker.make(User, email="test@example.com", is_active=True)

    def test_delete_publisher_should_return_204(self):
        """Test deleting a publisher returns 204."""
        self.authenticate_user(self.user)
        publisher = baker.make(Publisher, name="To Delete")
        response = self.client.delete(f"/portal/publishers/{publisher.id}/")
        self.assertEqual(204, response.status_code, response.content)
        self.assertFalse(Publisher.objects.filter(id=publisher.id).exists())

    def test_delete_publisher_where_not_found_should_return_404(self):
        """Test deleting a non-existent publisher returns 404."""
        self.authenticate_user(self.user)
        response = self.client.delete("/portal/publishers/99999/")
        self.assertEqual(404, response.status_code, response.content)

    def test_delete_publisher_where_unauthenticated_should_return_401(self):
        """Test deleting a publisher without auth returns 401."""
        publisher = baker.make(Publisher, name="Test")
        response = self.client.delete(f"/portal/publishers/{publisher.id}/")
        self.assertEqual(401, response.status_code, response.content)
