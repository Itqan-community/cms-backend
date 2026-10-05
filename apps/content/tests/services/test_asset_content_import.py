from model_bakery import baker

from apps.content.models import Asset, AssetTemplateChoice, CategoryChoice
from apps.content.services.asset_content_import import (
    DUPLICATE,
    UNKNOWN_UNIT,
    UNREADABLE,
    AssetContentInvalidRowsError,
    AssetContentParseError,
    parse_content_file,
)
from apps.content.services.asset_templates import unit_spec_for
from apps.content.tests.quran_data import QuranDataMixin
from apps.core.tests.base import BaseTestCase

_TRANSLATION_CSV = (
    b'"Translation Info:\n# preamble line",,,,\n'
    b"id,sura,aya,translation,footnotes\n"
    b'1,1,1,"In the name of Allah","[note]"\n'
    b'2,1,2,"All praise",""\n'
)

_TAFSIR_CSV = (
    "﻿المشروع,نوع المشروع,السورة,رقم السورة,رقم الآية,الآية,"
    "مرحلة العمل,قابل للنشر,المستخدم,المحتوى,الهامش\n"
    "تفسير,آية,الفاتحة,1,1,بسم,مرحلة,نعم,مستخدم,محتوى الآية,هامش\n"
).encode()


class ParseContentFileTest(QuranDataMixin, BaseTestCase):
    """Covers the two real QuranEnc export shapes for the ayah template.

    Ayah ids come from ``QuranDataMixin.bake_quran``: sura 1 has ayah 1 (id 1)
    and ayah 2 (id 2).
    """

    def setUp(self):
        super().setUp()
        self.bake_quran()
        self.asset = baker.make(Asset, category=CategoryChoice.TRANSLATION, template=AssetTemplateChoice.AYAH)
        self.spec = unit_spec_for(self.asset)

    def test_parse_where_translation_format_should_map_text(self):
        # Arrange / Act (the trailing footnotes column is ignored)
        entries = parse_content_file(_TRANSLATION_CSV, self.spec, self.asset)

        # Assert
        self.assertEqual(2, len(entries))
        self.assertEqual(self.ayah1.id, entries[0].unit_id)
        self.assertEqual("In the name of Allah", entries[0].text)
        self.assertEqual(self.ayah2.id, entries[1].unit_id)

    def test_parse_where_arabic_tafsir_format_should_map_content(self):
        # Arrange / Act (the trailing margin column is ignored)
        entries = parse_content_file(_TAFSIR_CSV, self.spec, self.asset)

        # Assert
        self.assertEqual(1, len(entries))
        self.assertEqual(self.ayah1.id, entries[0].unit_id)
        self.assertEqual("محتوى الآية", entries[0].text)

    def test_parse_where_no_header_should_raise(self):
        # Arrange
        raw = b"just,some,random\n1,2,3\n"

        # Act / Assert
        with self.assertRaises(AssetContentParseError):
            parse_content_file(raw, self.spec, self.asset)

    def test_parse_where_empty_file_should_raise(self):
        # Act / Assert
        with self.assertRaises(AssetContentParseError):
            parse_content_file(b"", self.spec, self.asset)


class StrictParseTest(QuranDataMixin, BaseTestCase):
    """Strict parsing (uploads) names every row whose text a lenient parse drops."""

    def setUp(self):
        super().setUp()
        self.bake_quran()
        self.asset = baker.make(Asset, category=CategoryChoice.TRANSLATION, template=AssetTemplateChoice.AYAH)
        self.spec = unit_spec_for(self.asset)

    def _parse_strict(self, content: bytes) -> list:
        return parse_content_file(content, self.spec, self.asset, strict=True)

    def test_parse_strict_where_every_row_is_usable_should_parse(self):
        # Arrange / Act — the real QuranEnc export, preamble and extra column included
        entries = self._parse_strict(_TRANSLATION_CSV)

        # Assert
        self.assertEqual([self.ayah1.id, self.ayah2.id], [entry.unit_id for entry in entries])

    def test_parse_strict_where_rows_would_be_dropped_should_name_each_row(self):
        # Arrange — row 3: same ayah, different text; row 4: sura not a number;
        # row 5: an ayah that does not exist
        content = b"sura,aya,text\n1,1,first\n1,1,second\nx,2,unreadable\n1,99,missing\n"

        # Act
        with self.assertRaises(AssetContentInvalidRowsError) as ctx:
            self._parse_strict(content)

        # Assert
        self.assertEqual({3: DUPLICATE, 4: UNREADABLE, 5: UNKNOWN_UNIT}, ctx.exception.rows)

    def test_parse_strict_where_rows_hide_no_text_should_accept_them(self):
        # Arrange — an identical duplicate, a blank row for a missing ayah, a blank line
        content = b"sura,aya,text\n1,1,same\n1,1,same\n1,99,\n\n1,2,second\n"

        # Act
        entries = self._parse_strict(content)

        # Assert
        self.assertEqual(["same", "second"], [entry.text for entry in entries])

    def test_parse_where_not_strict_should_keep_skipping_bad_rows(self):
        # Arrange — internal reads (e.g. rebuilding legacy versions) stay lenient
        content = b"sura,aya,text\n1,1,first\n1,1,second\n1,99,missing\n"

        # Act
        entries = parse_content_file(content, self.spec, self.asset)

        # Assert — the last duplicate wins, the missing ayah is skipped
        self.assertEqual([(self.ayah1.id, "second")], [(entry.unit_id, entry.text) for entry in entries])
