"""Tests for content sample endpoints (tafsir, translation, recitation, joined-ayah)."""

import json
from unittest import mock

from django.conf import settings
from django.core.cache import cache
from django.core.files.base import ContentFile
from model_bakery import baker

from apps.content.models import (
    Asset,
    AssetVersion,
    CategoryChoice,
    Qiraah,
    RecitationAyahTiming,
    RecitationFolder,
    RecitationSurahTrack,
    Reciter,
    Riwayah,
    StatusChoice,
)
from apps.content.services import asset_verse_text
from apps.core.tests.base import BaseTestCase
from apps.publishers.models import Publisher
from apps.quran.models import Ayah, Sura


class ContentSamplesTest(BaseTestCase):
    """Tests for /sample-data/tafsir/, /sample-data/translation/, /sample-data/recitation/, and /sample-data/joined-ayah/ endpoints."""

    def setUp(self):
        """Cold cache plus publisher/qiraah/riwayah/reciter and the 1:1 Quran anchor."""
        super().setUp()
        # TestCase transactions roll back DB rows but not the shared locmem
        # cache; verse-text entries would leak across tests (and rolled-back
        # SQLite ids collide), so every test starts with a cold cache.
        cache.clear()
        # Create a publisher for test assets
        self.publisher = baker.make(Publisher, name="Test Publisher")
        # Create required related objects for recitation tests
        self.qiraah = baker.make(Qiraah, name="Hafs")
        self.riwayah = baker.make(Riwayah, name="Warsh", qiraah=self.qiraah)
        self.reciter = baker.make(Reciter, name="Mishary Al-Afasy")
        # Deterministic Quran anchor for the sample endpoints: Surah 1 / Ayah 1:1.
        self._seed_quran_location(1, 1)

    def _seed_quran_location(self, sura_id: int, ayah_number: int):
        """Create one sura and one ayah row at the given location."""
        sura = baker.make(
            Sura,
            id=sura_id,
            name="الفاتحة" if sura_id == 1 else "البقرة",
            transliterated_name="Al-Faatiha" if sura_id == 1 else "Al-Baqara",
            english_name="The Opening" if sura_id == 1 else "The Cow",
            ayas_count=7 if sura_id == 1 else 286,
            start_offset=0,
            revelation_type="Meccan" if sura_id == 1 else "Medinan",
            revelation_order=5 if sura_id == 1 else 87,
            rukus_count=1 if sura_id == 1 else 40,
        )
        ayah = baker.make(
            Ayah,
            sura=sura,
            number_in_sura=ayah_number,
            text=f"نص الآية {sura_id}:{ayah_number}",
            juz=1,
            hizb_quarter=1,
            page=1,
        )
        return sura, ayah

    def _seed_versioned_asset(self, category, name: str, payload: dict):
        """Create a READY asset whose latest version carries the given JSON payload."""
        asset = baker.make(
            Asset,
            category=category,
            publisher=self.publisher,
            status=StatusChoice.READY,
            name=name,
            language="ar",
        )
        baker.make(
            AssetVersion,
            asset=asset,
            name="v1",
            file_url=ContentFile(json.dumps(payload, ensure_ascii=False).encode("utf-8"), name=f"{category}.json"),
        )
        return asset

    def _create_test_recitation_with_timing(self):
        """Helper to create a recitation asset with timing data for ayah 1:1."""
        # Create the recitation asset
        asset = baker.make(
            Asset,
            category=CategoryChoice.RECITATION,
            publisher=self.publisher,
            status=StatusChoice.READY,
            reciter=self.reciter,
            riwayah=self.riwayah,
            qiraah=self.qiraah,
            name="Test Recitation",
            language="ar",
        )

        # The post_save signal has already provisioned the asset's default
        # folder -- creating another here would violate one-default-per-asset.
        folder = asset.recitation_folders.get(is_default=True)

        # Create a track for surah 1 using ContentFile for the FileField
        track = RecitationSurahTrack.objects.create(
            asset=asset,
            folder=folder,
            surah_number=1,
            audio_file=ContentFile(b"\x00", name="test.mp3"),
            duration_ms=15000,
        )

        # Create timing for ayah 1:1
        baker.make(
            RecitationAyahTiming,
            track=track,
            ayah_key="1:1",
            start_ms=0,
            end_ms=3000,
            duration_ms=3000,
        )

        return asset

    def test_get_tafsir_sample_where_ready_asset_has_verse_file_should_return_real_text(self):
        """Text equals the uploaded JSON value byte-for-byte; structure matches the contract."""
        # Arrange
        tafsir_asset = baker.make(
            Asset,
            category=CategoryChoice.TAFSIR,
            publisher=self.publisher,
            status=StatusChoice.READY,
            name="Tafsir al-Tabari",
            language="ar",
            license="CC-BY-4.0",
        )
        verse_text = "نص التفسير الحقيقي للآية"
        payload = json.dumps({"1:1": verse_text}, ensure_ascii=False).encode("utf-8")
        baker.make(AssetVersion, asset=tafsir_asset, name="v1", file_url=ContentFile(payload, name="tafsir.json"))
        # Act
        response = self.client.get("/sample-data/tafsir/")
        # Assert
        self.assertEqual(200, response.status_code)
        data = response.json()
        self.assertEqual(
            {"asset_id", "asset_name", "publisher", "language", "license", "sample_verse"}, set(data.keys())
        )
        self.assertEqual(tafsir_asset.id, data["asset_id"])
        self.assertEqual({"id": self.publisher.id, "name": self.publisher.name}, data["publisher"])
        self.assertEqual({"surah": 1, "ayah": 1, "text": verse_text}, data["sample_verse"])

    def test_get_tafsir_sample_with_explicit_query_should_read_nested_shape(self):
        """Nested {"<surah>": {"<ayah>": ...}} payloads resolve via ?surah=&ayah=."""
        # Arrange
        tafsir_asset = baker.make(
            Asset,
            category=CategoryChoice.TAFSIR,
            publisher=self.publisher,
            status=StatusChoice.READY,
            name="تفسير الطبري",
            language="ar",
        )
        verse_text = "تفسير آية البقرة"
        payload = json.dumps({"2": {"255": verse_text}}, ensure_ascii=False).encode("utf-8")
        baker.make(AssetVersion, asset=tafsir_asset, name="v1", file_url=ContentFile(payload, name="tafsir.json"))
        # Act
        response = self.client.get("/sample-data/tafsir/", {"surah": 2, "ayah": 255})
        # Assert
        self.assertEqual(200, response.status_code)
        self.assertEqual({"surah": 2, "ayah": 255, "text": verse_text}, response.json()["sample_verse"])

    def test_get_tafsir_sample_where_latest_version_lacks_the_verse_should_return_404(self):
        """A READY asset whose file omits the requested verse fails honestly (typed 404)."""
        # Arrange - READY asset whose file only carries a different ayah
        tafsir_asset = baker.make(
            Asset,
            category=CategoryChoice.TAFSIR,
            publisher=self.publisher,
            status=StatusChoice.READY,
            name="Partial Tafsir",
            language="ar",
        )
        payload = json.dumps({"2:255": "غير موجودة هنا"}).encode("utf-8")
        baker.make(AssetVersion, asset=tafsir_asset, name="v1", file_url=ContentFile(payload, name="tafsir.json"))
        # Act
        response = self.client.get("/sample-data/tafsir/")
        # Assert
        self.assertEqual(404, response.status_code)
        self.assertEqual("tafsir_sample_verse_unavailable", response.json()["error_name"])

    def test_get_tafsir_sample_where_asset_has_no_version_file_should_return_404(self):
        """Metadata-only assets can never provide verse text."""
        # Arrange - metadata-only asset: no version file can ever carry the text
        baker.make(
            Asset,
            category=CategoryChoice.TAFSIR,
            publisher=self.publisher,
            status=StatusChoice.READY,
            name="Metadata-only Tafsir",
            language="ar",
        )
        # Act
        response = self.client.get("/sample-data/tafsir/")
        # Assert
        self.assertEqual(404, response.status_code)
        self.assertEqual("tafsir_sample_verse_unavailable", response.json()["error_name"])

    def test_get_tafsir_sample_where_only_restricted_asset_exists_should_return_404(self):
        """Tenant-restricted tafsirs are invisible to the public sample surface."""
        # Arrange - READY but tenant-restricted tafsir must never surface publicly
        baker.make(
            Asset,
            category=CategoryChoice.TAFSIR,
            publisher=self.publisher,
            status=StatusChoice.READY,
            restricted_for_tenant=True,
            name="Restricted Tafsir",
            language="ar",
        )
        # Act
        response = self.client.get("/sample-data/tafsir/")
        # Assert
        self.assertEqual(404, response.status_code)
        self.assertEqual("tafsir_not_found", response.json()["error_name"])

    def test_get_translation_sample_where_only_restricted_asset_exists_should_return_404(self):
        """Same restriction guard enforced for translations."""
        # Arrange
        baker.make(
            Asset,
            category=CategoryChoice.TRANSLATION,
            publisher=self.publisher,
            status=StatusChoice.READY,
            restricted_for_tenant=True,
            name="Restricted Translation",
            language="en",
        )
        # Act
        response = self.client.get("/sample-data/translation/")
        # Assert
        self.assertEqual(404, response.status_code)
        self.assertEqual("translation_not_found", response.json()["error_name"])

    def test_get_tafsir_sample_where_version_file_is_malformed_json_should_return_404(self):
        """Corrupt payloads degrade to honest unavailability instead of garbage output."""
        # Arrange - corrupt payload must degrade honestly, never surface garbage
        tafsir_asset = baker.make(
            Asset,
            category=CategoryChoice.TAFSIR,
            publisher=self.publisher,
            status=StatusChoice.READY,
            name="Corrupt Tafsir",
            language="ar",
        )
        baker.make(
            AssetVersion, asset=tafsir_asset, name="v1", file_url=ContentFile(b"{not valid json", name="broken.json")
        )
        # Act
        response = self.client.get("/sample-data/tafsir/")
        # Assert
        self.assertEqual(404, response.status_code)
        self.assertEqual("tafsir_sample_verse_unavailable", response.json()["error_name"])

    def test_get_tafsir_sample_where_version_file_is_pdf_should_return_404(self):
        """Binary formats are never fetched or parsed for verses."""
        # Arrange - binary formats can never yield verses and are never fetched
        tafsir_asset = baker.make(
            Asset,
            category=CategoryChoice.TAFSIR,
            publisher=self.publisher,
            status=StatusChoice.READY,
            name="Pdf Tafsir",
            language="ar",
        )
        baker.make(AssetVersion, asset=tafsir_asset, name="v1", file_url=ContentFile(b"%PDF-1.4 fake", name="book.pdf"))
        # Act
        response = self.client.get("/sample-data/tafsir/")
        # Assert
        self.assertEqual(404, response.status_code)
        self.assertEqual("tafsir_sample_verse_unavailable", response.json()["error_name"])

    def test_get_tafsir_sample_where_no_tafsir_exists_should_return_404(self):
        """With no READY tafsir at all the dedicated endpoint reports tafsir_not_found."""
        # Arrange - no Tafsir assets with status=READY
        # Act
        response = self.client.get("/sample-data/tafsir/")
        # Assert
        self.assertEqual(404, response.status_code)
        data = response.json()
        self.assertEqual("tafsir_not_found", data["error_name"])

    def test_get_translation_sample_where_ready_asset_has_verse_file_should_return_real_text(self):
        """Translation text comes from the uploaded JSON, never fabricated."""
        # Arrange
        translation_asset = baker.make(
            Asset,
            category=CategoryChoice.TRANSLATION,
            publisher=self.publisher,
            status=StatusChoice.READY,
            name="Saheeh International",
            language="en",
            license="CC-BY-4.0",
        )
        verse_text = "In the name of Allah, the Entirely Merciful, the Especially Merciful."
        payload = json.dumps({"1:1": verse_text}).encode("utf-8")
        baker.make(
            AssetVersion, asset=translation_asset, name="v1", file_url=ContentFile(payload, name="translation.json")
        )
        # Act
        response = self.client.get("/sample-data/translation/")
        # Assert
        self.assertEqual(200, response.status_code)
        data = response.json()
        self.assertEqual(
            {"asset_id", "asset_name", "publisher", "language", "license", "sample_verse"}, set(data.keys())
        )
        self.assertEqual(translation_asset.id, data["asset_id"])
        self.assertEqual({"surah": 1, "ayah": 1, "text": verse_text}, data["sample_verse"])

    def test_get_translation_sample_where_asset_has_no_version_file_should_return_404(self):
        """Metadata-only translation assets report unavailable."""
        # Arrange - metadata-only asset
        baker.make(
            Asset,
            category=CategoryChoice.TRANSLATION,
            publisher=self.publisher,
            status=StatusChoice.READY,
            name="Metadata-only Translation",
            language="en",
        )
        # Act
        response = self.client.get("/sample-data/translation/")
        # Assert
        self.assertEqual(404, response.status_code)
        self.assertEqual("translation_sample_verse_unavailable", response.json()["error_name"])

    def test_get_translation_sample_where_no_translation_exists_should_return_404(self):
        """Empty surface -> translation_not_found."""
        # Arrange - no Translation assets with status=READY
        # Act
        response = self.client.get("/sample-data/translation/")
        # Assert
        self.assertEqual(404, response.status_code)
        data = response.json()
        self.assertEqual("translation_not_found", data["error_name"])

    def test_get_recitation_sample_where_complete_asset_exists_should_return_media_player_payload(self):
        """Full player payload: identities plus default-folder track metadata."""
        # Arrange
        recitation_asset = self._create_test_recitation_with_timing()
        track = RecitationSurahTrack.objects.get(asset=recitation_asset, surah_number=1)
        baker.make(
            RecitationAyahTiming,
            track=track,
            ayah_key="1:2",
            start_ms=3000,
            end_ms=6500,
            duration_ms=3500,
        )
        # Act
        response = self.client.get("/sample-data/recitation/")
        # Assert
        self.assertEqual(200, response.status_code)
        data = response.json()
        self.assertEqual({"id", "name", "reciter", "riwayah", "qiraah", "publisher", "sample_track"}, set(data.keys()))
        self.assertEqual(recitation_asset.id, data["id"])
        self.assertEqual("Test Recitation", data["name"])
        self.assertEqual({"id": self.reciter.id, "name": self.reciter.name}, data["reciter"])
        self.assertEqual({"id": self.riwayah.id, "name": self.riwayah.name}, data["riwayah"])
        self.assertEqual({"id": self.qiraah.id, "name": self.qiraah.name}, data["qiraah"])
        self.assertEqual({"id": self.publisher.id, "name": self.publisher.name}, data["publisher"])

    def test_get_recitation_sample_should_include_audio_url_duration_and_ordered_timings(self):
        """Audio URL follows the R2 convention; timings arrive ordered by start_ms."""
        # Arrange
        recitation_asset = self._create_test_recitation_with_timing()
        track = RecitationSurahTrack.objects.get(asset=recitation_asset, surah_number=1)
        baker.make(
            RecitationAyahTiming,
            track=track,
            ayah_key="1:2",
            start_ms=3000,
            end_ms=6500,
            duration_ms=3500,
        )
        # Act
        response = self.client.get("/sample-data/recitation/")
        # Assert
        self.assertEqual(200, response.status_code)
        sample_track = response.json()["sample_track"]
        self.assertEqual({"surah_number", "audio_url", "duration_ms", "ayah_timings"}, set(sample_track.keys()))
        self.assertEqual(1, sample_track["surah_number"])
        expected_base = settings.CLOUDFLARE_R2_PUBLIC_BASE_URL
        self.assertEqual(f"{expected_base}/media/{track.audio_file.name}", sample_track["audio_url"])
        self.assertEqual(15000, sample_track["duration_ms"])
        self.assertEqual([1, 2], [t["ayah_number"] for t in sample_track["ayah_timings"]])
        self.assertEqual(0, sample_track["ayah_timings"][0]["start_ms"])
        self.assertEqual(3000, sample_track["ayah_timings"][0]["end_ms"])
        self.assertEqual(6500, sample_track["ayah_timings"][1]["end_ms"])

    def test_get_recitation_sample_with_explicit_surah_should_return_that_track(self):
        """?surah selects that surah's track (empty timings list when none uploaded)."""
        # Arrange
        recitation_asset = self._create_test_recitation_with_timing()
        baker.make(
            RecitationSurahTrack,
            asset=recitation_asset,
            folder=RecitationFolder.objects.get(asset=recitation_asset, is_default=True),
            surah_number=2,
            audio_file=ContentFile(b"\x00", name="test-2.mp3"),
            duration_ms=42000,
        )
        # Act
        response = self.client.get("/sample-data/recitation/", {"surah": 2})
        # Assert
        self.assertEqual(200, response.status_code)
        sample_track = response.json()["sample_track"]
        self.assertEqual(2, sample_track["surah_number"])
        self.assertEqual(42000, sample_track["duration_ms"])
        self.assertEqual([], sample_track["ayah_timings"])

    def test_get_recitation_sample_where_incomplete_assets_only_should_skip_to_404(self):
        """Assets missing riwayah/qiraah/reciter are skipped, not filled with placeholders."""
        # Arrange - READY recitation without a riwayah cannot render the contract
        baker.make(
            Asset,
            category=CategoryChoice.RECITATION,
            publisher=self.publisher,
            status=StatusChoice.READY,
            reciter=self.reciter,
            qiraah=self.qiraah,
            riwayah=None,
            name="Incomplete Recitation",
            language="ar",
        )
        # Act
        response = self.client.get("/sample-data/recitation/")
        # Assert
        self.assertEqual(404, response.status_code)
        self.assertEqual("recitation_not_found", response.json()["error_name"])

    def test_get_recitation_sample_where_surah_track_missing_should_return_404(self):
        """A complete asset without the requested surah track still reports not found."""
        # Arrange
        self._create_test_recitation_with_timing()
        # Act
        response = self.client.get("/sample-data/recitation/", {"surah": 3})
        # Assert
        self.assertEqual(404, response.status_code)
        self.assertEqual("recitation_not_found", response.json()["error_name"])

    def test_get_recitation_sample_where_no_recitation_exists_should_return_404(self):
        """No READY recitations at all -> recitation_not_found."""
        # Arrange - no Recitation assets with status=READY
        # Act
        response = self.client.get("/sample-data/recitation/")
        # Assert
        self.assertEqual(404, response.status_code)
        data = response.json()
        self.assertEqual("recitation_not_found", data["error_name"])

    def test_get_joined_ayah_with_default_query_should_return_full_1_1_payload(self):
        """Defaults assemble the full 1:1 payload across all five domains."""
        # Arrange
        self._seed_versioned_asset(CategoryChoice.TAFSIR, "Tafsir al-Tabari", {"1:1": "نص التفسير"})
        self._seed_versioned_asset(CategoryChoice.TRANSLATION, "Saheeh International", {"1:1": "In the name of Allah"})
        self._create_test_recitation_with_timing()
        # Act
        response = self.client.get("/sample-data/joined-ayah/")
        # Assert
        self.assertEqual(200, response.status_code)
        data = response.json()
        self.assertEqual({"surah", "ayah", "tafsir", "translation", "recitation"}, set(data.keys()))
        self.assertEqual(
            {
                "id": 1,
                "name": "الفاتحة",
                "transliterated_name": "Al-Faatiha",
                "english_name": "The Opening",
                "ayas_count": 7,
                "revelation_type": "Meccan",
                "revelation_order": 5,
                "rukus_count": 1,
            },
            data["surah"],
        )
        self.assertEqual(1, data["ayah"]["surah_id"])
        self.assertEqual(1, data["ayah"]["number_in_surah"])
        self.assertEqual("نص الآية 1:1", data["ayah"]["text_uthmani"])
        self.assertEqual({"surah": 1, "ayah": 1, "text": "نص التفسير"}, data["tafsir"]["sample_verse"])
        self.assertEqual({"surah": 1, "ayah": 1, "text": "In the name of Allah"}, data["translation"]["sample_verse"])
        self.assertEqual(1, data["recitation"]["sample_track"]["surah_number"])
        self.assertEqual([1], [t["ayah_number"] for t in data["recitation"]["sample_track"]["ayah_timings"]])

    def test_get_joined_ayah_with_custom_location_should_represent_that_verse(self):
        """?surah=2&ayah=255 anchors every section to that exact verse."""
        # Arrange - everything anchored to 2:255
        self._seed_quran_location(2, 255)
        self._seed_versioned_asset(CategoryChoice.TAFSIR, "Tafsir 2-255", {"2:255": "تفسير الكرسي"})
        self._seed_versioned_asset(
            CategoryChoice.TRANSLATION, "Translation nested", {"2": {"255": "Allah, there is no god but He"}}
        )
        recitation_asset = self._create_test_recitation_with_timing()
        folder = recitation_asset.recitation_folders.get(is_default=True)
        baker.make(
            RecitationSurahTrack,
            asset=recitation_asset,
            folder=folder,
            surah_number=2,
            audio_file=ContentFile(b"\x00", name="test-2.mp3"),
            duration_ms=42000,
        )
        baker.make(
            RecitationAyahTiming,
            track=RecitationSurahTrack.objects.get(asset=recitation_asset, surah_number=2),
            ayah_key="2:255",
            start_ms=1000,
            end_ms=4000,
            duration_ms=3000,
        )
        # Act
        response = self.client.get("/sample-data/joined-ayah/", {"surah": 2, "ayah": 255})
        # Assert
        self.assertEqual(200, response.status_code)
        data = response.json()
        self.assertEqual(2, data["surah"]["id"])
        self.assertEqual("The Cow", data["surah"]["english_name"])
        self.assertEqual(255, data["ayah"]["number_in_surah"])
        self.assertEqual("نص الآية 2:255", data["ayah"]["text_uthmani"])
        self.assertEqual({"surah": 2, "ayah": 255, "text": "تفسير الكرسي"}, data["tafsir"]["sample_verse"])
        self.assertEqual(
            {"surah": 2, "ayah": 255, "text": "Allah, there is no god but He"},
            data["translation"]["sample_verse"],
        )
        sample_track = data["recitation"]["sample_track"]
        self.assertEqual(2, sample_track["surah_number"])
        surah2_track = RecitationSurahTrack.objects.get(asset=recitation_asset, surah_number=2)
        self.assertEqual(
            f"{settings.CLOUDFLARE_R2_PUBLIC_BASE_URL}/media/{surah2_track.audio_file.name}",
            sample_track["audio_url"],
        )
        self.assertEqual(42000, sample_track["duration_ms"])
        self.assertEqual([255], [t["ayah_number"] for t in sample_track["ayah_timings"]])
        self.assertEqual(1000, sample_track["ayah_timings"][0]["start_ms"])

    def test_get_joined_ayah_where_surah_missing_should_return_sura_not_found(self):
        """Missing anchor sura fails the whole request with sura_not_found."""
        # Arrange - only Surah 1 exists in setUp
        # Act
        response = self.client.get("/sample-data/joined-ayah/", {"surah": 3, "ayah": 1})
        # Assert
        self.assertEqual(404, response.status_code)
        self.assertEqual("sura_not_found", response.json()["error_name"])

    def test_get_joined_ayah_where_ayah_missing_should_return_ayah_not_found(self):
        """Missing anchor ayah fails the whole request with ayah_not_found."""
        # Arrange - Surah 1 has only ayah 1
        # Act
        response = self.client.get("/sample-data/joined-ayah/", {"surah": 1, "ayah": 8})
        # Assert
        self.assertEqual(404, response.status_code)
        self.assertEqual("ayah_not_found", response.json()["error_name"])

    def test_get_joined_ayah_where_content_cannot_provide_verse_should_null_sections(self):
        """Sections unable to serve the anchored verse degrade to null (no fabrication)."""
        # Arrange - tafsir file lacks 1:1; translation has no file at all
        self._seed_versioned_asset(CategoryChoice.TAFSIR, "Partial Tafsir", {"2:255": "غير هنا"})
        baker.make(
            Asset,
            category=CategoryChoice.TRANSLATION,
            publisher=self.publisher,
            status=StatusChoice.READY,
            name="Metadata-only Translation",
            language="en",
        )
        self._create_test_recitation_with_timing()
        # Act
        response = self.client.get("/sample-data/joined-ayah/")
        # Assert
        self.assertEqual(200, response.status_code)
        data = response.json()
        self.assertIsNone(data["tafsir"])
        self.assertIsNone(data["translation"])
        self.assertIsNotNone(data["recitation"])

    def test_get_joined_ayah_where_no_recitation_exists_should_return_null_recitation(self):
        """Recitation section alone degrades while content sections stay populated."""
        # Arrange
        self._seed_versioned_asset(CategoryChoice.TAFSIR, "Tafsir al-Tabari", {"1:1": "نص التفسير"})
        self._seed_versioned_asset(CategoryChoice.TRANSLATION, "Saheeh International", {"1:1": "In the name of Allah"})
        # Act
        response = self.client.get("/sample-data/joined-ayah/")
        # Assert
        self.assertEqual(200, response.status_code)
        data = response.json()
        self.assertIsNone(data["recitation"])
        self.assertIsNotNone(data["tafsir"])
        self.assertIsNotNone(data["translation"])

    def test_get_joined_ayah_where_params_out_of_range_should_return_validation_error(self):
        """Bounds violations return 400 validation_error before any data access."""
        # Act
        response = self.client.get("/sample-data/joined-ayah/", {"surah": 115, "ayah": 1})
        # Assert
        self.assertEqual(400, response.status_code)
        self.assertEqual("validation_error", response.json()["error_name"])

    def test_get_tafsir_sample_where_two_ayahs_requested_from_one_version_should_parse_file_only_once(self):
        """Two distinct ayahs from one version open/parse the stored file exactly once."""
        # Arrange - one version carrying two valid verses
        self._seed_versioned_asset(
            CategoryChoice.TAFSIR,
            "Multi-verse Tafsir",
            {"1:1": "نص الآية الأولى", "1:2": "نص الآية الثانية"},
        )
        real_reader = asset_verse_text._read_version_json
        parse_calls = []

        def counting_reader(version):
            parse_calls.append(version)
            return real_reader(version)

        # Act - two DIFFERENT ayahs from the same version, then a repeat of the first
        with mock.patch.object(
            asset_verse_text, asset_verse_text._read_version_json.__name__, side_effect=counting_reader
        ):
            first = self.client.get("/sample-data/tafsir/", {"surah": 1, "ayah": 1})
            second = self.client.get("/sample-data/tafsir/", {"surah": 1, "ayah": 2})
            repeat = self.client.get("/sample-data/tafsir/", {"surah": 1, "ayah": 1})
        # Assert - every response correct; storage open+parse ran exactly once
        self.assertEqual(200, first.status_code)
        self.assertEqual(200, second.status_code)
        self.assertEqual("نص الآية الأولى", first.json()["sample_verse"]["text"])
        self.assertEqual("نص الآية الثانية", second.json()["sample_verse"]["text"])
        self.assertEqual("نص الآية الأولى", repeat.json()["sample_verse"]["text"])
        self.assertEqual(1, len(parse_calls))

    def test_get_tafsir_sample_where_version_file_updated_in_place_should_return_fresh_text_immediately(self):
        """In-place updates go through full Model.save(), bumping updated_at -> key rotates."""
        # Arrange - first request caches the original text for this version
        tafsir_asset = self._seed_versioned_asset(CategoryChoice.TAFSIR, "Cached Tafsir", {"1:1": "النص الأصلي"})
        first = self.client.get("/sample-data/tafsir/")
        # Act - mirror the real portal update flow (repo assigns the file then
        # calls the FULL model save), so auto_now bumps updated_at and the
        # cache key rotates without any manual invalidation.
        version = tafsir_asset.versions.get()
        version.file_url = ContentFile(
            json.dumps({"1:1": "النص المحدَّث"}, ensure_ascii=False).encode("utf-8"), name="tafsir.json"
        )
        version.save()
        refreshed = self.client.get("/sample-data/tafsir/")
        # Assert - fresh text served right away (no stale window inside the TTL)
        self.assertEqual(200, first.status_code)
        self.assertEqual(200, refreshed.status_code)
        self.assertEqual("النص المحدَّث", refreshed.json()["sample_verse"]["text"])

    def test_get_tafsir_sample_where_newer_version_becomes_latest_should_serve_its_text(self):
        """Scenario A: adding a new AssetVersion row rotates the key via its pk."""
        # Arrange - v1 text read and cached
        tafsir_asset = self._seed_versioned_asset(CategoryChoice.TAFSIR, "Versioned Tafsir", {"1:1": "الإصدار الأول"})
        before = self.client.get("/sample-data/tafsir/")
        # Act - a NEW row becomes latest (get_latest_version orders by -created_at)
        baker.make(
            AssetVersion,
            asset=tafsir_asset,
            name="v2",
            file_url=ContentFile(
                json.dumps({"1:1": "الإصدار الثاني"}, ensure_ascii=False).encode("utf-8"), name="v2.json"
            ),
        )
        after = self.client.get("/sample-data/tafsir/")
        # Assert - response comes from v2, not stale v1
        self.assertEqual(200, before.status_code)
        self.assertEqual("الإصدار الأول", before.json()["sample_verse"]["text"])
        self.assertEqual({"surah": 1, "ayah": 1, "text": "الإصدار الثاني"}, after.json()["sample_verse"])

    def test_get_tafsir_sample_where_verse_missing_should_serve_negative_cache_without_rereading_file(self):
        """Negative caching: the repeated 404 is served without touching storage."""
        # Arrange - file exists but lacks 1:1 -> negative result gets cached
        self._seed_versioned_asset(CategoryChoice.TAFSIR, "Late Tafsir", {"2:255": "غير ذات صلة"})
        before = self.client.get("/sample-data/tafsir/")
        # Act - second request must be served from the negative-cache sentinel;
        # any attempt to re-read/parse the stored file fails the test loudly.
        with mock.patch.object(
            asset_verse_text,
            asset_verse_text._read_version_json.__name__,
            side_effect=AssertionError("negative cache must not re-read the version file"),
        ):
            still_cached = self.client.get("/sample-data/tafsir/")
        # Assert
        self.assertEqual(404, before.status_code)
        self.assertEqual(404, still_cached.status_code)
        self.assertEqual("tafsir_sample_verse_unavailable", still_cached.json()["error_name"])

    def test_get_tafsir_sample_where_new_version_row_contains_verse_should_overcome_previous_unavailable(self):
        """Scenario B: a negative-cached miss must not outlive its own version row."""
        # Arrange - v1 exists but lacks 1:1 -> negative entry cached under v1's identity
        tafsir_asset = self._seed_versioned_asset(CategoryChoice.TAFSIR, "Late Tafsir", {"2:255": "غير ذات صلة"})
        before = self.client.get("/sample-data/tafsir/")
        # Act - a NEW version row carries the verse (different pk -> different key)
        baker.make(
            AssetVersion,
            asset=tafsir_asset,
            name="v2",
            file_url=ContentFile(json.dumps({"1:1": "نص متأخر"}, ensure_ascii=False).encode("utf-8"), name="v2.json"),
        )
        after = self.client.get("/sample-data/tafsir/")  # no manual cache.clear()
        # Assert - real verse served from the new version, old negative entry ignored
        self.assertEqual(404, before.status_code)
        self.assertEqual(200, after.status_code)
        self.assertEqual({"surah": 1, "ayah": 1, "text": "نص متأخر"}, after.json()["sample_verse"])

    def test_get_joined_ayah_where_available_should_match_individual_endpoints_responses(self):
        """Every joined section equals its dedicated endpoint response byte-for-byte."""
        # Arrange
        self._seed_versioned_asset(CategoryChoice.TAFSIR, "Tafsir al-Tabari", {"1:1": "نص التفسير"})
        self._seed_versioned_asset(CategoryChoice.TRANSLATION, "Saheeh International", {"1:1": "In the name of Allah"})
        self._create_test_recitation_with_timing()
        # Act
        surah_resp = self.client.get("/sample-data/surah/")
        ayah_resp = self.client.get("/sample-data/ayah/")
        tafsir_resp = self.client.get("/sample-data/tafsir/")
        translation_resp = self.client.get("/sample-data/translation/")
        recitation_resp = self.client.get("/sample-data/recitation/")
        joined_resp = self.client.get("/sample-data/joined-ayah/")
        joined = joined_resp.json()
        # Assert - every joined section is byte-for-byte the individual endpoint payload
        self.assertEqual(200, joined_resp.status_code)
        self.assertEqual(surah_resp.json(), joined["surah"])
        self.assertEqual(ayah_resp.json(), joined["ayah"])
        self.assertEqual(tafsir_resp.json(), joined["tafsir"])
        self.assertEqual(translation_resp.json(), joined["translation"])
        self.assertEqual(recitation_resp.json(), joined["recitation"])
