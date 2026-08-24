"""Tests for content sample endpoints (tafsir, translation, recitation, joined-ayah)."""

import json

from django.conf import settings
from django.core.cache import cache
from django.core.files.base import ContentFile
from django.test import TestCase
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
from apps.publishers.models import Publisher
from apps.quran.models import Ayah, Sura


class ContentSamplesTest(TestCase):
    """Tests for /sample-data/tafsir/, /sample-data/translation/, /sample-data/recitation/, and /sample-data/joined-ayah/ endpoints."""

    def setUp(self):
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
        # Arrange - no Tafsir assets with status=READY
        # Act
        response = self.client.get("/sample-data/tafsir/")
        # Assert
        self.assertEqual(404, response.status_code)
        data = response.json()
        self.assertEqual("tafsir_not_found", data["error_name"])

    def test_get_translation_sample_where_ready_asset_has_verse_file_should_return_real_text(self):
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
        # Arrange - no Translation assets with status=READY
        # Act
        response = self.client.get("/sample-data/translation/")
        # Assert
        self.assertEqual(404, response.status_code)
        data = response.json()
        self.assertEqual("translation_not_found", data["error_name"])

    def test_get_recitation_sample_where_complete_asset_exists_should_return_media_player_payload(self):
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
        # Arrange
        self._create_test_recitation_with_timing()
        # Act
        response = self.client.get("/sample-data/recitation/", {"surah": 3})
        # Assert
        self.assertEqual(404, response.status_code)
        self.assertEqual("recitation_not_found", response.json()["error_name"])

    def test_get_recitation_sample_where_no_recitation_exists_should_return_404(self):
        # Arrange - no Recitation assets with status=READY
        # Act
        response = self.client.get("/sample-data/recitation/")
        # Assert
        self.assertEqual(404, response.status_code)
        data = response.json()
        self.assertEqual("recitation_not_found", data["error_name"])

    def test_get_joined_ayah_with_default_query_should_return_full_1_1_payload(self):
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
        # Arrange - only Surah 1 exists in setUp
        # Act
        response = self.client.get("/sample-data/joined-ayah/", {"surah": 3, "ayah": 1})
        # Assert
        self.assertEqual(404, response.status_code)
        self.assertEqual("sura_not_found", response.json()["error_name"])

    def test_get_joined_ayah_where_ayah_missing_should_return_ayah_not_found(self):
        # Arrange - Surah 1 has only ayah 1
        # Act
        response = self.client.get("/sample-data/joined-ayah/", {"surah": 1, "ayah": 8})
        # Assert
        self.assertEqual(404, response.status_code)
        self.assertEqual("ayah_not_found", response.json()["error_name"])

    def test_get_joined_ayah_where_content_cannot_provide_verse_should_null_sections(self):
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
        # Act
        response = self.client.get("/sample-data/joined-ayah/", {"surah": 115, "ayah": 1})
        # Assert
        self.assertEqual(400, response.status_code)
        self.assertEqual("validation_error", response.json()["error_name"])

    def test_get_tafsir_sample_where_file_updated_within_cache_ttl_should_serve_cached_text_then_refresh_after_clear(
        self,
    ):
        # Arrange - first request caches the original text for this version
        tafsir_asset = self._seed_versioned_asset(CategoryChoice.TAFSIR, "Cached Tafsir", {"1:1": "النص الأصلي"})
        version = tafsir_asset.versions.get()
        first = self.client.get("/sample-data/tafsir/")
        # Act - overwrite the SAME version's file (same cache key) with new text
        version.file_url.save(
            "tafsir.json",
            ContentFile(json.dumps({"1:1": "النص المحدَّث"}, ensure_ascii=False).encode("utf-8")),
            save=True,
        )
        cached = self.client.get("/sample-data/tafsir/")
        cache.clear()  # simulate TTL expiry / invalidation
        refreshed = self.client.get("/sample-data/tafsir/")
        # Assert - stale text served within TTL window, fresh text after invalidation
        self.assertEqual(200, first.status_code)
        self.assertEqual("النص الأصلي", cached.json()["sample_verse"]["text"])
        self.assertEqual("النص المحدَّث", refreshed.json()["sample_verse"]["text"])

    def test_get_tafsir_sample_where_verse_added_after_negative_cache_should_stay_unavailable_until_cache_cleared(self):
        # Arrange - file exists but lacks 1:1 -> negative result gets cached
        tafsir_asset = self._seed_versioned_asset(CategoryChoice.TAFSIR, "Late Tafsir", {"2:255": "غير ذات صلة"})
        before = self.client.get("/sample-data/tafsir/")
        version = tafsir_asset.versions.get()
        # Act - verse becomes available on the same version (same negative-cache key)
        version.file_url.save(
            "tafsir.json",
            ContentFile(json.dumps({"1:1": "نص متأخر"}, ensure_ascii=False).encode("utf-8"), name="late.json"),
            save=True,
        )
        still_cached = self.client.get("/sample-data/tafsir/")
        cache.clear()
        after = self.client.get("/sample-data/tafsir/")
        # Assert - negative cache holds until invalidated, then the real text is served
        self.assertEqual(404, before.status_code)
        self.assertEqual(404, still_cached.status_code)
        self.assertEqual("tafsir_sample_verse_unavailable", still_cached.json()["error_name"])
        self.assertEqual(200, after.status_code)
        self.assertEqual({"surah": 1, "ayah": 1, "text": "نص متأخر"}, after.json()["sample_verse"])

    def test_get_joined_ayah_where_available_should_match_individual_endpoints_responses(self):
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
