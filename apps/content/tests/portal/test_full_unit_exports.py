import csv
import io

from model_bakery import baker

from apps.content.models import (
    Asset,
    AssetTemplateChoice,
    AssetVersion,
    AssetVersionEntry,
    CategoryChoice,
    MushafLayout,
    StatusChoice,
    VersionStateChoice,
)
from apps.content.repositories.asset_content import AssetContentRepository
from apps.content.services.asset_content_import import parse_content_file
from apps.content.services.asset_templates import unit_spec_for
from apps.core.permissions import PermissionChoice
from apps.core.tests.base import BaseTestCase
from apps.publishers.models import Publisher
from apps.quran.models import Ayah, Sura, Word
from apps.users.models import User


def _rows(content: bytes) -> list[list[str]]:
    return list(csv.reader(io.StringIO(content.decode("utf-8"))))


class FullUnitExportTests(BaseTestCase):
    """Downloads list every unit of the template, with blank text where the
    version has none, so the file is a complete sheet to fill in."""

    def setUp(self):
        super().setUp()
        self.publisher = baker.make(Publisher, name="Export Publisher")
        self.sura1 = baker.make(Sura, id=1, name="الفاتحة", ayas_count=2)
        self.sura2 = baker.make(Sura, id=2, name="البقرة", ayas_count=1)
        self.ayahs = [
            baker.make(Ayah, id=1, sura=self.sura1, number_in_sura=1, text="a1"),
            baker.make(Ayah, id=2, sura=self.sura1, number_in_sura=2, text="a2"),
            baker.make(Ayah, id=3, sura=self.sura2, number_in_sura=1, text="a3"),
        ]
        self.words = [
            baker.make(Word, id=1, sura=self.sura1, ayah=self.ayahs[0], position_in_ayah=1, text="w1"),
            baker.make(Word, id=2, sura=self.sura1, ayah=self.ayahs[0], position_in_ayah=2, text="w2"),
        ]
        self.repo = AssetContentRepository()

    def _version(self, template: str, **asset_kwargs) -> AssetVersion:
        asset = baker.make(
            Asset,
            publisher=self.publisher,
            category=CategoryChoice.TAFSIR,
            template=template,
            status=StatusChoice.READY,
            language="ar",
            **asset_kwargs,
        )
        return baker.make(
            AssetVersion,
            asset=asset,
            asset_language=asset.get_or_create_source_language(),
            name="v1",
            state=VersionStateChoice.PUBLISHED,
        )

    def test_entries_to_csv_bytes_where_ayah_version_is_partial_should_list_every_ayah(self):
        # Arrange
        version = self._version(AssetTemplateChoice.AYAH)
        baker.make(AssetVersionEntry, version=version, ayah=self.ayahs[1], text="tafsir of 1:2", order=2)

        # Act
        rows = _rows(self.repo.entries_to_csv_bytes(version, unit_spec_for(version.asset)))

        # Assert
        self.assertEqual(rows, [["surah", "ayah", "text"], ["1", "1", ""], ["1", "2", "tafsir of 1:2"], ["2", "1", ""]])

    def test_entries_to_csv_bytes_where_surah_version_is_partial_should_list_every_surah(self):
        # Arrange
        version = self._version(AssetTemplateChoice.SURAH)
        baker.make(AssetVersionEntry, version=version, sura=self.sura2, text="about al-baqara", order=2)

        # Act
        rows = _rows(self.repo.entries_to_csv_bytes(version, unit_spec_for(version.asset)))

        # Assert
        self.assertEqual(rows, [["sura", "text"], ["1", ""], ["2", "about al-baqara"]])

    def test_entries_to_csv_bytes_where_word_version_is_empty_should_list_every_word(self):
        # Arrange
        version = self._version(AssetTemplateChoice.WORD)

        # Act
        rows = _rows(self.repo.entries_to_csv_bytes(version, unit_spec_for(version.asset)))

        # Assert
        self.assertEqual(
            rows, [["word_id", "sura", "aya", "word", "text"], ["1", "1", "1", "1", ""], ["2", "1", "1", "2", ""]]
        )

    def test_snapshot_to_csv_bytes_where_page_snapshot_is_partial_should_list_every_page(self):
        # Arrange
        layout = baker.make(MushafLayout, name="Tiny 3", page_count=3)
        version = self._version(AssetTemplateChoice.PAGE, mushaf_layout=layout)

        # Act
        content = self.repo.snapshot_to_csv_bytes({2: "page two"}, unit_spec_for(version.asset), asset=version.asset)

        # Assert
        self.assertEqual(_rows(content), [["page", "text"], ["1", ""], ["2", "page two"], ["3", ""]])

    def test_export_version_where_translation_is_partial_should_download_every_ayah(self):
        # Arrange
        user = User.objects.create_user(email="exporter@example.com", name="Exporter", is_staff=True)
        self.give_permission(user, PermissionChoice.PORTAL_ACCESS_ALL_LANGUAGES)
        self.give_permission(user, PermissionChoice.PORTAL_READ_TAFSIR)
        version = self._version(AssetTemplateChoice.AYAH, slug="partial-tafsir")
        baker.make(AssetVersionEntry, version=version, ayah=self.ayahs[0], text="first", order=1)
        self.authenticate_user(user)

        # Act
        response = self.client.get(f"/portal/content/tafsirs/partial-tafsir/versions/{version.id}/export/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        rows = _rows(response.content)
        self.assertEqual(len(rows), 1 + len(self.ayahs))
        self.assertEqual([row[-1] for row in rows[1:]], ["first", "", ""])

    def test_parse_content_file_where_full_export_has_blank_rows_should_import_only_filled_units(self):
        # Arrange: re-uploading a full export must not create an empty entry per blank row.
        version = self._version(AssetTemplateChoice.AYAH)
        content = b"surah,ayah,text\n1,1,\n1,2,tafsir of 1:2\n2,1,\n"

        # Act
        parsed = parse_content_file(content, unit_spec_for(version.asset), version.asset)

        # Assert
        self.assertEqual([(entry.unit_id, entry.text) for entry in parsed], [(2, "tafsir of 1:2")])
