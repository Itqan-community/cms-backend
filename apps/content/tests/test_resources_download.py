import tempfile
from pathlib import Path

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from model_bakery import baker

from apps.content.models import Resource
from apps.content.models import ResourceVersion
from apps.core.tests import BaseTestCase


class DownloadResourceTest(BaseTestCase):
    def create_file(self, name: str, content: bytes, content_type: str) -> SimpleUploadedFile:
        return SimpleUploadedFile(name, content, content_type=content_type)

    def test_download_returns_latest_version_file_with_correct_headers_csv(self):
        # Arrange
        with tempfile.TemporaryDirectory() as tmpdir:
            with override_settings(MEDIA_ROOT=tmpdir):
                resource = baker.make(Resource, name="Dataset A")

                file_obj = self.create_file("data.csv", b"a,b\n1,2\n", "text/csv")
                version = baker.make(
                    ResourceVersion,
                    resource=resource,
                    semvar="1.0.0",
                    storage_url=file_obj,
                    file_type=ResourceVersion.FileTypeChoice.CSV,
                    is_latest=True,
                )

                # Act
                response = self.client.get(f"/content/resources/{resource.id}/download/", format="json")

                # Assert
                self.assertEqual(200, response.status_code, getattr(response, "content", b""))
                content_disposition = response["Content-Disposition"]
                self.assertIn(f"{resource.name}_v{version.semvar}.csv", content_disposition)
                self.assertEqual("text/csv", response.get("Content-Type"))

    def test_download_fallbacks_to_most_recent_when_no_latest_marked(self):
        # Arrange
        with tempfile.TemporaryDirectory() as tmpdir:
            with override_settings(MEDIA_ROOT=tmpdir):
                resource = baker.make(Resource, name="Dataset B")

                older_file = self.create_file("old.json", b'{"a":1}', "application/json")
                newer_file = self.create_file("new.json", b'{"a":2}', "application/json")

                baker.make(
                    ResourceVersion,
                    resource=resource,
                    semvar="0.9.0",
                    storage_url=older_file,
                    file_type=ResourceVersion.FileTypeChoice.JSON,
                    is_latest=False,
                    created_at="2024-01-01T00:00:00Z",
                )
                newer = baker.make(
                    ResourceVersion,
                    resource=resource,
                    semvar="1.1.0",
                    storage_url=newer_file,
                    file_type=ResourceVersion.FileTypeChoice.JSON,
                    is_latest=False,
                    created_at="2025-01-01T00:00:00Z",
                )

                # Act
                response = self.client.get(f"/content/resources/{resource.id}/download/", format="json")

                # Assert
                self.assertEqual(200, response.status_code, getattr(response, "content", b""))
                content_disposition = response["Content-Disposition"]
                self.assertIn(f"{resource.name}_v{newer.semvar}.json", content_disposition)
                self.assertEqual("application/json", response.get("Content-Type"))

    def test_download_returns_404_when_no_versions_exist(self):
        # Arrange
        resource = baker.make(Resource)

        # Act
        response = self.client.get(f"/content/resources/{resource.id}/download/", format="json")

        # Assert
        self.assertEqual(404, response.status_code, getattr(response, "content", b""))

    def test_download_returns_404_when_file_missing_on_disk(self):
        # Arrange
        with tempfile.TemporaryDirectory() as tmpdir:
            with override_settings(MEDIA_ROOT=tmpdir):
                resource = baker.make(Resource, name="Dataset C")
                file_obj = self.create_file("archive.zip", b"PK\x03\x04...", "application/zip")
                version = baker.make(
                    ResourceVersion,
                    resource=resource,
                    semvar="2.0.0",
                    storage_url=file_obj,
                    file_type=ResourceVersion.FileTypeChoice.ZIP,
                    is_latest=True,
                )

                # Remove the stored file to simulate missing file on disk
                file_path = Path(version.storage_url.path)
                if file_path.exists():
                    file_path.unlink()

                # Act
                response = self.client.get(f"/content/resources/{resource.id}/download/", format="json")

                # Assert
                self.assertEqual(404, response.status_code, getattr(response, "content", b""))

    def test_download_returns_404_when_resource_not_found(self):
        # Arrange - Use a non-existent integer ID
        non_existent_id = 99999

        # Act
        response = self.client.get(f"/content/resources/{non_existent_id}/download/", format="json")

        # Assert
        self.assertEqual(404, response.status_code, getattr(response, "content", b""))

    def test_download_returns_404_when_resource_is_inactive(self):
        # Arrange
        resource = baker.make(Resource, is_active=False)

        # Act
        response = self.client.get(f"/content/resources/{resource.id}/download/", format="json")

        # Assert
        self.assertEqual(404, response.status_code, getattr(response, "content", b""))

    def test_download_returns_404_when_only_inactive_versions_exist(self):
        # Arrange
        with tempfile.TemporaryDirectory() as tmpdir:
            with override_settings(MEDIA_ROOT=tmpdir):
                resource = baker.make(Resource, name="Dataset D")
                file_obj = self.create_file("data.csv", b"x,y\n3,4\n", "text/csv")
                # Create only inactive versions (is_active=False) which default manager will not return
                baker.make(
                    ResourceVersion,
                    resource=resource,
                    semvar="0.1.0",
                    storage_url=file_obj,
                    file_type=ResourceVersion.FileTypeChoice.CSV,
                    is_latest=True,
                    is_active=False,
                )

                # Act
                response = self.client.get(f"/content/resources/{resource.id}/download/", format="json")

                # Assert
                self.assertEqual(404, response.status_code, getattr(response, "content", b""))

    def test_download_returns_404_when_version_has_no_storage_url_value(self):
        # Arrange
        with tempfile.TemporaryDirectory() as tmpdir:
            with override_settings(MEDIA_ROOT=tmpdir):
                resource = baker.make(Resource, name="Dataset E")
                file_obj = self.create_file("d.csv", b"a,b\n1,2\n", "text/csv")
                version = baker.make(
                    ResourceVersion,
                    resource=resource,
                    semvar="3.0.0",
                    storage_url=file_obj,
                    file_type=ResourceVersion.FileTypeChoice.CSV,
                    is_latest=True,
                )

                # Force empty storage path to simulate corrupted data
                version.storage_url.name = ""
                version.save(update_fields=["storage_url"])

                # Act
                response = self.client.get(f"/content/resources/{resource.id}/download/", format="json")

                # Assert
                self.assertEqual(404, response.status_code, getattr(response, "content", b""))
