from model_bakery import baker

from apps.content.models import Asset, AssetTemplateChoice, CategoryChoice
from apps.content.services.asset_content_import import AssetContentParseError, parse_content_file
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
