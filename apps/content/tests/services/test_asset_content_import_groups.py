from django.core.files.uploadedfile import SimpleUploadedFile
from model_bakery import baker

from apps.content.models import (
    Asset,
    AssetLanguage,
    AssetTemplateChoice,
    AssetVersion,
    AssetVersionEntry,
    CategoryChoice,
    StatusChoice,
    VersionStateChoice,
)
from apps.content.repositories.asset_content import AssetContentRepository
from apps.content.services.asset_content_import import (
    AssetContentInvalidRowsError,
    parse_content_file,
)
from apps.content.services.asset_templates import unit_spec_for
from apps.content.tests.group_quran_data import GroupQuranDataMixin
from apps.content.unit_keys import encode_group_key
from apps.core.permissions import PermissionChoice
from apps.core.tests.base import BaseTestCase
from apps.users.models import User

AYAH_HEADER = b"from_surah,from_ayah,to_surah,to_ayah,text\n"
WORD_HEADER = b"from_surah,from_ayah,from_word,to_surah,to_ayah,to_word,text\n"


class GroupImportTests(GroupQuranDataMixin, BaseTestCase):
    def setUp(self):
        super().setUp()
        self.bake_group_quran()

    def _asset(self, template: str = AssetTemplateChoice.AYAH_GROUP) -> Asset:
        return baker.make(
            Asset, category=CategoryChoice.TAFSIR, status=StatusChoice.READY, template=template, language="ar"
        )

    def _parse(self, raw: bytes, template: str = AssetTemplateChoice.AYAH_GROUP, **kwargs) -> dict:
        asset = self._asset(template)
        parsed = parse_content_file(raw, unit_spec_for(asset), asset, **kwargs)
        return {entry.unit_id: entry.cells for entry in parsed}

    def test_parse_content_file_where_ayah_group_file_should_return_encoded_ranges(self):
        # Arrange
        raw = AYAH_HEADER + b"1,1,1,3,a\n1,1,1,1,b\n"

        # Act
        parsed = self._parse(raw)

        # Assert
        self.assertEqual(parsed, {encode_group_key(1, 3): {"text": "a"}, encode_group_key(1, 1): {"text": "b"}})

    def test_parse_content_file_where_word_group_crosses_ayah_should_resolve(self):
        # Arrange — word 3 of 1:1 to word 1 of 1:2
        raw = WORD_HEADER + b"1,1,3,1,2,1,x\n"

        # Act
        parsed = self._parse(raw, AssetTemplateChoice.WORD_GROUP)

        # Assert
        self.assertEqual(parsed, {encode_group_key(3, 4): {"text": "x"}})

    def test_parse_content_file_where_rows_out_of_order_should_accept_all(self):
        # Arrange
        raw = AYAH_HEADER + b"2,1,2,2,later\n1,1,1,2,earlier\n"

        # Act
        parsed = self._parse(raw)

        # Assert
        self.assertEqual(set(parsed), {encode_group_key(4, 5), encode_group_key(1, 2)})

    def test_parse_content_file_where_overlapping_ranges_should_accept_both(self):
        # Arrange
        raw = AYAH_HEADER + b"1,1,2,2,whole\n1,2,1,3,part\n"

        # Act
        parsed = self._parse(raw)

        # Assert
        self.assertEqual(set(parsed), {encode_group_key(1, 5), encode_group_key(2, 3)})

    def test_parse_content_file_where_range_reversed_should_raise_with_row_number(self):
        # Arrange
        raw = AYAH_HEADER + b"1,1,1,1,ok\n1,3,1,1,backwards\n"

        # Act
        with self.assertRaises(AssetContentInvalidRowsError) as raised:
            self._parse(raw)

        # Assert
        self.assertEqual(raised.exception.rows, {3: "range_reversed"})

    def test_parse_content_file_where_unknown_position_should_raise_with_row_number(self):
        # Arrange
        raw = AYAH_HEADER + b"1,1,1,9,x\n"

        # Act
        with self.assertRaises(AssetContentInvalidRowsError) as raised:
            self._parse(raw)

        # Assert
        self.assertEqual(raised.exception.rows, {2: "unknown_unit"})

    def test_parse_content_file_where_same_range_repeated_should_raise_duplicate(self):
        # Arrange — identical text still counts as a repeat
        raw = AYAH_HEADER + b"1,1,1,3,same\n1,1,1,3,same\n"

        # Act
        with self.assertRaises(AssetContentInvalidRowsError) as raised:
            self._parse(raw)

        # Assert
        self.assertEqual(raised.exception.rows, {3: "duplicate"})

    def test_parse_content_file_where_not_strict_and_group_should_still_raise(self):
        # Arrange
        raw = AYAH_HEADER + b"1,1,1,1,ok\nnot,a,number,row,x\n"

        # Act / Assert
        with self.assertRaises(AssetContentInvalidRowsError):
            self._parse(raw, strict=False)

    def test_parse_content_file_where_range_not_in_allowed_should_raise_not_in_source(self):
        # Arrange
        raw = AYAH_HEADER + b"1,1,1,3,ok\n2,1,2,2,new\n"

        # Act
        with self.assertRaises(AssetContentInvalidRowsError) as raised:
            self._parse(raw, allowed_unit_ids={encode_group_key(1, 3)})

        # Assert
        self.assertEqual(raised.exception.rows, {3: "not_in_source"})

    def test_parse_content_file_where_verbose_export_reimported_should_match_cells(self):
        # Arrange
        asset = self._asset(AssetTemplateChoice.WORD_GROUP)
        column = asset.ensure_text_columns()[0]
        version = baker.make(AssetVersion, asset=asset, state=VersionStateChoice.PUBLISHED)
        for start, end, text in ((3, 4, "x, with comma"), (1, 1, "y")):
            AssetVersionEntry.objects.create(
                version=version, column=column, text=text, order=start, from_word_id=start, to_word_id=end
            )
        spec = unit_spec_for(asset)
        exported = AssetContentRepository().entries_to_csv_bytes(version, spec, verbose=True)

        # Act
        parsed = parse_content_file(exported, spec, asset)

        # Assert
        self.assertEqual(
            {entry.unit_id: entry.cells for entry in parsed},
            {encode_group_key(3, 4): {"text": "x, with comma"}, encode_group_key(1, 1): {"text": "y"}},
        )


class GroupTranslationUploadTests(GroupQuranDataMixin, BaseTestCase):
    def setUp(self):
        super().setUp()
        self.bake_group_quran()
        self.tafsir = baker.make(
            Asset,
            category=CategoryChoice.TAFSIR,
            status=StatusChoice.READY,
            template=AssetTemplateChoice.AYAH_GROUP,
            language="ar",
            slug="group-tafsir",
        )
        source = self.tafsir.get_or_create_source_language()
        head = baker.make(
            AssetVersion, asset=self.tafsir, asset_language=source, state=VersionStateChoice.PUBLISHED, name="1.0"
        )
        AssetVersionEntry.objects.create(
            version=head,
            column=self.tafsir.ensure_text_columns()[0],
            text="src",
            order=1,
            from_ayah_id=1,
            to_ayah_id=3,
        )
        AssetLanguage.objects.create(asset=self.tafsir, language="en")
        self.user = User.objects.create_user(email="editor@example.com", name="Editor", is_staff=True)
        self.give_permission(self.user, PermissionChoice.PORTAL_EDIT_TAFSIR_CONTENT)
        self.give_permission(self.user, PermissionChoice.PORTAL_ACCESS_ALL_LANGUAGES)

    def test_create_tafsir_version_where_translation_language_uses_unknown_range_should_return_400(self):
        # Arrange
        self.authenticate_user(self.user)
        file = SimpleUploadedFile(
            "en.csv", AYAH_HEADER + b"1,1,1,3,ok\n2,1,2,2,not in source\n", content_type="text/csv"
        )

        # Act
        response = self.client.post(
            f"/portal/tafsirs/{self.tafsir.slug}/versions/",
            data={"asset_id": self.tafsir.id, "version_number": "1.0", "language": "en", "file": file},
        )

        # Assert
        self.assertEqual(response.status_code, 400, response.content)
        body = response.json()
        self.assertEqual(body["error_name"], "content_file_invalid_rows")
        self.assertEqual(body["extra"]["rows"], {"3": "not_in_source"})
