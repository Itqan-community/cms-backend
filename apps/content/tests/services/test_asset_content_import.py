from django.test import SimpleTestCase

from apps.content.services.asset_content_import import AssetContentParseError, parse_content_file

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


class ParseContentFileTest(SimpleTestCase):
    def test_parse_where_translation_format_should_map_text_and_footnotes(self):
        # Arrange / Act
        entries = parse_content_file(_TRANSLATION_CSV)

        # Assert
        self.assertEqual(2, len(entries))
        self.assertEqual((1, 1), (entries[0].sura, entries[0].aya))
        self.assertEqual("In the name of Allah", entries[0].text)
        self.assertEqual("[note]", entries[0].footnotes)

    def test_parse_where_arabic_tafsir_format_should_map_content_and_margin(self):
        # Arrange / Act
        entries = parse_content_file(_TAFSIR_CSV)

        # Assert
        self.assertEqual(1, len(entries))
        self.assertEqual((1, 1), (entries[0].sura, entries[0].aya))
        self.assertEqual("محتوى الآية", entries[0].text)
        self.assertEqual("هامش", entries[0].footnotes)

    def test_parse_where_no_header_should_raise(self):
        # Arrange
        raw = b"just,some,random\n1,2,3\n"

        # Act / Assert
        with self.assertRaises(AssetContentParseError):
            parse_content_file(raw)

    def test_parse_where_empty_file_should_raise(self):
        # Act / Assert
        with self.assertRaises(AssetContentParseError):
            parse_content_file(b"")
