"""Per-language gating of the portal content endpoints.

Every route that resolves a language enforces the member's assignment. Each one
is covered here rather than relying on the filtered language list, because a
version-scoped route takes an id and is not constrained by that list at all.
"""

from model_bakery import baker

from apps.content.models import (
    Asset,
    AssetLanguage,
    AssetTemplateChoice,
    AssetVersion,
    CategoryChoice,
    StatusChoice,
    VersionStateChoice,
)
from apps.core.permissions import PermissionChoice
from apps.core.tests.base import BaseTestCase
from apps.publishers.models import MemberLanguage, Publisher, PublisherMember
from apps.quran.models import Ayah, Sura
from apps.users.models import User


class AssetLanguageGatingTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.publisher = baker.make(Publisher, name="Test Publisher")
        self.translation = baker.make(
            Asset,
            category=CategoryChoice.TRANSLATION,
            template=AssetTemplateChoice.AYAH,
            publisher=self.publisher,
            status=StatusChoice.READY,
            slug="t1",
            language="ar",
        )
        self.fr = AssetLanguage.objects.create(asset=self.translation, language="fr")
        self.es = AssetLanguage.objects.create(asset=self.translation, language="es")
        self.sura = baker.make(Sura, id=1, name="الفاتحة", ayas_count=3)
        self.ayah = baker.make(Ayah, id=1, sura=self.sura, number_in_sura=1, text="a")

        # Assigned to 'fr' only, with full content-edit rights but no bypass.
        self.user = User.objects.create_user(email="editor@example.com", name="Editor", is_staff=True)
        self.membership = baker.make(
            PublisherMember,
            user=self.user,
            publisher=self.publisher,
            status=PublisherMember.StatusChoice.ACTIVE,
        )
        MemberLanguage.objects.create(member=self.membership, language="fr")

        self.es_version = baker.make(
            AssetVersion,
            asset=self.translation,
            asset_language=self.es,
            name="es-v1",
            state=VersionStateChoice.PUBLISHED,
        )

    def _authorise(self):
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_READ_TRANSLATION)
        self.give_permission(self.user, PermissionChoice.PORTAL_UPDATE_TRANSLATION)
        self.give_permission(self.user, PermissionChoice.PORTAL_EDIT_TRANSLATION_CONTENT)
        self.give_permission(self.user, PermissionChoice.PORTAL_DELETE_TRANSLATION)

    def _assert_language_not_assigned(self, response):
        self.assertEqual(403, response.status_code, response.content)
        self.assertEqual("language_not_assigned", response.json()["error_name"])

    def test_list_languages_where_assigned_to_one_should_hide_the_others(self):
        # Arrange
        self._authorise()

        # Act
        response = self.client.get(f"/portal/content/translations/{self.translation.slug}/languages/")

        # Assert — 'ar' (source) and 'es' are filtered out
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual(["fr"], [row["language"] for row in response.json()])

    def test_list_languages_where_bypass_permission_should_show_all(self):
        # Arrange
        self._authorise()
        self.give_permission(self.user, PermissionChoice.PORTAL_ACCESS_ALL_LANGUAGES)

        # Act
        response = self.client.get(f"/portal/content/translations/{self.translation.slug}/languages/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual({"ar", "fr", "es"}, {row["language"] for row in response.json()})

    def test_create_draft_where_language_not_assigned_should_return_403(self):
        # Arrange
        self._authorise()

        # Act
        response = self.client.post(
            f"/portal/content/translations/{self.translation.slug}/draft/",
            data={"language": "es"},
            content_type="application/json",
        )

        # Assert
        self._assert_language_not_assigned(response)

    def test_create_draft_where_source_language_not_assigned_should_return_403(self):
        # Arrange — the source is gated like any other language
        self._authorise()

        # Act
        response = self.client.post(
            f"/portal/content/translations/{self.translation.slug}/draft/",
            data={"language": "ar"},
            content_type="application/json",
        )

        # Assert
        self._assert_language_not_assigned(response)

    def test_create_draft_where_language_assigned_should_succeed(self):
        # Arrange
        self._authorise()

        # Act
        response = self.client.post(
            f"/portal/content/translations/{self.translation.slug}/draft/",
            data={"language": "fr"},
            content_type="application/json",
        )

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual("fr", response.json()["language"])

    def test_list_entries_where_version_language_not_assigned_should_return_403(self):
        # Arrange — a read, reached by version id rather than by language
        self._authorise()

        # Act
        response = self.client.get(
            f"/portal/content/translations/{self.translation.slug}/versions/{self.es_version.id}/entries/"
        )

        # Assert
        self._assert_language_not_assigned(response)

    def test_version_diff_where_version_language_not_assigned_should_return_403(self):
        # Arrange
        self._authorise()

        # Act
        response = self.client.get(
            f"/portal/content/translations/{self.translation.slug}/versions/{self.es_version.id}/diff/"
        )

        # Assert
        self._assert_language_not_assigned(response)

    def test_export_where_version_language_not_assigned_should_return_403(self):
        # Arrange
        self._authorise()

        # Act
        response = self.client.get(
            f"/portal/content/translations/{self.translation.slug}/versions/{self.es_version.id}/export/"
        )

        # Assert
        self._assert_language_not_assigned(response)

    def test_patch_entries_where_version_language_not_assigned_should_return_403(self):
        # Arrange
        self._authorise()

        # Act
        response = self.client.patch(
            f"/portal/content/translations/{self.translation.slug}/versions/{self.es_version.id}/entries/",
            data={"rows": [{"unit_id": self.ayah.id, "text": "x"}]},
            content_type="application/json",
        )

        # Assert
        self._assert_language_not_assigned(response)

    def test_version_scoped_read_where_bypass_permission_should_succeed(self):
        # Arrange
        self._authorise()
        self.give_permission(self.user, PermissionChoice.PORTAL_ACCESS_ALL_LANGUAGES)

        # Act
        response = self.client.get(
            f"/portal/content/translations/{self.translation.slug}/versions/{self.es_version.id}/entries/"
        )

        # Assert
        self.assertEqual(200, response.status_code, response.content)

    def test_set_availability_where_language_not_assigned_should_return_403(self):
        # Arrange
        self._authorise()

        # Act
        response = self.client.patch(
            f"/portal/content/translations/{self.translation.slug}/languages/es/availability/",
            data={"available": True},
            content_type="application/json",
        )

        # Assert
        self._assert_language_not_assigned(response)

    def test_list_versions_where_unfiltered_should_omit_unassigned_languages(self):
        # Arrange
        self._authorise()
        baker.make(
            AssetVersion,
            asset=self.translation,
            asset_language=self.fr,
            name="fr-v1",
            state=VersionStateChoice.PUBLISHED,
        )

        # Act
        response = self.client.get(f"/portal/translations/{self.translation.slug}/versions/")

        # Assert — the 'es' version is not listed
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual(["fr-v1"], [row["name"] for row in response.json()["results"]])

    def test_list_versions_where_filtering_by_unassigned_language_should_return_403(self):
        # Arrange
        self._authorise()

        # Act
        response = self.client.get(f"/portal/translations/{self.translation.slug}/versions/?language=es")

        # Assert
        self._assert_language_not_assigned(response)

    def test_delete_version_where_language_not_assigned_should_return_403(self):
        # Arrange
        self._authorise()

        # Act
        response = self.client.delete(f"/portal/translations/{self.translation.slug}/versions/{self.es_version.id}/")

        # Assert
        self._assert_language_not_assigned(response)


class AddAssetLanguagePermissionTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.publisher = baker.make(Publisher, name="Test Publisher")
        self.translation = baker.make(
            Asset,
            category=CategoryChoice.TRANSLATION,
            template=AssetTemplateChoice.AYAH,
            publisher=self.publisher,
            status=StatusChoice.READY,
            slug="t1",
            language="ar",
        )
        self.user = User.objects.create_user(email="adder@example.com", name="Adder", is_staff=True)
        self.membership = baker.make(
            PublisherMember,
            user=self.user,
            publisher=self.publisher,
            status=PublisherMember.StatusChoice.ACTIVE,
        )

    def test_add_language_where_only_edit_permission_should_return_403(self):
        # Arrange — editing content no longer implies starting a new language
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_UPDATE_TRANSLATION)
        self.give_permission(self.user, PermissionChoice.PORTAL_READ_TRANSLATION)

        # Act
        response = self.client.post(
            f"/portal/content/translations/{self.translation.slug}/languages/",
            data={"language": "es"},
        )

        # Assert
        self.assertEqual(403, response.status_code, response.content)
        self.assertEqual("permission_denied", response.json()["error_name"])

    def test_add_language_where_permitted_should_assign_it_to_the_creator(self):
        # Arrange — no edit permission at all, only read + the add permission
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_READ_TRANSLATION)
        self.give_permission(self.user, PermissionChoice.PORTAL_ADD_ASSET_LANGUAGE)

        # Act
        response = self.client.post(
            f"/portal/content/translations/{self.translation.slug}/languages/",
            data={"language": "es"},
        )

        # Assert — the creator can edit what they just created
        self.assertEqual(200, response.status_code, response.content)
        self.assertTrue(MemberLanguage.objects.filter(member=self.membership, language="es").exists())
