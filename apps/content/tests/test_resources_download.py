import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from model_bakery import baker

from apps.content.models import Resource, ResourceVersion, UsageEvent
from apps.core.tests import BaseTestCase
from apps.users.models import User


class DownloadResourceTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.user = baker.make(User, email="test@example.com", is_active=True)

    def create_file(self, name: str, content: bytes, content_type: str) -> SimpleUploadedFile:
        return SimpleUploadedFile(name, content, content_type=content_type)

    def test_download_returns_latest_version_file_with_correct_headers_csv(self):
        # Arrange
        self.authenticate_user(self.user)
        with (
            tempfile.TemporaryDirectory() as tmpdir,
            override_settings(MEDIA_ROOT=tmpdir),
        ):
            resource = baker.make(Resource, name="Dataset A")

            file_obj = self.create_file("data.csv", b"a,b\n1,2\n", "text/csv")
            baker.make(
                ResourceVersion,
                resource=resource,
                semvar="1.0.0",
                storage_url=file_obj,
                file_type=ResourceVersion.FileTypeChoice.CSV,
                is_latest=True,
            )

            # Act
            response = self.client.get(f"/resources/{resource.id}/download/", format="json")
            body = response.json()

            # Assert
            self.assertEqual(200, response.status_code)
            self.assertIn("download_url", body)
            self.assertIn("/data.csv", body["download_url"])

    def test_download_fallbacks_to_most_recent_when_no_latest_marked(self):
        # Arrange
        self.authenticate_user(self.user)
        with (
            tempfile.TemporaryDirectory() as tmpdir,
            override_settings(MEDIA_ROOT=tmpdir),
        ):
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
            baker.make(
                ResourceVersion,
                resource=resource,
                semvar="1.1.0",
                storage_url=newer_file,
                file_type=ResourceVersion.FileTypeChoice.JSON,
                is_latest=False,
                created_at="2025-01-01T00:00:00Z",
            )

            # Act
            response = self.client.get(f"/resources/{resource.id}/download/", format="json")
            body = response.json()

            # Assert
            self.assertEqual(200, response.status_code)
            self.assertIn("download_url", body)
            self.assertIn("/new.json", body["download_url"])

    def test_download_returns_404_when_no_versions_exist(self):
        # Arrange
        self.authenticate_user(self.user)
        resource = baker.make(Resource)

        # Act
        response = self.client.get(f"/resources/{resource.id}/download/", format="json")

        # Assert
        self.assertEqual(404, response.status_code)

    def test_download_returns_404_when_resource_not_found(self):
        # Arrange - Use a non-existent integer ID
        self.authenticate_user(self.user)
        non_existent_id = 99999

        # Act
        response = self.client.get(f"/resources/{non_existent_id}/download/", format="json")

        # Assert
        self.assertEqual(404, response.status_code)

    def test_download_returns_404_when_version_has_no_storage_url_value(self):
        # Arrange
        self.authenticate_user(self.user)
        with (
            tempfile.TemporaryDirectory() as tmpdir,
            override_settings(MEDIA_ROOT=tmpdir),
        ):
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
            response = self.client.get(f"/resources/{resource.id}/download/", format="json")

            # Assert
            self.assertEqual(404, response.status_code)

    def test_download_resource_should_create_usage_event_for_authenticated_user(self):
        # Arrange
        self.authenticate_user(self.user)
        with (
            tempfile.TemporaryDirectory() as tmpdir,
            override_settings(MEDIA_ROOT=tmpdir),
        ):
            resource = baker.make(Resource, name="Usage Event Test Resource")
            file_obj = self.create_file("test.csv", b"test,data\n1,2\n", "text/csv")
            baker.make(
                ResourceVersion,
                resource=resource,
                semvar="1.0.0",
                storage_url=file_obj,
                file_type=ResourceVersion.FileTypeChoice.CSV,
                is_latest=True,
            )

            # Act
            response = self.client.get(f"/resources/{resource.id}/download/", format="json")
            body = response.json()

            # Assert
            self.assertEqual(200, response.status_code)
            self.assertIn("download_url", body)
            self.assertIn("/test.csv", body["download_url"])

            # Verify usage event was created in database
            usage_events = UsageEvent.objects.filter(
                developer_user=self.user,
                usage_kind=UsageEvent.UsageKindChoice.FILE_DOWNLOAD,
                subject_kind=UsageEvent.SubjectKindChoice.RESOURCE,
                resource_id=resource.id,
            )
            self.assertEqual(1, usage_events.count())

            usage_event = usage_events.first()
            self.assertEqual(usage_event.developer_user, self.user)
            self.assertEqual(usage_event.usage_kind, UsageEvent.UsageKindChoice.FILE_DOWNLOAD)
            self.assertEqual(usage_event.subject_kind, UsageEvent.SubjectKindChoice.RESOURCE)
            self.assertEqual(usage_event.resource_id, resource.id)
            self.assertIsNone(usage_event.asset_id)
            self.assertEqual(usage_event.effective_license, "CC0")
            self.assertIsInstance(usage_event.metadata, dict)

    def test_download_resource_should_include_request_metadata_in_usage_event(self):
        # Arrange
        self.authenticate_user(self.user)
        with (
            tempfile.TemporaryDirectory() as tmpdir,
            override_settings(MEDIA_ROOT=tmpdir),
        ):
            resource = baker.make(Resource, name="Metadata Test Resource")
            file_obj = self.create_file("metadata.json", b'{"test": "data"}', "application/json")
            baker.make(
                ResourceVersion,
                resource=resource,
                semvar="2.0.0",
                storage_url=file_obj,
                file_type=ResourceVersion.FileTypeChoice.JSON,
                is_latest=True,
            )

            # Act - Include custom headers
            response = self.client.get(
                f"/resources/{resource.id}/download/",
                format="json",
                headers={
                    "user-agent": "Resource Download Agent/3.0",
                    "x-forwarded-for": "192.168.1.300",
                },
            )
            body = response.json()

            # Assert
            self.assertEqual(200, response.status_code)
            self.assertIn("download_url", body)
            self.assertIn("/metadata.json", body["download_url"])

            # Verify usage event was created with correct metadata
            usage_events = UsageEvent.objects.filter(
                developer_user=self.user,
                usage_kind=UsageEvent.UsageKindChoice.FILE_DOWNLOAD,
                subject_kind=UsageEvent.SubjectKindChoice.RESOURCE,
                resource_id=resource.id,
            )
            self.assertEqual(1, usage_events.count())

            usage_event = usage_events.first()
            self.assertEqual(usage_event.user_agent, "Resource Download Agent/3.0")
            # Note: IP address capture depends on Django test client configuration
            # In real requests, this would capture the client IP
