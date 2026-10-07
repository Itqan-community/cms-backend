import csv
import io

from model_bakery import baker

from apps.content.models import MushafLayout
from apps.content.services.asset_content_import import parse_content_file
from apps.content.services.asset_templates import unit_spec_for
from apps.content.tests.portal.test_asset_content import AssetContentBaseTest
from apps.core.permissions import PermissionChoice


def _rows(response) -> list[list[str]]:
    return list(csv.reader(io.StringIO(response.content.decode("utf-8"))))


class DownloadCsvTemplateTest(AssetContentBaseTest):
    def test_download_csv_template_where_ayah_should_list_every_ayah_with_blank_text(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_READ_TRANSLATION)

        # Act
        response = self.client.get("/portal/content/translations/csv-template/?template=ayah")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertIn('filename="ayah-template.csv"', response["Content-Disposition"])
        rows = _rows(response)
        self.assertEqual(["surah", "ayah", "surah_name", "ayah_text", "text"], rows[0])
        self.assertEqual([["1", "1"], ["1", "2"], ["1", "3"]], [row[:2] for row in rows[1:]])
        self.assertEqual({""}, {row[4] for row in rows[1:]})

    def test_download_csv_template_where_page_without_layout_should_raise(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_READ_TAFSIR)

        # Act
        response = self.client.get("/portal/content/tafsirs/csv-template/?template=page")

        # Assert
        self.assertEqual(400, response.status_code, response.content)
        self.assertEqual("mushaf_layout_required", response.json()["error_name"])

    def test_download_csv_template_where_page_with_layout_should_list_its_pages(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_READ_TAFSIR)
        layout = baker.make(MushafLayout, name="Tiny Mushaf", page_count=3)

        # Act
        response = self.client.get(f"/portal/content/tafsirs/csv-template/?template=page&mushaf_layout_id={layout.id}")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertIn('filename="page-Tiny_Mushaf-template.csv"', response["Content-Disposition"])
        self.assertEqual([["page", "text"], ["1", ""], ["2", ""], ["3", ""]], _rows(response))

    def test_download_csv_template_where_layout_missing_should_raise(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_READ_TAFSIR)

        # Act
        response = self.client.get("/portal/content/tafsirs/csv-template/?template=page&mushaf_layout_id=999999")

        # Assert
        self.assertEqual(404, response.status_code, response.content)
        self.assertEqual("mushaf_layout_not_found", response.json()["error_name"])

    def test_download_csv_template_where_unsupported_category_should_raise(self):
        # Arrange
        self.authenticate_user(self.user)

        # Act
        response = self.client.get("/portal/content/mushafs/csv-template/?template=ayah")

        # Assert
        self.assertEqual(404, response.status_code, response.content)
        self.assertEqual("unsupported_content_category", response.json()["error_name"])

    def test_download_csv_template_where_no_read_permission_should_be_forbidden(self):
        # Arrange
        self.authenticate_user(self.user)

        # Act
        response = self.client.get("/portal/content/translations/csv-template/?template=ayah")

        # Assert
        self.assertEqual(403, response.status_code, response.content)

    def test_download_csv_template_where_filled_in_should_import(self):
        # Arrange — a user fills the downloaded sheet's text column
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_READ_TRANSLATION)
        rows = _rows(self.client.get("/portal/content/translations/csv-template/?template=ayah"))
        rows[1][4] = "first"
        rows[3][4] = "third"
        buffer = io.StringIO()
        csv.writer(buffer).writerows(rows)

        # Act
        entries = parse_content_file(buffer.getvalue().encode(), unit_spec_for(self.translation), self.translation)

        # Assert
        self.assertEqual([(1, "first"), (3, "third")], [(entry.unit_id, entry.text) for entry in entries])


class DownloadAssetCsvTemplateTest(AssetContentBaseTest):
    def test_download_asset_csv_template_where_asset_exists_should_use_its_template(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_READ_TRANSLATION)
        self.translation.name_en = "French Rashid"
        self.translation.save(update_fields=["name_en"])

        # Act
        response = self.client.get(f"/portal/content/translations/{self.translation.slug}/csv-template/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertIn('filename="French_Rashid-ayah-template.csv"', response["Content-Disposition"])
        rows = _rows(response)
        self.assertEqual(["surah", "ayah", "surah_name", "ayah_text", "text"], rows[0])
        self.assertEqual(4, len(rows))

    def test_download_asset_csv_template_where_asset_missing_should_raise(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_READ_TRANSLATION)

        # Act
        response = self.client.get("/portal/content/translations/no-such-slug/csv-template/")

        # Assert
        self.assertEqual(404, response.status_code, response.content)
        self.assertEqual("translation_not_found", response.json()["error_name"])
