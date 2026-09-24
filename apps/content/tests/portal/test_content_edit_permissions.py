from urllib.parse import urlencode

from django.core.files.uploadedfile import SimpleUploadedFile
from model_bakery import baker

from apps.content.models import (
    Asset,
    AssetTemplateChoice,
    AssetVersion,
    CategoryChoice,
    StatusChoice,
    VersionStateChoice,
)
from apps.core.permissions import PermissionChoice
from apps.core.services.permissions import PermissionHierarchyService
from apps.core.tests.base import BaseTestCase
from apps.publishers.models import Publisher
from apps.users.models import User


class ContentEditPermissionTests(BaseTestCase):
    """Editing an asset's text is its own permission, per category, separate from
    the metadata UPDATE permission."""

    def setUp(self):
        super().setUp()
        publisher = baker.make(Publisher, name="Perm Publisher")
        common = {
            "publisher": publisher,
            "template": AssetTemplateChoice.AYAH,
            "status": StatusChoice.READY,
            "language": "ar",
        }
        self.translation = baker.make(Asset, category=CategoryChoice.TRANSLATION, slug="perm-translation", **common)
        self.tafsir = baker.make(Asset, category=CategoryChoice.TAFSIR, slug="perm-tafsir", **common)
        self.user = User.objects.create_user(email="perm-editor@example.com", name="Editor", is_staff=True)
        self.give_permission(self.user, PermissionChoice.PORTAL_ACCESS_ALL_LANGUAGES)

    def _open_draft(self, segment: str, slug: str):
        return self.client.post(
            f"/portal/content/{segment}/{slug}/draft/",
            data={"language": "ar"},
            content_type="application/json",
        )

    def test_get_or_create_draft_where_user_has_only_metadata_update_should_return_403(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_UPDATE_TRANSLATION)

        # Act
        response = self._open_draft("translations", self.translation.slug)

        # Assert
        self.assertEqual(403, response.status_code, response.content)
        self.assertEqual("permission_denied", response.json()["error_name"])

    def test_get_or_create_draft_where_user_can_edit_translation_content_should_return_200(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_EDIT_TRANSLATION_CONTENT)

        # Act
        response = self._open_draft("translations", self.translation.slug)

        # Assert
        self.assertEqual(200, response.status_code, response.content)

    def test_get_or_create_draft_where_permission_is_for_other_category_should_return_403(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_EDIT_TRANSLATION_CONTENT)

        # Act
        response = self._open_draft("tafsirs", self.tafsir.slug)

        # Assert
        self.assertEqual(403, response.status_code, response.content)
        self.assertEqual("permission_denied", response.json()["error_name"])

    def test_restore_version_where_user_has_only_metadata_update_should_return_403(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_UPDATE_TAFSIR)
        source = self.tafsir.get_or_create_source_language()
        version = baker.make(AssetVersion, asset=self.tafsir, asset_language=source, state=VersionStateChoice.PUBLISHED)

        # Act
        response = self.client.post(
            f"/portal/content/tafsirs/{self.tafsir.slug}/versions/{version.id}/restore/",
            data={},
            content_type="application/json",
        )

        # Assert
        self.assertEqual(403, response.status_code, response.content)
        self.assertEqual("permission_denied", response.json()["error_name"])

    def test_create_version_where_user_has_only_metadata_permissions_should_return_403(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_CREATE_TRANSLATION)

        # Act
        response = self.client.post(
            f"/portal/translations/{self.translation.slug}/versions/",
            data={
                "asset_id": self.translation.id,
                "name": "v2",
                "summary": "upload",
                "file": SimpleUploadedFile("v2.pdf", b"content", content_type="application/pdf"),
            },
        )

        # Assert
        self.assertEqual(403, response.status_code, response.content)
        self.assertEqual("permission_denied", response.json()["error_name"])

    def test_create_version_where_user_can_edit_content_should_return_201(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_EDIT_TRANSLATION_CONTENT)

        # Act
        response = self.client.post(
            f"/portal/translations/{self.translation.slug}/versions/",
            data={
                "asset_id": self.translation.id,
                "name": "v2",
                "summary": "upload",
                "file": SimpleUploadedFile("v2.pdf", b"content", content_type="application/pdf"),
            },
        )

        # Assert
        self.assertEqual(201, response.status_code, response.content)

    def test_patch_version_where_file_replaced_with_only_metadata_update_should_return_403(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_UPDATE_TAFSIR)
        version = baker.make(AssetVersion, asset=self.tafsir, name="v1", summary="s")

        # Act
        response = self.client.patch(
            f"/portal/tafsirs/{self.tafsir.slug}/versions/{version.id}/",
            data={"file": SimpleUploadedFile("new.pdf", b"new", content_type="application/pdf")},
        )

        # Assert
        self.assertEqual(403, response.status_code, response.content)
        self.assertEqual("permission_denied", response.json()["error_name"])

    def test_patch_version_where_only_name_changes_should_need_metadata_update_only(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_UPDATE_TAFSIR)
        version = baker.make(AssetVersion, asset=self.tafsir, name="v1", summary="s")

        # Act
        response = self.client.patch(
            f"/portal/tafsirs/{self.tafsir.slug}/versions/{version.id}/",
            data=urlencode({"name": "Renamed"}),
            content_type="application/x-www-form-urlencoded",
        )

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual("Renamed", response.json()["name"])

    def test_with_implied_where_content_permission_granted_should_include_category_read(self):
        # Arrange
        service = PermissionHierarchyService()

        # Act
        implied = service.with_implied([PermissionChoice.PORTAL_EDIT_TAFSIR_CONTENT])

        # Assert
        self.assertIn(PermissionChoice.PORTAL_READ_TAFSIR, implied)
        self.assertNotIn(PermissionChoice.PORTAL_UPDATE_TAFSIR, implied)
