from model_bakery import baker

from apps.content.models import Asset, CategoryChoice, StatusChoice
from apps.core.permissions import PermissionChoice
from apps.core.tests import BaseTestCase
from apps.publishers.models import Publisher
from apps.users.models import User


class TranslationDeleteTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.publisher = baker.make(Publisher, name="Test Publisher")
        self.translation = baker.make(
            Asset,
            category=CategoryChoice.TRANSLATION,
            publisher=self.publisher,
            status=StatusChoice.READY,
            name="Translation to Delete",
            description="Will be deleted",
        )

        self.user = User.objects.create_user(email="testuser@example.com", name="Test User")

    def test_delete_translation_where_valid_slug_should_return_204(self):
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_DELETE_TRANSLATION)
        translation_slug = self.translation.slug

        response = self.client.delete(f"/portal/translations/{translation_slug}/")

        self.assertEqual(204, response.status_code)

        # Verify asset was deleted
        self.assertFalse(Asset.objects.filter(slug=translation_slug).exists())

    def test_delete_translation_where_not_found_should_return_404(self):
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_DELETE_TRANSLATION)
        response = self.client.delete("/portal/translations/nonexistent-slug/")

        self.assertEqual(404, response.status_code, response.content)
        body = response.json()
        self.assertEqual("translation_not_found", body["error_name"])

    def test_delete_translation_where_unauthenticated_should_return_401(self):
        response = self.client.delete(f"/portal/translations/{self.translation.slug}/")

        self.assertEqual(401, response.status_code, response.content)

        # Verify nothing was deleted
        self.assertTrue(Asset.objects.filter(slug=self.translation.slug).exists())

    def test_delete_translation_where_user_lacks_permission_should_return_403(self):
        user_without_permission = User.objects.create_user(email="noperm@example.com", name="No Permission User")
        self.authenticate_user(user_without_permission)
        response = self.client.delete(f"/portal/translations/{self.translation.slug}/")
        self.assertEqual(403, response.status_code)
        self.assertEqual("permission_denied", response.json()["error_name"])

        # Verify nothing was deleted
        self.assertTrue(Asset.objects.filter(slug=self.translation.slug).exists())
