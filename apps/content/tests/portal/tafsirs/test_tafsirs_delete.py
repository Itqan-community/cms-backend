from model_bakery import baker

from apps.content.models import Asset, CategoryChoice, StatusChoice
from apps.core.tests import BaseTestCase
from apps.publishers.models import Publisher
from apps.users.models import User


class TafsirDeleteTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.publisher = baker.make(Publisher, name="Test Publisher")
        self.tafsir = baker.make(
            Asset,
            category=CategoryChoice.TAFSIR,
            publisher=self.publisher,
            status=StatusChoice.READY,
            name="Tafsir to Delete",
            description="Will be deleted",
        )

        self.user = User.objects.create_user(email="testuser@example.com", name="Test User")

    def test_delete_tafsir_where_valid_slug_should_return_204(self):
        self.authenticate_user(self.user)
        tafsir_slug = self.tafsir.slug

        response = self.client.delete(f"/portal/tafsirs/{tafsir_slug}/")

        self.assertEqual(204, response.status_code)

        # Verify asset was deleted
        self.assertFalse(Asset.objects.filter(slug=tafsir_slug).exists())

    def test_delete_tafsir_where_not_found_should_return_404(self):
        self.authenticate_user(self.user)
        response = self.client.delete("/portal/tafsirs/nonexistent-slug/")

        self.assertEqual(404, response.status_code, response.content)
        body = response.json()
        self.assertEqual("tafsir_not_found", body["error_name"])

    def test_delete_tafsir_where_unauthenticated_should_return_401(self):
        response = self.client.delete(f"/portal/tafsirs/{self.tafsir.slug}/")

        self.assertEqual(401, response.status_code, response.content)

        # Verify nothing was deleted
        self.assertTrue(Asset.objects.filter(slug=self.tafsir.slug).exists())
