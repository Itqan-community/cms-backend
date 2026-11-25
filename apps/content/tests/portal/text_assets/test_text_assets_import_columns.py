import json

from django.core.files.uploadedfile import SimpleUploadedFile

from apps.content.models import AssetLanguage, AssetVersion
from apps.content.tests.portal.text_assets.test_text_assets_versions import TextAssetVersionBaseTest
from apps.core.permissions import PermissionChoice

UNMATCHED_CSV = b"chapter,verse,meaning\n1,1,in the name\n"


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
