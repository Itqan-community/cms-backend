from django.core.files.uploadedfile import SimpleUploadedFile
from model_bakery import baker
from oauth2_provider.models import Application

from apps.content.models import (
    Asset,
    AssetAccessRequest,
    AssetTemplateChoice,
    AssetVersion,
    CategoryChoice,
    LicenseChoice,
    Qiraah,
    RecitationSurahTrack,
    Reciter,
    Riwayah,
    StatusChoice,
)
from apps.content.tests.publishing import publish
from apps.core.tests.base import BaseTestCase
from apps.publishers.models import Publisher
from apps.users.models import User


class AssetChannelsSurfacesTest(BaseTestCase):
    """Turning one channel off hides the asset on that surface only."""

    def setUp(self):
        super().setUp()
        self.publisher = baker.make(Publisher, name="Channels Publisher")
        self.domain = baker.make(
            "publishers.Domain", domain="channels.example.com", publisher=self.publisher, is_primary=True
        )
        self.qiraah = baker.make(Qiraah, name="Hafs Q")
        self.riwayah = baker.make(Riwayah, name="Hafs R", qiraah=self.qiraah)
        self.reciter = baker.make(Reciter, name="Channel Reciter")
        self.asset = baker.make(
            Asset,
            category=CategoryChoice.RECITATION,
            publisher=self.publisher,
            status=StatusChoice.READY,
            reciter=self.reciter,
            riwayah=self.riwayah,
            qiraah=self.qiraah,
            name="Channel Recitation",
            is_open_access=True,
        )
        RecitationSurahTrack.objects.create(
            asset=self.asset, surah_number=1, audio_file=SimpleUploadedFile("1.mp3", b"audio")
        )
        self.user = User.objects.create_user(email="channels-surface@example.com", name="Surface User")
        self.app = Application.objects.create(
            user=self.user,
            name="Channels App",
            client_type="confidential",
            authorization_grant_type="password",
        )

    def _set(self, **flags):
        Asset.objects.filter(pk=self.asset.pk).update(**flags)

    # --- surface probes: True when the asset is visible there ---

    def _gallery_list(self) -> bool:
        self.authenticate_user(self.user)
        response = self.client.get("/cms-api/assets/")
        assert response.status_code == 200, response.content
        return self.asset.id in {r["id"] for r in response.json()["results"]}

    def _gallery_detail(self) -> bool:
        self.authenticate_user(self.user)
        response = self.client.get(f"/cms-api/assets/{self.asset.id}/")
        assert response.status_code in (200, 404), response.content
        return response.status_code == 200

    def _gallery_recitations(self) -> bool:
        self.authenticate_user(self.user)
        response = self.client.get("/cms-api/recitations/")
        assert response.status_code == 200, response.content
        return self.asset.id in {r["id"] for r in response.json()["results"]}

    def _gallery_tracks(self) -> bool:
        self.authenticate_user(self.user)
        response = self.client.get(f"/cms-api/recitation-tracks/{self.asset.id}/")
        assert response.status_code in (200, 404), response.content
        return response.status_code == 200

    def _public_recitations(self) -> bool:
        self.authenticate_client(self.app)
        response = self.client.get("/recitations/")
        assert response.status_code == 200, response.content
        return self.asset.id in {r["id"] for r in response.json()["results"]}

    def _public_tracks(self) -> bool:
        self.authenticate_client(self.app)
        response = self.client.get(f"/recitations/{self.asset.id}/")
        assert response.status_code in (200, 404), response.content
        return response.status_code == 200

    def _public_reciters_count(self) -> int:
        self.authenticate_client(self.app)
        response = self.client.get("/reciters/")
        assert response.status_code == 200, response.content
        rows = [r for r in response.json()["results"] if r["id"] == self.reciter.id]
        return rows[0]["recitations_count"] if rows else 0

    def _tenant_recitations(self) -> bool:
        self.authenticate_user(self.user, domain=self.domain)
        response = self.client.get("/tenant/recitations/")
        assert response.status_code == 200, response.content
        return self.asset.id in {r["id"] for r in response.json()["results"]}

    def _tenant_tracks(self) -> bool:
        self.authenticate_user(self.user, domain=self.domain)
        response = self.client.get(f"/tenant/recitation-tracks/{self.asset.id}/")
        assert response.status_code in (200, 404), response.content
        return response.status_code == 200

    def _tenant_reciters(self) -> bool:
        self.authenticate_user(self.user, domain=self.domain)
        response = self.client.get("/tenant/reciters/")
        assert response.status_code == 200, response.content
        return self.reciter.id in {r["id"] for r in response.json()["results"]}

    def _gallery(self) -> list[bool]:
        return [self._gallery_list(), self._gallery_detail(), self._gallery_recitations(), self._gallery_tracks()]

    def _public(self) -> list[bool]:
        return [self._public_recitations(), self._public_tracks(), self._public_reciters_count() == 1]

    def _tenant(self) -> list[bool]:
        return [self._tenant_recitations(), self._tenant_tracks(), self._tenant_reciters()]

    def test_surfaces_where_all_channels_on_should_show_asset_everywhere(self):
        # Arrange / Act
        gallery, public, tenant = self._gallery(), self._public(), self._tenant()
        # Assert
        self.assertEqual([True] * 4, gallery)
        self.assertEqual([True] * 3, public)
        self.assertEqual([True] * 3, tenant)

    def test_surfaces_where_in_gallery_off_should_hide_only_from_gallery(self):
        # Arrange
        self._set(in_gallery=False)
        # Act / Assert
        self.assertEqual([False] * 4, self._gallery())
        self.assertEqual([True] * 3, self._public())
        self.assertEqual([True] * 3, self._tenant())

    def test_surfaces_where_in_public_api_off_should_hide_only_from_public_api(self):
        # Arrange
        self._set(in_public_api=False)
        # Act / Assert
        self.assertEqual([False] * 3, self._public())
        self.assertEqual([True] * 4, self._gallery())
        self.assertEqual([True] * 3, self._tenant())

    def test_surfaces_where_in_tenants_off_should_hide_only_from_tenant_api(self):
        # Arrange
        self._set(in_tenants=False)
        # Act / Assert
        self.assertEqual([False] * 3, self._tenant())
        self.assertEqual([True] * 4, self._gallery())
        self.assertEqual([True] * 3, self._public())

    def test_surfaces_where_in_cli_off_should_not_affect_gallery_public_or_tenant(self):
        # Arrange
        self._set(in_cli=False)
        # Act / Assert
        self.assertEqual([True] * 4, self._gallery())
        self.assertEqual([True] * 3, self._public())
        self.assertEqual([True] * 3, self._tenant())

    def test_surfaces_where_tenant_reads_other_publishers_asset_should_still_be_scoped(self):
        # Arrange
        other_domain = baker.make(
            "publishers.Domain", domain="other-channels.example.com", publisher=baker.make(Publisher), is_primary=True
        )
        self.authenticate_user(self.user, domain=other_domain)
        # Act
        response = self.client.get("/tenant/recitations/")
        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertNotIn(self.asset.id, {r["id"] for r in response.json()["results"]})

    def test_gallery_download_where_other_channels_off_should_still_download(self):
        # Arrange
        tafsir = baker.make(
            Asset,
            publisher=self.publisher,
            category=CategoryChoice.TEXT,
            template=AssetTemplateChoice.AYAH,
            license=LicenseChoice.CC0,
            status=StatusChoice.READY,
            is_open_access=True,
            in_public_api=False,
            in_cli=False,
            in_tenants=False,
        )
        publish(
            baker.make(
                AssetVersion,
                asset=tafsir,
                name="Version 1",
                file_url=SimpleUploadedFile("t.csv", b"data", content_type="text/csv"),
            )
        )
        self.authenticate_user(self.user)
        # Act
        on = self.client.get(f"/cms-api/assets/{tafsir.id}/download/")
        Asset.objects.filter(pk=tafsir.pk).update(in_gallery=False)
        off = self.client.get(f"/cms-api/assets/{tafsir.id}/download/")
        # Assert
        self.assertEqual(200, on.status_code, on.content)
        self.assertEqual(404, off.status_code, off.content)
        self.assertEqual("not_found", off.json()["error_name"])

    def test_samples_where_in_public_api_off_should_skip_recitation(self):
        # Arrange: covered in test_samples (public sample endpoint); here only assert the
        # sampler repository honours the channel directly.
        from apps.content.repositories.recitation import RecitationRepository

        self.authenticate_user(self.user)
        sample_before = RecitationRepository().get_sample_asset()
        self._set(in_public_api=False)
        # Act
        sample_after = RecitationRepository().get_sample_asset()
        # Assert
        self.assertIn(sample_before, (None, self.asset))
        self.assertIsNone(sample_after)

    def test_dependabot_dispatch_where_in_cli_off_should_skip(self):
        # Arrange
        from unittest.mock import patch

        from apps.content.models import VersionStateChoice
        from apps.dependabot import tasks as dependabot_tasks

        tafsir = baker.make(
            Asset,
            publisher=self.publisher,
            category=CategoryChoice.TEXT,
            template=AssetTemplateChoice.AYAH,
            status=StatusChoice.READY,
            in_cli=False,
        )
        version = baker.make(AssetVersion, asset=tafsir, name="1.0.0", state=VersionStateChoice.PUBLISHED)
        enabled = type("Cfg", (), {"enabled": True})()
        # Act
        with patch.object(dependabot_tasks, dependabot_tasks.load_github_app_config.__name__, return_value=enabled):
            result = dependabot_tasks.dispatch_dependabot_updates_for_version(version.pk)
        # Assert
        self.assertEqual({"status": "skipped", "reason": "not_in_cli", "dispatched_count": 0}, result)

    def test_request_access_where_in_gallery_off_should_return_404(self):
        # Arrange
        self._set(in_gallery=False)
        self.authenticate_user(self.user)
        # Act
        response = self.client.post(
            f"/cms-api/assets/{self.asset.id}/request-access/",
            data={"purpose": "x", "intended_use": AssetAccessRequest.IntendedUseChoice.NON_COMMERCIAL},
            content_type="application/json",
        )
        # Assert
        self.assertEqual(404, response.status_code, response.content)
