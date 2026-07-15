from model_bakery import baker

from apps.content.models import Asset, CategoryChoice, Reciter, StatusChoice
from apps.core.tests.base import BaseTestCase


class ReciterDetailTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.reciter = Reciter.objects.create(
            name="Test Reciter",
            name_en="Test Reciter",
            name_ar="مقرئ تجريبي",
            slug="test-reciter",
            bio_en="Test Bio",
            bio_ar="سيرة تجريبية",
            nationality="SA",
        )

    def test_get_reciter_where_exists_should_return_200(self):
        # Act
        response = self.client.get(f"/cms-api/reciters/{self.reciter.slug}/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual(self.reciter.id, body["id"])
        self.assertEqual("Test Reciter", body["name_en"])
        self.assertEqual("مقرئ تجريبي", body["name_ar"])
        self.assertEqual("Test Bio", body["bio_en"])
        self.assertEqual("سيرة تجريبية", body["bio_ar"])
        self.assertEqual("test-reciter", body["slug"])
        self.assertEqual("SA", body["nationality"])
        self.assertIn("created_at", body)
        self.assertIn("updated_at", body)

    def test_get_reciter_where_unauthenticated_should_return_200(self):
        # Arrange — no authenticate_user() call: client stays anonymous

        # Act
        response = self.client.get(f"/cms-api/reciters/{self.reciter.slug}/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)

    def test_get_reciter_where_non_existent_slug_should_return_404(self):
        # Act
        response = self.client.get("/cms-api/reciters/does-not-exist/")

        # Assert
        self.assertEqual(404, response.status_code, response.content)
        self.assertEqual("reciter_not_found", response.json()["error_name"])

    def test_get_reciter_where_inactive_should_return_404(self):
        # Arrange — inactive reciters must not be publicly viewable, matching the list endpoint
        inactive_reciter = baker.make(Reciter, name="Inactive Reciter", slug="inactive-reciter", is_active=False)

        # Act
        response = self.client.get(f"/cms-api/reciters/{inactive_reciter.slug}/")

        # Assert
        self.assertEqual(404, response.status_code, response.content)
        self.assertEqual("reciter_not_found", response.json()["error_name"])

    def test_get_reciter_where_nationality_missing_should_return_null(self):
        # Arrange
        reciter = baker.make(Reciter, name="No Nationality Reciter", slug="no-nationality-reciter")

        # Act
        response = self.client.get(f"/cms-api/reciters/{reciter.slug}/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertIsNone(response.json()["nationality"])

    def test_get_reciter_recitations_count_should_only_count_ready_recitation_assets(self):
        # Arrange
        riwayah = baker.make("content.Riwayah", name="Test Riwayah")
        baker.make(
            Asset,
            category=CategoryChoice.RECITATION,
            reciter=self.reciter,
            riwayah=riwayah,
            status=StatusChoice.READY,
        )
        baker.make(
            Asset,
            category=CategoryChoice.RECITATION,
            reciter=self.reciter,
            riwayah=riwayah,
            status=StatusChoice.DRAFT,
        )

        # Act
        response = self.client.get(f"/cms-api/reciters/{self.reciter.slug}/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual(1, response.json()["recitations_count"])

    def test_get_reciter_where_date_of_death_present_should_be_returned(self):
        # Arrange
        self.reciter.date_of_death = "2020-01-15"
        self.reciter.save()

        # Act
        response = self.client.get(f"/cms-api/reciters/{self.reciter.slug}/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual("2020-01-15", response.json()["date_of_death"])
