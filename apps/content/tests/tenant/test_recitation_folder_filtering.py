from django.core.files.uploadedfile import SimpleUploadedFile
from model_bakery import baker

from apps.content.models import (
    Asset,
    CategoryChoice,
    RecitationFolder,
    RecitationSurahTrack,
    StatusChoice,
)
from apps.core.tests.base import BaseTestCase
from apps.publishers.models import Publisher
from apps.users.models import User


class TenantRecitationFolderFilteringTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.publisher = baker.make(Publisher)
        self.domain = baker.make(
            "publishers.Domain",
            domain="tenant-folders.com",
            publisher=self.publisher,
            is_primary=True,
        )
        self.asset = baker.make(
            Asset,
            category=CategoryChoice.RECITATION,
            publisher=self.publisher,
            status=StatusChoice.READY,
            reciter=baker.make("content.Reciter", name="Tenant Reciter"),
            riwayah=baker.make("content.Riwayah", name="Tenant Riwayah"),
        )
        self.default_folder = self.asset.recitation_folders.get(is_default=True)
        self.echo_folder = RecitationFolder.objects.create(asset=self.asset, name="With echo", name_en="With echo")

        for surah_number in (1, 2):
            RecitationSurahTrack.objects.create(
                asset=self.asset,
                folder=self.default_folder,
                surah_number=surah_number,
                duration_ms=1000,
                size_bytes=512,
                audio_file=SimpleUploadedFile(f"{surah_number:03}.mp3", b"dummy"),
            )
        RecitationSurahTrack.objects.create(
            asset=self.asset,
            folder=self.echo_folder,
            surah_number=1,
            duration_ms=9999,
            size_bytes=4096,
            audio_file=SimpleUploadedFile("001-echo.mp3", b"dummy"),
        )

        self.user = User.objects.create_user(email="tenant-folders@example.com", name="Tenant User")

    def test_list_recitations_should_omit_hidden_folders(self):
        self.echo_folder.is_visible = False
        self.echo_folder.save(update_fields=["is_visible"])
        self.authenticate_user(self.user, domain=self.domain)

        response = self.client.get("/tenant/recitations/", format="json")

        self.assertEqual(200, response.status_code, response.content)
        recitation = next(r for r in response.json()["results"] if r["id"] == self.asset.id)
        self.assertEqual(
            [{"name": "Default", "slug": "default", "is_default": True}],
            recitation["folders"],
        )

    def test_list_tracks_where_folder_hidden_should_return_404(self):
        self.echo_folder.is_visible = False
        self.echo_folder.save(update_fields=["is_visible"])
        self.authenticate_user(self.user, domain=self.domain)

        response = self.client.get(f"/tenant/recitation-tracks/{self.asset.id}/?folder=with-echo", format="json")

        self.assertEqual(404, response.status_code, response.content)
        self.assertEqual("folder_not_found", response.json()["error_name"])

    def test_list_tracks_where_default_promoted_should_return_new_default_without_folder_param(self):
        self.echo_folder.is_default = True
        self.default_folder.is_default = False
        RecitationFolder.objects.bulk_update(
            [self.echo_folder, self.default_folder],
            ["is_default"],
        )
        self.authenticate_user(self.user, domain=self.domain)

        response = self.client.get(f"/tenant/recitation-tracks/{self.asset.id}/", format="json")

        self.assertEqual(200, response.status_code, response.content)
        items = response.json()["results"]
        self.assertEqual(1, len(items))
        self.assertEqual(9999, items[0]["duration_ms"])
