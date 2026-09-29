from model_bakery import baker

from apps.content.models import Asset, AssetTemplateChoice, LicenseChoice, MushafLayout, StatusChoice
from apps.content.services.tafsir import TafsirService
from apps.content.services.translation import TranslationService
from apps.core.ninja_utils.errors import ItqanError
from apps.core.permissions import PermissionChoice
from apps.core.tests.base import BaseTestCase
from apps.publishers.models import Publisher
from apps.users.models import User


class TranslationTemplateCreateTests(BaseTestCase):
    def _payload(self, **overrides):
        publisher = baker.make(Publisher)
        payload = {
            "name_en": "Test Translation",
            "description_en": "d",
            "license": LicenseChoice.CC0.value,
            "language": "en",
            "publisher_id": publisher.id,
            "template": AssetTemplateChoice.AYAH.value,
        }
        payload.update(overrides)
        return payload

    def test_create_where_template_is_page_and_no_layout_should_return_400(self):
        # Arrange
        self.user = User.objects.create_user(email="admin@example.com", name="Admin", is_staff=True)
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_CREATE_TRANSLATION)

        # Act
        response = self.client.post(
            "/portal/translations/",
            data=self._payload(template=AssetTemplateChoice.PAGE.value),
        )

        # Assert
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error_name"], "mushaf_layout_required")

    def test_create_where_template_is_ayah_and_layout_given_should_return_400(self):
        # Arrange
        self.user = User.objects.create_user(email="admin@example.com", name="Admin", is_staff=True)
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_CREATE_TRANSLATION)
        layout = baker.make(MushafLayout, name="Madani 604", page_count=604)

        # Act
        response = self.client.post(
            "/portal/translations/",
            data=self._payload(mushaf_layout_id=layout.id),
        )

        # Assert
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error_name"], "mushaf_layout_not_allowed")

    def test_create_where_layout_does_not_exist_should_return_404(self):
        # Arrange
        self.user = User.objects.create_user(email="admin@example.com", name="Admin", is_staff=True)
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_CREATE_TRANSLATION)

        # Act
        response = self.client.post(
            "/portal/translations/",
            data=self._payload(template=AssetTemplateChoice.PAGE.value, mushaf_layout_id=999999),
        )

        # Assert
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error_name"], "mushaf_layout_not_found")

    def test_create_where_valid_page_template_should_persist_template_and_layout(self):
        # Arrange
        self.user = User.objects.create_user(email="admin@example.com", name="Admin", is_staff=True)
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_CREATE_TRANSLATION)
        layout = baker.make(MushafLayout, name="Madani 604", page_count=604)

        # Act
        response = self.client.post(
            "/portal/translations/",
            data=self._payload(template=AssetTemplateChoice.PAGE.value, mushaf_layout_id=layout.id),
        )

        # Assert
        self.assertEqual(response.status_code, 201)
        asset = Asset.objects.get(pk=response.json()["id"])
        self.assertEqual(asset.template, AssetTemplateChoice.PAGE)
        self.assertEqual(asset.mushaf_layout_id, layout.id)
        self.assertEqual(response.json()["mushaf_layout"]["id"], layout.id)

    def test_update_where_template_sent_should_be_ignored_by_the_schema(self):
        # Arrange
        self.user = User.objects.create_user(email="admin@example.com", name="Admin", is_staff=True)
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_UPDATE_TRANSLATION)
        asset = baker.make(
            Asset,
            category="translation",
            template=AssetTemplateChoice.AYAH,
            license=LicenseChoice.CC0,
            status=StatusChoice.READY,
        )

        # Act
        response = self.client.put(
            f"/portal/translations/{asset.slug}/",
            data={
                "name_en": "Renamed",
                "license": LicenseChoice.CC0.value,
                "language": asset.language,
                "publisher_id": asset.publisher_id,
                "template": AssetTemplateChoice.WORD.value,
            },
            content_type="application/json",
        )

        # Assert
        self.assertEqual(response.status_code, 200)
        asset.refresh_from_db()
        self.assertEqual(asset.template, AssetTemplateChoice.AYAH)

    def test_detail_where_asset_has_template_should_expose_it(self):
        # Arrange
        self.user = User.objects.create_user(email="admin@example.com", name="Admin", is_staff=True)
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_READ_TRANSLATION)
        asset = baker.make(
            Asset,
            category="translation",
            template=AssetTemplateChoice.WORD,
            license=LicenseChoice.CC0,
            status=StatusChoice.READY,
        )

        # Act
        response = self.client.get(f"/portal/translations/{asset.slug}/")

        # Assert
        self.assertEqual(response.json()["template"], "word")
        self.assertIsNone(response.json()["mushaf_layout"])

    def test_update_translation_where_fields_carry_template_should_raise_immutable_error(self):
        # Arrange
        asset = baker.make(
            Asset,
            category="translation",
            template=AssetTemplateChoice.AYAH,
            license=LicenseChoice.CC0,
            status=StatusChoice.READY,
        )

        # Act & Assert
        with self.assertRaises(ItqanError) as ctx:
            TranslationService().update_translation(asset.slug, fields={"template": AssetTemplateChoice.WORD})
        self.assertEqual(ctx.exception.error_name, "asset_template_immutable")
        self.assertEqual(ctx.exception.status_code, 400)

    def test_update_translation_where_fields_carry_mushaf_layout_id_should_raise_immutable_error(self):
        # Arrange
        asset = baker.make(
            Asset,
            category="translation",
            template=AssetTemplateChoice.AYAH,
            license=LicenseChoice.CC0,
            status=StatusChoice.READY,
        )
        layout = baker.make(MushafLayout, name="Madani 604", page_count=604)

        # Act & Assert
        with self.assertRaises(ItqanError) as ctx:
            TranslationService().update_translation(asset.slug, fields={"mushaf_layout_id": layout.id})
        self.assertEqual(ctx.exception.error_name, "asset_template_immutable")
        self.assertEqual(ctx.exception.status_code, 400)


class TafsirTemplateCreateTests(BaseTestCase):
    def _payload(self, **overrides):
        publisher = baker.make(Publisher)
        payload = {
            "name_en": "Test Tafsir",
            "description_en": "d",
            "license": LicenseChoice.CC0.value,
            "language": "ar",
            "publisher_id": publisher.id,
            "template": AssetTemplateChoice.AYAH.value,
        }
        payload.update(overrides)
        return payload

    def test_create_where_template_is_page_and_no_layout_should_return_400(self):
        # Arrange
        self.user = User.objects.create_user(email="admin@example.com", name="Admin", is_staff=True)
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_CREATE_TAFSIR)

        # Act
        response = self.client.post(
            "/portal/tafsirs/",
            data=self._payload(template=AssetTemplateChoice.PAGE.value),
        )

        # Assert
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error_name"], "mushaf_layout_required")

    def test_create_where_template_is_ayah_and_layout_given_should_return_400(self):
        # Arrange
        self.user = User.objects.create_user(email="admin@example.com", name="Admin", is_staff=True)
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_CREATE_TAFSIR)
        layout = baker.make(MushafLayout, name="Madani 604", page_count=604)

        # Act
        response = self.client.post(
            "/portal/tafsirs/",
            data=self._payload(mushaf_layout_id=layout.id),
        )

        # Assert
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error_name"], "mushaf_layout_not_allowed")

    def test_create_where_layout_does_not_exist_should_return_404(self):
        # Arrange
        self.user = User.objects.create_user(email="admin@example.com", name="Admin", is_staff=True)
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_CREATE_TAFSIR)

        # Act
        response = self.client.post(
            "/portal/tafsirs/",
            data=self._payload(template=AssetTemplateChoice.PAGE.value, mushaf_layout_id=999999),
        )

        # Assert
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error_name"], "mushaf_layout_not_found")

    def test_create_where_valid_page_template_should_persist_template_and_layout(self):
        # Arrange
        self.user = User.objects.create_user(email="admin@example.com", name="Admin", is_staff=True)
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_CREATE_TAFSIR)
        layout = baker.make(MushafLayout, name="Madani 604", page_count=604)

        # Act
        response = self.client.post(
            "/portal/tafsirs/",
            data=self._payload(template=AssetTemplateChoice.PAGE.value, mushaf_layout_id=layout.id),
        )

        # Assert
        self.assertEqual(response.status_code, 201)
        asset = Asset.objects.get(pk=response.json()["id"])
        self.assertEqual(asset.template, AssetTemplateChoice.PAGE)
        self.assertEqual(asset.mushaf_layout_id, layout.id)
        self.assertEqual(response.json()["mushaf_layout"]["id"], layout.id)

    def test_update_where_template_sent_should_be_ignored_by_the_schema(self):
        # Arrange
        self.user = User.objects.create_user(email="admin@example.com", name="Admin", is_staff=True)
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_UPDATE_TAFSIR)
        asset = baker.make(
            Asset,
            category="tafsir",
            template=AssetTemplateChoice.AYAH,
            license=LicenseChoice.CC0,
            status=StatusChoice.READY,
        )

        # Act
        response = self.client.put(
            f"/portal/tafsirs/{asset.slug}/",
            data={
                "name_en": "Renamed",
                "license": LicenseChoice.CC0.value,
                "language": asset.language,
                "publisher_id": asset.publisher_id,
                "template": AssetTemplateChoice.WORD.value,
            },
        )

        # Assert
        self.assertEqual(response.status_code, 200)
        asset.refresh_from_db()
        self.assertEqual(asset.template, AssetTemplateChoice.AYAH)

    def test_detail_where_asset_has_template_should_expose_it(self):
        # Arrange
        self.user = User.objects.create_user(email="admin@example.com", name="Admin", is_staff=True)
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_READ_TAFSIR)
        asset = baker.make(
            Asset,
            category="tafsir",
            template=AssetTemplateChoice.WORD,
            license=LicenseChoice.CC0,
            status=StatusChoice.READY,
        )

        # Act
        response = self.client.get(f"/portal/tafsirs/{asset.slug}/")

        # Assert
        self.assertEqual(response.json()["template"], "word")
        self.assertIsNone(response.json()["mushaf_layout"])

    def test_update_tafsir_where_fields_carry_template_should_raise_immutable_error(self):
        # Arrange
        asset = baker.make(
            Asset,
            category="tafsir",
            template=AssetTemplateChoice.AYAH,
            license=LicenseChoice.CC0,
            status=StatusChoice.READY,
        )

        # Act & Assert
        with self.assertRaises(ItqanError) as ctx:
            TafsirService().update_tafsir(asset.slug, fields={"template": AssetTemplateChoice.WORD})
        self.assertEqual(ctx.exception.error_name, "asset_template_immutable")
        self.assertEqual(ctx.exception.status_code, 400)

    def test_update_tafsir_where_fields_carry_mushaf_layout_id_should_raise_immutable_error(self):
        # Arrange
        asset = baker.make(
            Asset,
            category="tafsir",
            template=AssetTemplateChoice.AYAH,
            license=LicenseChoice.CC0,
            status=StatusChoice.READY,
        )
        layout = baker.make(MushafLayout, name="Madani 604", page_count=604)

        # Act & Assert
        with self.assertRaises(ItqanError) as ctx:
            TafsirService().update_tafsir(asset.slug, fields={"mushaf_layout_id": layout.id})
        self.assertEqual(ctx.exception.error_name, "asset_template_immutable")
        self.assertEqual(ctx.exception.status_code, 400)
