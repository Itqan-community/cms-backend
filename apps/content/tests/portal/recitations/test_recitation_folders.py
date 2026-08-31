from django.core.files.uploadedfile import SimpleUploadedFile
from model_bakery import baker

from apps.content.models import (
    Asset,
    CategoryChoice,
    Qiraah,
    RecitationFolder,
    RecitationSurahTrack,
    Reciter,
    Riwayah,
    StatusChoice,
)
from apps.core.permissions import PermissionChoice
from apps.core.tests.base import BaseTestCase
from apps.publishers.models import Publisher
from apps.users.models import User


class RecitationFoldersPortalAPITest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.staff_user = User.objects.create_user(email="folders-staff@example.com", name="Staff User", is_staff=True)
        self.non_staff_user = User.objects.create_user(
            email="folders-user@example.com", name="Regular User", is_staff=False
        )

        self.publisher = baker.make(Publisher, name="Folders Publisher")
        self.reciter = baker.make(Reciter, name="Folders Reciter")
        self.qiraah = baker.make(Qiraah, name="Folders Qiraah")
        self.riwayah = baker.make(Riwayah, name="Folders Riwayah", qiraah=self.qiraah)

        self.asset = baker.make(
            Asset,
            publisher=self.publisher,
            status=StatusChoice.READY,
            category=CategoryChoice.RECITATION,
            reciter=self.reciter,
            qiraah=self.qiraah,
            riwayah=self.riwayah,
            name="Folders Recitation",
        )
        self.default_folder = self.asset.recitation_folders.get(is_default=True)
        self.url = f"/portal/recitations/{self.asset.slug}/folders/"

    # --- list ---

    def test_list_folders_where_permitted_should_return_default_first_with_track_counts(self):
        # Arrange
        self.authenticate_user(self.staff_user)
        self.give_permission(self.staff_user, PermissionChoice.PORTAL_READ_RECITATION)
        echo = RecitationFolder.objects.create(asset=self.asset, name="With echo", name_en="With echo")
        RecitationSurahTrack.objects.create(
            asset=self.asset, folder=echo, surah_number=1, audio_file=SimpleUploadedFile("001.mp3", b"x")
        )

        # Act
        response = self.client.get(self.url)

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual(2, len(body))
        self.assertTrue(body[0]["is_default"])
        self.assertEqual(0, body[0]["tracks_count"])
        self.assertEqual("with-echo", body[1]["slug"])
        self.assertEqual(1, body[1]["tracks_count"])

    def test_list_folders_where_missing_permission_should_return_403(self):
        # Arrange
        self.authenticate_user(self.non_staff_user)

        # Act
        response = self.client.get(self.url)

        # Assert
        self.assertEqual(403, response.status_code, response.content)
        self.assertEqual("permission_denied", response.json()["error_name"])

    def test_list_folders_where_recitation_unknown_should_return_404(self):
        # Arrange
        self.authenticate_user(self.staff_user)
        self.give_permission(self.staff_user, PermissionChoice.PORTAL_READ_RECITATION)

        # Act
        response = self.client.get("/portal/recitations/does-not-exist/folders/")

        # Assert
        self.assertEqual(404, response.status_code, response.content)
        self.assertEqual("recitation_not_found", response.json()["error_name"])

    # --- create ---

    def test_create_folder_where_valid_should_return_201_and_derive_slug(self):
        # Arrange
        self.authenticate_user(self.staff_user)
        self.give_permission(self.staff_user, PermissionChoice.PORTAL_CREATE_RECITATION)

        # Act
        response = self.client.post(self.url, {"name_ar": "مع صدى", "name_en": "With echo"}, format="json")

        # Assert
        self.assertEqual(201, response.status_code, response.content)
        body = response.json()
        self.assertEqual("with-echo", body["slug"])
        self.assertFalse(body["is_default"])
        self.assertEqual(2, RecitationFolder.objects.filter(asset=self.asset).count())

    def test_create_folder_where_names_blank_should_return_400_folder_name_required(self):
        # Arrange
        self.authenticate_user(self.staff_user)
        self.give_permission(self.staff_user, PermissionChoice.PORTAL_CREATE_RECITATION)

        # Act
        response = self.client.post(self.url, {"name_ar": "", "name_en": "  "}, format="json")

        # Assert
        self.assertEqual(400, response.status_code, response.content)
        self.assertEqual("folder_name_required", response.json()["error_name"])

    def test_create_folder_where_missing_permission_should_return_403(self):
        # Arrange
        self.authenticate_user(self.non_staff_user)

        # Act
        response = self.client.post(self.url, {"name_en": "With echo"}, format="json")

        # Assert
        self.assertEqual(403, response.status_code, response.content)
        self.assertEqual("permission_denied", response.json()["error_name"])

    # --- update ---

    def test_update_folder_where_renamed_should_keep_slug_and_return_200(self):
        # Arrange
        self.authenticate_user(self.staff_user)
        self.give_permission(self.staff_user, PermissionChoice.PORTAL_UPDATE_RECITATION)
        RecitationFolder.objects.create(asset=self.asset, name="With echo", name_en="With echo")

        # Act
        response = self.client.patch(f"{self.url}with-echo/", {"name_en": "Echo and delay"}, format="json")

        # Assert - slug is the public ?folder= value and must survive a rename
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual("with-echo", body["slug"])
        self.assertEqual("Echo and delay", body["name_en"])

    def test_update_folder_where_folder_unknown_should_return_404_folder_not_found(self):
        # Arrange
        self.authenticate_user(self.staff_user)
        self.give_permission(self.staff_user, PermissionChoice.PORTAL_UPDATE_RECITATION)

        # Act
        response = self.client.patch(f"{self.url}nope/", {"name_en": "X"}, format="json")

        # Assert
        self.assertEqual(404, response.status_code, response.content)
        self.assertEqual("folder_not_found", response.json()["error_name"])

    # --- delete ---

    def test_delete_folder_where_variant_should_return_204_and_remove_tracks(self):
        # Arrange
        self.authenticate_user(self.staff_user)
        self.give_permission(self.staff_user, PermissionChoice.PORTAL_DELETE_RECITATION)
        echo = RecitationFolder.objects.create(asset=self.asset, name="With echo", name_en="With echo")
        RecitationSurahTrack.objects.create(
            asset=self.asset, folder=echo, surah_number=1, audio_file=SimpleUploadedFile("001.mp3", b"x")
        )

        # Act
        response = self.client.delete(f"{self.url}with-echo/")

        # Assert
        self.assertEqual(204, response.status_code, response.content)
        self.assertFalse(RecitationFolder.objects.filter(id=echo.id).exists())
        self.assertEqual(0, RecitationSurahTrack.objects.filter(folder_id=echo.id).count())

    def test_delete_folder_where_default_should_return_400_cannot_delete_default_folder(self):
        # Arrange
        self.authenticate_user(self.staff_user)
        self.give_permission(self.staff_user, PermissionChoice.PORTAL_DELETE_RECITATION)

        # Act
        response = self.client.delete(f"{self.url}{self.default_folder.slug}/")

        # Assert - every API falls back to the default folder, so it must stay
        self.assertEqual(400, response.status_code, response.content)
        self.assertEqual("cannot_delete_default_folder", response.json()["error_name"])
        self.assertTrue(RecitationFolder.objects.filter(id=self.default_folder.id).exists())

    def test_delete_folder_where_missing_permission_should_return_403(self):
        # Arrange
        self.authenticate_user(self.non_staff_user)
        RecitationFolder.objects.create(asset=self.asset, name="With echo", name_en="With echo")

        # Act
        response = self.client.delete(f"{self.url}with-echo/")

        # Assert
        self.assertEqual(403, response.status_code, response.content)
        self.assertEqual("permission_denied", response.json()["error_name"])

    def test_update_folder_where_hidden_should_return_200_with_is_visible(self):
        self.authenticate_user(self.staff_user)
        self.give_permission(self.staff_user, PermissionChoice.PORTAL_UPDATE_RECITATION)
        echo = RecitationFolder.objects.create(asset=self.asset, name="With echo", name_en="With echo")

        response = self.client.patch(f"{self.url}with-echo/", {"is_visible": False}, format="json")

        self.assertEqual(200, response.status_code, response.content)
        self.assertFalse(response.json()["is_visible"])
        echo.refresh_from_db()
        self.assertFalse(echo.is_visible)

    def test_update_folder_where_default_hidden_should_return_400(self):
        self.authenticate_user(self.staff_user)
        self.give_permission(self.staff_user, PermissionChoice.PORTAL_UPDATE_RECITATION)

        response = self.client.patch(
            f"{self.url}{self.default_folder.slug}/",
            {"is_visible": False},
            format="json",
        )

        self.assertEqual(400, response.status_code, response.content)
        self.assertEqual("cannot_hide_default_folder", response.json()["error_name"])

    def test_update_folder_where_set_default_should_promote_variant(self):
        self.authenticate_user(self.staff_user)
        self.give_permission(self.staff_user, PermissionChoice.PORTAL_UPDATE_RECITATION)
        echo = RecitationFolder.objects.create(asset=self.asset, name="With echo", name_en="With echo")

        response = self.client.patch(f"{self.url}with-echo/", {"is_default": True}, format="json")

        self.assertEqual(200, response.status_code, response.content)
        self.assertTrue(response.json()["is_default"])
        self.default_folder.refresh_from_db()
        echo.refresh_from_db()
        self.assertFalse(self.default_folder.is_default)
        self.assertTrue(echo.is_default)


class RecitationFoldersPortalScopingTest(BaseTestCase):
    """Folders must never be reachable through another publisher's recitation."""

    def setUp(self):
        super().setUp()
        self.staff_user = User.objects.create_user(email="scoping-staff@example.com", name="Staff User", is_staff=True)
        self.reciter = baker.make(Reciter, name="Scoping Reciter")
        self.qiraah = baker.make(Qiraah, name="Scoping Qiraah")
        self.riwayah = baker.make(Riwayah, name="Scoping Riwayah", qiraah=self.qiraah)

        self.own_asset = baker.make(
            Asset,
            publisher=baker.make(Publisher, name="Own Publisher"),
            status=StatusChoice.READY,
            category=CategoryChoice.RECITATION,
            reciter=self.reciter,
            qiraah=self.qiraah,
            riwayah=self.riwayah,
            name="Own Recitation",
        )
        self.other_asset = baker.make(
            Asset,
            publisher=baker.make(Publisher, name="Other Publisher"),
            status=StatusChoice.READY,
            category=CategoryChoice.RECITATION,
            reciter=self.reciter,
            qiraah=self.qiraah,
            riwayah=self.riwayah,
            name="Other Recitation",
        )

    def test_create_folder_where_slug_belongs_to_other_recitation_should_not_leak(self):
        # Arrange - a folder slug that exists under the *other* recitation
        self.authenticate_user(self.staff_user)
        self.give_permission(self.staff_user, PermissionChoice.PORTAL_UPDATE_RECITATION)
        RecitationFolder.objects.create(asset=self.other_asset, name="Secret", name_en="Secret")

        # Act - ask for it through our own recitation
        response = self.client.patch(
            f"/portal/recitations/{self.own_asset.slug}/folders/secret/",
            {"name_en": "Renamed"},
            format="json",
        )

        # Assert
        self.assertEqual(404, response.status_code, response.content)
        self.assertEqual("folder_not_found", response.json()["error_name"])

    def test_create_folder_where_same_name_on_two_recitations_should_allow_both(self):
        # Arrange
        self.authenticate_user(self.staff_user)
        self.give_permission(self.staff_user, PermissionChoice.PORTAL_CREATE_RECITATION)

        # Act
        first = self.client.post(
            f"/portal/recitations/{self.own_asset.slug}/folders/",
            {"name_en": "With echo"},
            format="json",
        )
        second = self.client.post(
            f"/portal/recitations/{self.other_asset.slug}/folders/",
            {"name_en": "With echo"},
            format="json",
        )

        # Assert - slug uniqueness is per asset
        self.assertEqual(201, first.status_code, first.content)
        self.assertEqual(201, second.status_code, second.content)
        self.assertEqual("with-echo", first.json()["slug"])
        self.assertEqual("with-echo", second.json()["slug"])
