from model_bakery import baker

from apps.content.models import Reciter
from apps.core.tests import BaseTestCase
from apps.users.models import User


class ReciterCreateTest(BaseTestCase):
    """Tests for the reciter creation endpoint."""

    def setUp(self):
        """Set up test fixtures."""
        super().setUp()
        self.user = baker.make(User, email="test@example.com", is_active=True)

    def test_create_reciter_should_return_201(self):
        """Test creating a reciter with valid data returns 201."""
        self.authenticate_user(self.user)
        response = self.client.post(
            "/cms-api/reciters/",
            data={
                "name": "Test Reciter",
                "name_ar": "قارئ تجريبي",
                "name_en": "Test Reciter EN",
                "nationality": "Saudi",
                "bio": "A test reciter.",
            },
            content_type="application/json",
        )
        self.assertEqual(201, response.status_code, response.content)
        body = response.json()
        self.assertEqual("Test Reciter", body["name"])
        self.assertEqual("Saudi", body["nationality"])
        self.assertTrue(body["slug"])

    def test_create_reciter_where_name_blank_should_return_422(self):
        """Test creating a reciter with blank name returns validation error."""
        self.authenticate_user(self.user)
        response = self.client.post(
            "/cms-api/reciters/",
            data={"name": "   ", "name_ar": "عربي", "name_en": "English"},
            content_type="application/json",
        )
        self.assertEqual(422, response.status_code, response.content)

    def test_create_reciter_where_name_exists_should_return_409(self):
        """Test creating a reciter with duplicate name returns 409."""
        self.authenticate_user(self.user)
        baker.make(Reciter, name="Existing Reciter", slug="existing-reciter")
        response = self.client.post(
            "/cms-api/reciters/",
            data={
                "name": "Existing Reciter",
                "name_ar": "قارئ موجود",
                "name_en": "Existing Reciter EN",
            },
            content_type="application/json",
        )
        self.assertEqual(409, response.status_code, response.content)
        body = response.json()
        self.assertEqual("RECITER_ALREADY_EXISTS", body["error_name"])

    def test_create_reciter_where_unauthenticated_should_return_401(self):
        """Test creating a reciter without auth returns 401."""
        response = self.client.post(
            "/cms-api/reciters/",
            data={"name": "Test", "name_ar": "تست", "name_en": "Test EN"},
            content_type="application/json",
        )
        self.assertEqual(401, response.status_code, response.content)

    def test_create_reciter_where_name_ar_blank_should_return_422(self):
        """Test creating a reciter with blank name_ar returns validation error."""
        self.authenticate_user(self.user)
        response = self.client.post(
            "/cms-api/reciters/",
            data={"name": "Valid", "name_ar": "   ", "name_en": "Valid EN"},
            content_type="application/json",
        )
        self.assertEqual(422, response.status_code, response.content)

    def test_create_reciter_where_missing_name_ar_should_return_422(self):
        """Test creating a reciter without required name_ar returns validation error."""
        self.authenticate_user(self.user)
        response = self.client.post(
            "/cms-api/reciters/",
            data={"name": "Valid", "name_en": "Valid EN"},
            content_type="application/json",
        )
        self.assertEqual(422, response.status_code, response.content)


class ReciterListTest(BaseTestCase):
    """Tests for the reciter list endpoint."""

    def test_list_reciters_should_return_all_reciters(self):
        """Test listing reciters returns paginated results."""
        baker.make(Reciter, name="Reciter A", slug="reciter-a")
        baker.make(Reciter, name="Reciter B", slug="reciter-b")
        response = self.client.get("/cms-api/reciters/")
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertIn("results", body)
        self.assertEqual(2, len(body["results"]))

    def test_list_reciters_where_filter_by_nationality_should_return_filtered(self):
        """Test filtering reciters by nationality."""
        baker.make(Reciter, name="R1", slug="r1", nationality="Saudi")
        baker.make(Reciter, name="R2", slug="r2", nationality="Egyptian")
        response = self.client.get("/cms-api/reciters/?nationality=Saudi")
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual(1, len(body["results"]))
        self.assertEqual("Saudi", body["results"][0]["nationality"])


class ReciterGetTest(BaseTestCase):
    """Tests for the reciter detail endpoint."""

    def setUp(self):
        """Set up test fixtures."""
        super().setUp()

    def test_get_reciter_should_return_reciter(self):
        """Test retrieving a reciter by ID returns the reciter."""
        reciter = baker.make(Reciter, name="Test Reciter", slug="test-reciter")
        response = self.client.get(f"/cms-api/reciters/{reciter.id}/")
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual("Test Reciter", body["name"])

    def test_get_reciter_where_not_found_should_return_404(self):
        """Test retrieving a non-existent reciter returns 404."""
        response = self.client.get("/cms-api/reciters/99999/")
        self.assertEqual(404, response.status_code, response.content)
        body = response.json()
        self.assertEqual("RECITER_NOT_FOUND", body["error_name"])


class ReciterUpdateTest(BaseTestCase):
    """Tests for the reciter update endpoint."""

    def setUp(self):
        """Set up test fixtures."""
        super().setUp()
        self.user = baker.make(User, email="test@example.com", is_active=True)

    def test_update_reciter_should_return_updated_reciter(self):
        """Test updating a reciter returns the updated reciter."""
        self.authenticate_user(self.user)
        reciter = baker.make(Reciter, name="Old Name", slug="old-name")
        response = self.client.patch(
            f"/cms-api/reciters/{reciter.id}/",
            data={"nationality": "Egyptian"},
            content_type="application/json",
        )
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual("Egyptian", body["nationality"])

    def test_update_reciter_where_not_found_should_return_404(self):
        """Test updating a non-existent reciter returns 404."""
        self.authenticate_user(self.user)
        response = self.client.patch(
            "/cms-api/reciters/99999/",
            data={"name": "New Name"},
            content_type="application/json",
        )
        self.assertEqual(404, response.status_code, response.content)

    def test_update_reciter_where_blank_name_should_return_422(self):
        """Test updating a reciter with blank name returns validation error."""
        self.authenticate_user(self.user)
        reciter = baker.make(Reciter, name="Test", slug="test")
        response = self.client.patch(
            f"/cms-api/reciters/{reciter.id}/",
            data={"name": "   "},
            content_type="application/json",
        )
        self.assertEqual(422, response.status_code, response.content)

    def test_update_reciter_where_unauthenticated_should_return_401(self):
        """Test updating a reciter without auth returns 401."""
        reciter = baker.make(Reciter, name="Test", slug="test")
        response = self.client.patch(
            f"/cms-api/reciters/{reciter.id}/",
            data={"name": "New"},
            content_type="application/json",
        )
        self.assertEqual(401, response.status_code, response.content)

    def test_update_reciter_where_null_nationality_should_return_422(self):
        """Test updating a reciter with null non-nullable field returns validation error."""
        self.authenticate_user(self.user)
        reciter = baker.make(Reciter, name="Test", slug="test")
        response = self.client.patch(
            f"/cms-api/reciters/{reciter.id}/",
            data={"nationality": None},
            content_type="application/json",
        )
        self.assertEqual(422, response.status_code, response.content)

    def test_update_reciter_where_duplicate_name_should_return_409(self):
        """Test updating a reciter with conflicting name returns 409."""
        self.authenticate_user(self.user)
        baker.make(Reciter, name="Existing", slug="existing")
        reciter = baker.make(Reciter, name="Other", slug="other")
        response = self.client.patch(
            f"/cms-api/reciters/{reciter.id}/",
            data={"name": "Existing"},
            content_type="application/json",
        )
        self.assertEqual(409, response.status_code, response.content)
        body = response.json()
        self.assertEqual("RECITER_CONFLICT", body["error_name"])
