import json
from unittest.mock import MagicMock

from django.core.files.uploadedfile import SimpleUploadedFile

from apps.content.admin import ContentIssueReportAdmin
from apps.content.models import (
    Asset,
    AssetLanguage,
    AssetTemplateChoice,
    AssetVersion,
    AssetVersionEntry,
    CategoryChoice,
    ContentIssueReport,
    Qiraah,
    RecitationAyahTiming,
    RecitationFolder,
    RecitationSurahTrack,
    Reciter,
    VersionStateChoice,
)
from apps.content.repositories.asset_content import AssetContentRepository
from apps.content.services.admin.asset_recitation_ayah_timestamps_upload_service import (
    bulk_upload_recitation_ayah_timestamps,
)
from apps.content.services.asset_content_import import ParsedEntry
from apps.content.services.asset_language_backfill import backfill_source_languages
from apps.content.services.asset_templates import unit_spec_for
from apps.content.services.recitation_folder import RecitationFolderService
from apps.core.tests.base import BaseTestCase
from apps.publishers.models import Publisher
from apps.quran.models import Ayah, Sura
from apps.users.models import User


class ContentBulkHistoryTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.publisher = Publisher.objects.create(name="Content Publisher", slug="content-pub")
        self.user = User.objects.create_user(email="editor@example.com", name="Editor")
        self.asset = Asset.objects.create(
            publisher=self.publisher,
            name="Test Translation",
            name_en="Test Translation",
            name_ar="ترجمة تجريبية",
            category=CategoryChoice.TRANSLATION,
            template=AssetTemplateChoice.AYAH,
            slug="test-trans",
            language="en",
        )
        self.lang = AssetLanguage.objects.create(asset=self.asset, language="en", is_source=True)
        self.repo = AssetContentRepository()

        # Ensure reference Ayah exists
        self.sura, _ = Sura.objects.get_or_create(
            id=1,
            defaults={
                "name": "Al-Fatiha",
                "transliterated_name": "Al-Faatiha",
                "english_name": "The Opening",
                "ayas_count": 7,
                "start_offset": 0,
                "revelation_type": "Meccan",
                "revelation_order": 5,
                "rukus_count": 1,
            },
        )
        self.ayah, _ = Ayah.objects.get_or_create(
            id=1,
            defaults={
                "sura": self.sura,
                "number_in_sura": 1,
                "text": "بِسْمِ اللَّهِ الرَّحْمَٰنِ الرَّحِيمِ",
                "juz": 1,
                "hizb_quarter": 1,
                "page": 1,
            },
        )

    def test_ensure_mushaf_coverage_where_ayahas_missing_should_write_create_history_records(self):
        # Arrange: create draft version and mushaf version with an entry
        mushaf_asset = Asset.objects.create(
            publisher=self.publisher,
            name="Source Mushaf",
            name_en="Source Mushaf",
            name_ar="المصحف المصدر",
            category=CategoryChoice.MUSHAF,
            slug="source-mushaf",
        )
        mushaf_lang = AssetLanguage.objects.create(asset=mushaf_asset, language="ar", is_source=True)
        mushaf_version = AssetVersion.objects.create(
            asset=mushaf_asset,
            asset_language=mushaf_lang,
            name="1.0.0",
            state=VersionStateChoice.PUBLISHED,
        )
        AssetVersionEntry.objects.create(version=mushaf_version, ayah=self.ayah, text="بِسْمِ اللَّهِ", order=1)

        draft = AssetVersion.objects.create(
            asset=self.asset,
            asset_language=self.lang,
            name="0.1.0",
            state=VersionStateChoice.DRAFT,
        )

        # Act: ensure coverage (should bulk create empty row for missing ayah)
        added = self.repo.ensure_mushaf_coverage(draft, mushaf_version)

        # Assert: 1 row added and history record created in audit DB with '+'
        assert added == 1
        entry = draft.entries.get(ayah=self.ayah)
        assert entry.text == ""

        h = entry.history.order_by("-history_date").first()
        assert h is not None
        assert h.history_type == "+"
        assert h.text == ""

    def test_upsert_entries_where_new_and_updated_rows_should_write_create_and_update_history(self):
        # Arrange: draft with an existing entry
        draft = AssetVersion.objects.create(
            asset=self.asset,
            asset_language=self.lang,
            name="0.2.0",
            state=VersionStateChoice.DRAFT,
        )
        existing_entry = AssetVersionEntry.objects.create(
            version=draft, ayah=self.ayah, text="Old Translation", order=1
        )
        initial_history_count = existing_entry.history.count()

        # Create a second ayah
        ayah2, _ = Ayah.objects.get_or_create(
            id=2,
            defaults={
                "sura": self.sura,
                "number_in_sura": 2,
                "text": "الْحَمْدُ لِلَّهِ رَبِّ الْعَالَمِينَ",
                "juz": 1,
                "hizb_quarter": 1,
                "page": 1,
            },
        )

        spec = unit_spec_for(self.asset)
        rows = [
            {"unit_id": 1, "text": "Updated Translation"},
            {"unit_id": 2, "text": "New Translation 2"},
        ]

        # Act: upsert entries (one update, one create)
        changed = self.repo.upsert_entries(draft, spec, rows)

        # Assert: two entries returned
        assert len(changed) == 2
        existing_entry.refresh_from_db()
        assert existing_entry.text == "Updated Translation"

        new_entry = draft.entries.get(ayah_id=2)
        assert new_entry.text == "New Translation 2"

        # Assert: existing entry has update (~) history record
        latest_existing_h = existing_entry.history.order_by("-history_date").first()
        assert latest_existing_h.history_type == "~"
        assert latest_existing_h.text == "Updated Translation"
        assert existing_entry.history.count() == initial_history_count + 1

        # Assert: new entry has create (+) history record
        new_h = new_entry.history.order_by("-history_date").first()
        assert new_h is not None
        assert new_h.history_type == "+"
        assert new_h.text == "New Translation 2"

    def test_replace_entries_from_parsed_where_rows_provided_should_write_history(self):
        # Arrange: draft version
        draft = AssetVersion.objects.create(
            asset=self.asset,
            asset_language=self.lang,
            name="0.3.0",
            state=VersionStateChoice.DRAFT,
        )
        spec = unit_spec_for(self.asset)
        parsed = [
            ParsedEntry(unit_id=1, text="Parsed text 1"),
        ]

        # Act: replace entries
        count = self.repo.replace_entries_from_parsed(draft, spec, parsed)

        # Assert: 1 entry created with history
        assert count == 1
        entry = draft.entries.get(ayah_id=1)
        assert entry.text == "Parsed text 1"

        h = entry.history.order_by("-history_date").first()
        assert h is not None
        assert h.history_type == "+"
        assert h.text == "Parsed text 1"

    def test_commit_draft_where_changes_detected_should_write_asset_version_change_history(self):
        # Arrange: published v1 and draft v2
        v1 = AssetVersion.objects.create(
            asset=self.asset,
            asset_language=self.lang,
            name="1.0.0",
            state=VersionStateChoice.PUBLISHED,
        )
        AssetVersionEntry.objects.create(version=v1, ayah=self.ayah, text="Old Text", order=1)

        v2 = AssetVersion.objects.create(
            asset=self.asset,
            asset_language=self.lang,
            name="2.0.0",
            state=VersionStateChoice.DRAFT,
            content_edited=True,
        )
        AssetVersionEntry.objects.create(version=v2, ayah=self.ayah, text="New Committed Text", order=1)

        # Act: record changes
        counts = self.repo._record_changes(v2, v1)

        # Assert: changes recorded with history
        assert counts["modified"] == 1
        changes = list(v2.changes.all())
        assert len(changes) == 1

        change = changes[0]
        h = change.history.order_by("-history_date").first()
        assert h is not None
        assert h.history_type == "+"
        assert h.new_text == "New Committed Text"

    def test_content_issue_report_bulk_status_update_where_executed_should_write_history(self):
        # Arrange: create issue reports
        r1 = ContentIssueReport.objects.create(
            asset=self.asset,
            reporter=self.user,
            description="Typo on ayah 1 in translation",
            status=ContentIssueReport.StatusChoice.PENDING,
        )
        r2 = ContentIssueReport.objects.create(
            asset=self.asset,
            reporter=self.user,
            description="Typo on ayah 2 in translation",
            status=ContentIssueReport.StatusChoice.PENDING,
        )

        admin = ContentIssueReportAdmin(ContentIssueReport, None)
        request = MagicMock()
        request.user = self.user

        # Act: run bulk update action
        qs = ContentIssueReport.objects.filter(id__in=[r1.id, r2.id])
        admin._bulk_update_status(request, qs, ContentIssueReport.StatusChoice.UNDER_REVIEW, "under review")

        # Assert: default DB status updated
        r1.refresh_from_db()
        r2.refresh_from_db()
        assert r1.status == ContentIssueReport.StatusChoice.UNDER_REVIEW
        assert r2.status == ContentIssueReport.StatusChoice.UNDER_REVIEW

        # Assert: audit DB has update (~) record with history_user_id
        h1 = r1.history.order_by("-history_date").first()
        h2 = r2.history.order_by("-history_date").first()
        assert h1.history_type == "~"
        assert h1.status == ContentIssueReport.StatusChoice.UNDER_REVIEW
        assert h1.history_user_id == self.user.id
        assert h2.history_type == "~"
        assert h2.status == ContentIssueReport.StatusChoice.UNDER_REVIEW
        assert h2.history_user_id == self.user.id

    def test_recitation_folder_promote_to_default_where_demotes_other_should_write_history(self):
        # Arrange: recitation asset with two folders
        reciter = Reciter.objects.create(name="Reciter 1", name_en="Reciter 1", name_ar="القارئ 1", slug="reciter-1")
        qiraah = Qiraah.objects.create(name="Qiraah 1", name_en="Qiraah 1", name_ar="القراءة 1", slug="qiraah-1")
        rec_asset = Asset.objects.create(
            publisher=self.publisher,
            name="Recitation Asset",
            name_en="Recitation Asset",
            name_ar="تلاوة",
            category=CategoryChoice.RECITATION,
            reciter=reciter,
            qiraah=qiraah,
            slug="rec-asset",
        )
        folder1 = RecitationFolder.objects.get(asset=rec_asset, is_default=True)
        folder2 = RecitationFolder.objects.create(asset=rec_asset, name="Folder 2", slug="f2", is_default=False)
        initial_h1_count = folder1.history.count()

        service = RecitationFolderService()

        # Act: promote folder 2 to default
        service._promote_to_default(folder2)

        # Assert: folder1 demoted and folder2 promoted
        folder1.refresh_from_db()
        folder2.refresh_from_db()
        assert folder1.is_default is False
        assert folder2.is_default is True

        # Assert: folder1 has update history record in audit DB
        latest_h1 = folder1.history.order_by("-history_date").first()
        assert latest_h1.history_type == "~"
        assert latest_h1.is_default is False
        assert folder1.history.count() == initial_h1_count + 1

    def test_backfill_source_languages_where_versions_unlinked_should_write_history(self):
        # Arrange: version lacking asset_language (clear via update since save auto-assigns)
        v = AssetVersion.objects.create(
            asset=self.asset,
            name="1.0.0",
            state=VersionStateChoice.PUBLISHED,
        )
        AssetVersion.objects.filter(id=v.id).update(asset_language=None)
        v.refresh_from_db()
        assert v.asset_language_id is None

        # Act: run backfill
        backfill_source_languages(Asset, AssetLanguage, AssetVersion)

        # Assert: version is linked in default DB
        v.refresh_from_db()
        assert v.asset_language_id == self.lang.id

        # Assert: history record generated for the update
        latest_h = v.history.order_by("-history_date").first()
        assert latest_h is not None
        assert latest_h.history_type == "~"
        assert latest_h.asset_language_id == self.lang.id

    def test_bulk_upload_recitation_ayah_timestamps_where_new_and_existing_should_preserve_history(self):
        # Arrange: create recitation asset, track, and timing payload
        reciter = Reciter.objects.create(
            name="Reciter Timings", name_en="Reciter Timings", name_ar="القارئ", slug="reciter-timings"
        )
        qiraah = Qiraah.objects.create(
            name="Qiraah Timings", name_en="Qiraah Timings", name_ar="القراءة", slug="qiraah-timings"
        )
        rec_asset = Asset.objects.create(
            publisher=self.publisher,
            name="Recitation Timings Asset",
            name_en="Recitation Timings Asset",
            name_ar="تلاوة",
            category=CategoryChoice.RECITATION,
            reciter=reciter,
            qiraah=qiraah,
            slug="rec-timings-asset",
        )
        folder = RecitationFolder.objects.get(asset=rec_asset, is_default=True)
        track = RecitationSurahTrack.objects.create(
            asset=rec_asset,
            folder=folder,
            surah_number=1,
            audio_file=SimpleUploadedFile("001.mp3", b"dummy audio"),
        )

        def make_file(start_sec: float, end_sec: float) -> SimpleUploadedFile:
            payload = json.dumps(
                {"surah_id": 1, "ayahs": [{"ayah_number": 1, "start": start_sec, "end": end_sec}]}
            ).encode()
            return SimpleUploadedFile("001.json", payload, content_type="application/json")

        # Act 1: Initial upload (triggers bulk_create_with_history)
        bulk_upload_recitation_ayah_timestamps(asset_id=rec_asset.id, files=[make_file(0.5, 1.5)], folder_id=folder.id)

        # Assert 1: timing created with '+' history
        timing = RecitationAyahTiming.objects.get(track=track, ayah_key="1:1")
        assert timing.start_ms == 500
        assert timing.end_ms == 1500
        h1 = timing.history.order_by("-history_date").first()
        assert h1 is not None
        assert h1.history_type == "+"
        assert h1.start_ms == 500

        # Act 2: Second upload with modified timestamp (triggers bulk_update_with_history)
        bulk_upload_recitation_ayah_timestamps(asset_id=rec_asset.id, files=[make_file(0.7, 2.0)], folder_id=folder.id)

        # Assert 2: timing updated with '~' history
        timing.refresh_from_db()
        assert timing.start_ms == 700
        assert timing.end_ms == 2000
        h2 = timing.history.order_by("-history_date").first()
        assert h2 is not None
        assert h2.history_type == "~"
        assert h2.start_ms == 700
        assert timing.history.count() == 2
