import json

from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test.utils import CaptureQueriesContext
from model_bakery import baker

from apps.content.models import AssetColumn, AssetLanguage, AssetVersion
from apps.content.services.asset_content_import import PREVIEW_BYTES
from apps.content.tests.portal.text_assets.test_text_assets_versions import TextAssetVersionBaseTest
from apps.core.permissions import PermissionChoice

UNMATCHED_CSV = b"chapter,verse,meaning\n1,1,in the name\n"


class ImportColumnsPreviewApiTest(TextAssetVersionBaseTest):
    def _url(self, slug: str | None = None) -> str:
        return f"/portal/text-assets/{slug or self.text_asset.slug}/import-columns/"

    def test_preview_import_columns_where_headers_unmatched_should_return_fields_and_partial_mapping(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_READ_TEXT_ASSET)
        baker.make(AssetColumn, asset=self.text_asset, key="meaning_text", label_en="Meaning", order=0)
        file = SimpleUploadedFile("t.csv", b"surah,verse,meaning\n1,1,x\n", content_type="text/csv")

        # Act
        response = self.client.post(self._url(), data={"file": file})

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual(["surah", "verse", "meaning"], body["headers"])
        self.assertEqual(1, body["header_row"])
        self.assertEqual([["1", "1", "x"]], body["samples"])
        self.assertEqual(
            [
                {"key": "surah", "kind": "unit", "label_en": "", "label_ar": ""},
                {"key": "ayah", "kind": "unit", "label_en": "", "label_ar": ""},
                {"key": "meaning_text", "kind": "text", "label_en": "Meaning", "label_ar": ""},
            ],
            body["fields"],
        )
        self.assertEqual([["surah", "ayah", "meaning_text"]], body["required"])
        self.assertEqual({"surah": 0}, body["mapping"])
        self.assertFalse(body["complete"])

    def test_preview_import_columns_where_file_is_large_should_read_only_its_start(self):
        # Arrange — ~6 MB: the preview must not parse past the first PREVIEW_BYTES
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_READ_TEXT_ASSET)
        body_rows = b"".join(b"1,%d,%s\n" % (i, b"x" * 200) for i in range(30_000))
        file = SimpleUploadedFile("big.csv", b"surah,ayah,text\n" + body_rows, content_type="text/csv")
        self.assertGreater(file.size, 90 * PREVIEW_BYTES)

        # Act
        with CaptureQueriesContext(connection) as queries:
            response = self.client.post(self._url(), data={"file": file})

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertTrue(body["complete"])
        self.assertEqual(3, len(body["samples"]))
        self.assertLessEqual(len(queries), 8)

    def test_preview_import_columns_where_file_empty_should_return_content_file_unparseable(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_READ_TEXT_ASSET)
        file = SimpleUploadedFile("t.csv", b"", content_type="text/csv")

        # Act
        response = self.client.post(self._url(), data={"file": file})

        # Assert
        self.assertEqual(400, response.status_code, response.content)
        self.assertEqual("content_file_unparseable", response.json()["error_name"])

    def test_preview_import_columns_where_title_above_header_should_say_the_header_must_be_first(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_READ_TEXT_ASSET)
        file = SimpleUploadedFile("t.csv", b"My export\nchapter,verse,meaning\n1,1,x\n", content_type="text/csv")

        # Act
        response = self.client.post(self._url(), data={"file": file})

        # Assert
        self.assertEqual(400, response.status_code, response.content)
        body = response.json()
        self.assertEqual("content_file_unparseable", body["error_name"])
        self.assertIn("first row must be its header row", body["message"])

    def test_create_version_where_mapped_file_has_title_above_header_should_say_the_header_must_be_first(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_EDIT_TEXT_ASSET_CONTENT)

        # Act
        response = self.client.post(
            f"/portal/text-assets/{self.text_asset.slug}/versions/",
            data={
                "asset_id": self.text_asset.id,
                "version_number": "1.0",
                "summary_en": "first",
                "file": SimpleUploadedFile("t.csv", b"My export\nchapter,verse,meaning\n1,1,x\n"),
                "column_mapping": json.dumps({"surah": 0, "ayah": 1, "text": 2}),
            },
        )

        # Assert
        self.assertEqual(400, response.status_code, response.content)
        body = response.json()
        self.assertEqual("content_file_unparseable", body["error_name"])
        self.assertIn("first row must be its header row", body["message"])

    def test_preview_import_columns_where_slug_unknown_should_return_text_asset_not_found(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_READ_TEXT_ASSET)
        file = SimpleUploadedFile("t.csv", UNMATCHED_CSV, content_type="text/csv")

        # Act
        response = self.client.post(self._url("missing"), data={"file": file})

        # Assert
        self.assertEqual(404, response.status_code, response.content)
        self.assertEqual("text_asset_not_found", response.json()["error_name"])

    def test_preview_import_columns_where_user_lacks_permission_should_return_403(self):
        # Arrange
        self.authenticate_user(self.user)
        file = SimpleUploadedFile("t.csv", UNMATCHED_CSV, content_type="text/csv")

        # Act
        response = self.client.post(self._url(), data={"file": file})

        # Assert
        self.assertEqual(403, response.status_code, response.content)


class ImportWithColumnMappingApiTest(TextAssetVersionBaseTest):
    def _create(self, mapping: object, content: bytes = UNMATCHED_CSV):
        return self.client.post(
            f"/portal/text-assets/{self.text_asset.slug}/versions/",
            data={
                "asset_id": self.text_asset.id,
                "version_number": "1.0",
                "summary_en": "first",
                "file": SimpleUploadedFile("t.csv", content, content_type="text/csv"),
                **({"column_mapping": mapping if isinstance(mapping, str) else json.dumps(mapping)} if mapping else {}),
            },
        )

    def test_create_version_where_column_mapping_given_should_import_mapped_columns(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_EDIT_TEXT_ASSET_CONTENT)

        # Act
        response = self._create({"surah": 0, "ayah": 1, "text": 2})

        # Assert
        self.assertEqual(201, response.status_code, response.content)
        version = AssetVersion.objects.get(id=response.json()["id"])
        self.assertEqual(["in the name"], [entry.text for entry in version.entries.all()])

    def test_create_version_where_no_mapping_and_headers_unmatched_should_still_reject(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_EDIT_TEXT_ASSET_CONTENT)

        # Act
        response = self._create(None)

        # Assert
        self.assertEqual(400, response.status_code, response.content)
        self.assertEqual("content_file_unparseable", response.json()["error_name"])

    def test_create_version_where_mapping_incomplete_should_return_column_mapping_incomplete(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_EDIT_TEXT_ASSET_CONTENT)

        # Act
        response = self._create({"surah": 0, "ayah": 1})

        # Assert
        self.assertEqual(400, response.status_code, response.content)
        body = response.json()
        self.assertEqual("column_mapping_incomplete", body["error_name"])
        self.assertEqual(["text"], body["extra"]["fields"])
        self.assertFalse(AssetVersion.objects.filter(asset=self.text_asset).exists())

    def test_create_version_where_mapping_not_json_object_should_return_column_mapping_invalid(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_EDIT_TEXT_ASSET_CONTENT)

        # Act
        bad_json = self._create("{not json")
        bad_value = self._create({"surah": "0"})

        # Assert
        self.assertEqual(400, bad_json.status_code, bad_json.content)
        self.assertEqual("column_mapping_invalid", bad_json.json()["error_name"])
        self.assertEqual(400, bad_value.status_code, bad_value.content)
        self.assertEqual("column_mapping_invalid", bad_value.json()["error_name"])

    def test_create_version_where_mapping_reuses_column_should_return_column_mapping_invalid(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_EDIT_TEXT_ASSET_CONTENT)

        # Act
        response = self._create({"surah": 0, "ayah": 0, "text": 2})

        # Assert
        self.assertEqual(400, response.status_code, response.content)
        self.assertEqual("column_mapping_invalid", response.json()["error_name"])

    def test_update_version_where_file_replaced_with_mapping_should_import_mapped_columns(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_EDIT_TEXT_ASSET_CONTENT)
        self.give_permission(self.user, PermissionChoice.PORTAL_UPDATE_TEXT_ASSET)
        created = self._create({"surah": 0, "ayah": 1, "text": 2}).json()

        # Act
        response = self.client.patch(
            f"/portal/text-assets/{self.text_asset.slug}/versions/{created['id']}/",
            data={
                "file": SimpleUploadedFile("t.csv", b"x,meaning,verse,chapter\n,new text,1,1\n"),
                "column_mapping": json.dumps({"surah": 3, "ayah": 2, "text": 1}),
            },
        )

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        version = AssetVersion.objects.get(id=created["id"])
        self.assertEqual(["new text"], [entry.text for entry in version.entries.all()])

    def test_add_language_where_column_mapping_given_should_seed_mapped_columns(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_READ_TEXT_ASSET)
        self.give_permission(self.user, PermissionChoice.PORTAL_ADD_ASSET_LANGUAGE)

        # Act
        response = self.client.post(
            f"/portal/content/text-assets/{self.text_asset.slug}/languages/",
            data={
                "language": "es",
                "version_number": "1.0",
                "file": SimpleUploadedFile("es.csv", b"chapter,verse,meaning\n1,1,en el nombre\n"),
                "column_mapping": json.dumps({"surah": 0, "ayah": 1, "text": 2}),
            },
        )

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        version = AssetVersion.objects.get(asset_language__language="es", asset=self.text_asset)
        self.assertEqual(["en el nombre"], [entry.text for entry in version.entries.all()])
        self.assertTrue(AssetLanguage.objects.filter(asset=self.text_asset, language="es").exists())


class NewAssetImportColumnsPreviewApiTest(TextAssetVersionBaseTest):
    url = "/portal/content/text-assets/import-columns/"

    def test_preview_new_asset_import_columns_where_columns_given_should_return_their_fields(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_CREATE_TEXT_ASSET)
        columns = [{"key": "question", "label_en": "Question", "label_ar": "السؤال"}, {"key": "answer"}]
        file = SimpleUploadedFile("t.csv", b"sura,aya,question,reply\n1,1,q,a\n", content_type="text/csv")

        # Act
        response = self.client.post(self.url, data={"template": "ayah", "columns": json.dumps(columns), "file": file})

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual(
            [
                {"key": "surah", "kind": "unit", "label_en": "", "label_ar": ""},
                {"key": "ayah", "kind": "unit", "label_en": "", "label_ar": ""},
                {"key": "question", "kind": "text", "label_en": "Question", "label_ar": "السؤال"},
                {"key": "answer", "kind": "text", "label_en": "", "label_ar": ""},
            ],
            body["fields"],
        )
        self.assertEqual({"surah": 0, "ayah": 1, "question": 2}, body["mapping"])
        self.assertFalse(body["complete"])

    def test_preview_new_asset_import_columns_where_no_columns_should_use_the_text_column(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_CREATE_TEXT_ASSET)
        file = SimpleUploadedFile("t.csv", b"page,translation\n1,x\n", content_type="text/csv")

        # Act
        response = self.client.post(self.url, data={"template": "page", "file": file})

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual([["page", "text"]], body["required"])
        self.assertTrue(body["complete"])

    def test_preview_new_asset_import_columns_where_column_key_invalid_should_return_column_key_invalid(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_CREATE_TEXT_ASSET)
        file = SimpleUploadedFile("t.csv", UNMATCHED_CSV, content_type="text/csv")

        # Act
        response = self.client.post(
            self.url, data={"template": "ayah", "columns": json.dumps([{"key": "Surah"}]), "file": file}
        )

        # Assert
        self.assertEqual(400, response.status_code, response.content)
        self.assertEqual("column_key_invalid", response.json()["error_name"])

    def test_preview_new_asset_import_columns_where_user_cannot_create_should_return_403(self):
        # Arrange
        self.authenticate_user(self.user)
        file = SimpleUploadedFile("t.csv", UNMATCHED_CSV, content_type="text/csv")

        # Act
        response = self.client.post(self.url, data={"template": "ayah", "file": file})

        # Assert
        self.assertEqual(403, response.status_code, response.content)
