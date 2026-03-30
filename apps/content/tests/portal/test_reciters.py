from model_bakery import baker

from apps.content.models import Nationality, Reciter
from apps.core.tests import BaseTestCase
from apps.users.models import User


class ReciterCreateTest(BaseTestCase):

    def setUp(self) -> None:
        super().setUp()
        self.user = baker.make(User, email="test@example.com", is_active=True)
        self.nationality = baker.make(Nationality, code="SA", name="Saudi Arabia")

    def test_create_reciter_where_valid_data_should_return_201(self) -> None:
        self.authenticate_user(self.user)
        response = self.client.post(
            "/portal/reciters/",
            data={
                "name": "Test Reciter",
                "name_ar": "قارئ تجريبي",
                "name_en": "Test Reciter EN",
                "nationality_id": self.nationality.id,
                "bio": "A test reciter.",
            },
            content_type="application/json",
        )
        self.assertEqual(201, response.status_code, response.content)
        body = response.json()
        self.assertEqual("Test Reciter EN", body["name"])
        self.assertEqual({"id": self.nationality.id, "name": "Saudi Arabia"}, body["nationality"])
        self.assertTrue(body["slug"])

    def test_create_reciter_where_no_nationality_should_return_201(self) -> None:
        self.authenticate_user(self.user)
        response = self.client.post(
            "/portal/reciters/",
            data={"name": "Test Reciter", "name_ar": "قارئ تجريبي", "name_en": "Test Reciter EN"},
            content_type="application/json",
        )
        self.assertEqual(201, response.status_code, response.content)
        self.assertIsNone(response.json()["nationality"])

    def test_create_reciter_where_name_blank_should_return_400(self) -> None:
        self.authenticate_user(self.user)
        response = self.client.post(
            "/portal/reciters/",
            data={"name": "   ", "name_ar": "عربي", "name_en": "English"},
            content_type="application/json",
        )
        self.assertEqual(400, response.status_code, response.content)

    def test_create_reciter_where_name_exists_should_return_409(self) -> None:
        self.authenticate_user(self.user)
        baker.make(Reciter, name="Existing Reciter", slug="existing-reciter")
        response = self.client.post(
            "/portal/reciters/",
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

    def test_create_reciter_where_unauthenticated_should_return_401(self) -> None:
        response = self.client.post(
            "/portal/reciters/",
            data={"name": "Test", "name_ar": "تست", "name_en": "Test EN"},
            content_type="application/json",
        )
        self.assertEqual(401, response.status_code, response.content)

    def test_create_reciter_where_name_ar_blank_should_return_400(self) -> None:
        self.authenticate_user(self.user)
        response = self.client.post(
            "/portal/reciters/",
            data={"name": "Valid", "name_ar": "   ", "name_en": "Valid EN"},
            content_type="application/json",
        )
        self.assertEqual(400, response.status_code, response.content)

    def test_create_reciter_where_missing_name_ar_should_return_400(self) -> None:
        self.authenticate_user(self.user)
        response = self.client.post(
            "/portal/reciters/",
            data={"name": "Valid", "name_en": "Valid EN"},
            content_type="application/json",
        )
        self.assertEqual(400, response.status_code, response.content)

    def test_create_reciter_where_unknown_nationality_id_should_return_404(self) -> None:
        self.authenticate_user(self.user)
        response = self.client.post(
            "/portal/reciters/",
            data={"name": "Valid", "name_ar": "صالح", "name_en": "Valid EN", "nationality_id": 99999},
            content_type="application/json",
        )
        self.assertEqual(404, response.status_code, response.content)
        body = response.json()
        self.assertEqual("NATIONALITY_NOT_FOUND", body["error_name"])


class ReciterListTest(BaseTestCase):

    def setUp(self) -> None:
        super().setUp()
        self.user = baker.make(User, email="listtest@example.com", is_active=True)
        self.authenticate_user(self.user)

    def test_list_reciters_where_reciters_exist_should_return_all(self) -> None:
        baker.make(Reciter, name="Reciter A", slug="reciter-a")
        baker.make(Reciter, name="Reciter B", slug="reciter-b")
        response = self.client.get("/portal/reciters/")
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertIn("results", body)
        self.assertEqual(2, len(body["results"]))

    def test_list_reciters_where_filter_by_nationality_should_return_filtered(self) -> None:
        nationality_sa = baker.make(Nationality, code="SA", name="Saudi Arabia")
        nationality_eg = baker.make(Nationality, code="EG", name="Egypt")
        baker.make(Reciter, name="R1", slug="r1", nationality=nationality_sa)
        baker.make(Reciter, name="R2", slug="r2", nationality=nationality_eg)
        response = self.client.get("/portal/reciters/?nationality=Saudi")
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual(1, len(body["results"]))
        self.assertEqual({"id": nationality_sa.id, "name": "Saudi Arabia"}, body["results"][0]["nationality"])


class ReciterGetTest(BaseTestCase):

    def setUp(self) -> None:
        super().setUp()
        self.user = baker.make(User, email="gettest@example.com", is_active=True)
        self.authenticate_user(self.user)

    def test_get_reciter_where_exists_should_return_reciter(self) -> None:
        reciter = baker.make(Reciter, name="Test Reciter", slug="test-reciter")
        response = self.client.get(f"/portal/reciters/{reciter.id}/")
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual("Test Reciter", body["name"])
        self.assertIsNone(body["nationality"])

    def test_get_reciter_where_not_found_should_return_404(self) -> None:
        response = self.client.get("/portal/reciters/99999/")
        self.assertEqual(404, response.status_code, response.content)
        body = response.json()
        self.assertEqual("RECITER_NOT_FOUND", body["error_name"])


class ReciterUpdateTest(BaseTestCase):

    def setUp(self) -> None:
        super().setUp()
        self.user = baker.make(User, email="test@example.com", is_active=True)
        self.nationality = baker.make(Nationality, code="EG", name="Egypt")

    def test_update_reciter_where_valid_data_should_return_updated(self) -> None:
        self.authenticate_user(self.user)
        reciter = baker.make(Reciter, name="Old Name", slug="old-name")
        response = self.client.patch(
            f"/portal/reciters/{reciter.id}/",
            data={"nationality_id": self.nationality.id},
            content_type="application/json",
        )
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual({"id": self.nationality.id, "name": "Egypt"}, body["nationality"])

    def test_update_reciter_where_not_found_should_return_404(self) -> None:
        self.authenticate_user(self.user)
        response = self.client.patch(
            "/portal/reciters/99999/",
            data={"name": "New Name"},
            content_type="application/json",
        )
        self.assertEqual(404, response.status_code, response.content)

    def test_update_reciter_where_blank_name_should_return_400(self) -> None:
        self.authenticate_user(self.user)
        reciter = baker.make(Reciter, name="Test", slug="test")
        response = self.client.patch(
            f"/portal/reciters/{reciter.id}/",
            data={"name": "   "},
            content_type="application/json",
        )
        self.assertEqual(400, response.status_code, response.content)

    def test_update_reciter_where_unauthenticated_should_return_401(self) -> None:
        reciter = baker.make(Reciter, name="Test", slug="test")
        response = self.client.patch(
            f"/portal/reciters/{reciter.id}/",
            data={"name": "New"},
            content_type="application/json",
        )
        self.assertEqual(401, response.status_code, response.content)

    def test_update_reciter_where_null_nationality_id_should_clear_nationality(self) -> None:
        self.authenticate_user(self.user)
        reciter = baker.make(Reciter, name="Test", slug="test", nationality=self.nationality)
        response = self.client.patch(
            f"/portal/reciters/{reciter.id}/",
            data={"nationality_id": None},
            content_type="application/json",
        )
        self.assertEqual(200, response.status_code, response.content)
        self.assertIsNone(response.json()["nationality"])

    def test_update_reciter_where_unknown_nationality_id_should_return_404(self) -> None:
        self.authenticate_user(self.user)
        reciter = baker.make(Reciter, name="Test", slug="test")
        response = self.client.patch(
            f"/portal/reciters/{reciter.id}/",
            data={"nationality_id": 99999},
            content_type="application/json",
        )
        self.assertEqual(404, response.status_code, response.content)
        body = response.json()
        self.assertEqual("NATIONALITY_NOT_FOUND", body["error_name"])

    def test_update_reciter_where_duplicate_name_should_return_409(self) -> None:
        self.authenticate_user(self.user)
        baker.make(Reciter, name="Existing", slug="existing")
        reciter = baker.make(Reciter, name="Other", slug="other")
        response = self.client.patch(
            f"/portal/reciters/{reciter.id}/",
            data={"name": "Existing"},
            content_type="application/json",
        )
        self.assertEqual(409, response.status_code, response.content)
        body = response.json()
        self.assertEqual("RECITER_CONFLICT", body["error_name"])
