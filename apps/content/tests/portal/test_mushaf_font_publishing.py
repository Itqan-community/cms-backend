"""Mushafs and fonts serve an explicitly published version, like translations
and tafsirs: uploads can be staged, and publishers roll back with a reason."""

from datetime import timedelta
import importlib

from django.apps import apps as django_apps
from django.core.cache import cache
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from model_bakery import baker

from apps.content.models import (
    Asset,
    AssetLanguage,
    AssetVersion,
    CategoryChoice,
    StatusChoice,
    VersionStateChoice,
    consumer_visible_q,
)
from apps.content.tests.publishing import publish
from apps.core.permissions import PermissionChoice
from apps.core.tests.base import BaseTestCase
from apps.package_manager.services.package_registry import PackageRegistryService, PackageVersionStatus
from apps.publishers.models import Publisher
from apps.users.models import User

# The module name starts with a digit, so a plain `from ... import` is illegal.
migration = importlib.import_module("apps.content.migrations.0007_publish_newest_mushaf_and_font_versions")


class MushafPublishingBaseTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        cache.clear()  # the public package API is throttled per client
        self.publisher = baker.make(Publisher, name="P")
        self.mushaf = baker.make(
            Asset,
            category=CategoryChoice.MUSHAF,
            publisher=self.publisher,
            status=StatusChoice.READY,
            is_open_access=True,
            language="ar",
            slug="m1",
            name="M1",
        )
        self.user = User.objects.create_user(email="pub@example.com", name="Pub", is_staff=True)
        self._clock = timezone.now() - timedelta(days=10)

    def _commit(self, name: str, *, asset: Asset | None = None) -> AssetVersion:
        """A committed version with a file, created after the previous one."""
        self._clock += timedelta(hours=1)
        version = baker.make(
            AssetVersion,
            asset=asset or self.mushaf,
            name=name,
            state=VersionStateChoice.PUBLISHED,
            file_url=ContentFile(b"pdf", name=f"{name}.pdf"),
        )
        AssetVersion.objects.filter(pk=version.pk).update(created_at=self._clock)
        version.refresh_from_db()
        return version

    def _upload(self, *, publish_now: bool):
        file = SimpleUploadedFile("mushaf.pdf", b"content", content_type="application/pdf")
        return self.client.post(
            "/portal/mushafs/m1/versions/",
            data={"asset_id": self.mushaf.id, "summary_en": "New", "file": file, "publish": publish_now},
        )

    def _publish_url(self, version: AssetVersion, kind: str = "mushafs", slug: str = "m1") -> str:
        return f"/portal/{kind}/{slug}/versions/{version.pk}/set-published/"

    def _authorize(self, *permissions: PermissionChoice) -> None:
        for permission in permissions:
            self.give_permission(self.user, permission)
        self.authenticate_user(self.user)


class PublishNewestMushafAndFontVersionsMigrationTests(MushafPublishingBaseTest):
    def test_publish_newest_versions_where_mushaf_has_versions_should_publish_the_newest(self):
        # Arrange
        self._commit("1.0")
        newest = self._commit("1.1")

        # Act
        migration.publish_newest_versions(django_apps, None)

        # Assert
        self.assertEqual(newest, self.mushaf.get_published_version())
        newest.refresh_from_db()
        self.assertEqual(newest.created_at, newest.first_published_at)

    def test_publish_newest_versions_where_language_already_published_should_keep_it(self):
        # Arrange
        older = publish(self._commit("1.0"))
        self._commit("1.1")

        # Act
        migration.publish_newest_versions(django_apps, None)

        # Assert
        self.assertEqual(older, self.mushaf.get_published_version())

    def test_publish_newest_versions_where_tafsir_should_leave_it_alone(self):
        # Arrange
        tafsir = baker.make(Asset, category=CategoryChoice.TAFSIR, template="ayah", status=StatusChoice.READY)
        self._commit("1.0", asset=tafsir)

        # Act
        migration.publish_newest_versions(django_apps, None)

        # Assert
        self.assertIsNone(tafsir.get_published_version())


class MushafConsumerVisibilityTests(MushafPublishingBaseTest):
    def test_get_published_version_where_newer_version_not_published_should_serve_published(self):
        # Arrange
        published = publish(self._commit("1.0"))
        self._commit("1.1")

        # Act
        served = self.mushaf.get_published_version()

        # Assert
        self.assertEqual(published, served)

    def test_consumer_visible_q_where_mushaf_has_no_published_version_should_hide_it(self):
        # Arrange
        self._commit("1.0")

        # Act
        visible = Asset.objects.filter(consumer_visible_q(), pk=self.mushaf.pk).exists()

        # Assert
        self.assertFalse(visible)

    def test_version_statuses_where_newer_mushaf_version_not_published_should_not_release_it(self):
        # Arrange
        publish(self._commit("1.0"))
        staged = self._commit("1.1")
        rendition = AssetLanguage.objects.get(asset=self.mushaf, is_source=True)

        # Act
        statuses = {s.version.pk: s.status for s in PackageRegistryService().version_statuses(self.mushaf, rendition)}

        # Assert
        self.assertEqual(PackageVersionStatus.NOT_RELEASED, statuses[staged.pk])


class MushafUploadPublishTests(MushafPublishingBaseTest):
    def test_create_mushaf_version_where_publish_requested_should_publish_it(self):
        # Arrange
        publish(self._commit("1.0"))
        self._authorize(PermissionChoice.PORTAL_CREATE_MUSHAF, PermissionChoice.PORTAL_PUBLISH_CONTENT)

        # Act
        response = self._upload(publish_now=True)

        # Assert
        self.assertEqual(201, response.status_code, response.content)
        self.assertTrue(response.json()["is_published"])
        self.assertEqual(response.json()["id"], self.mushaf.get_published_version().pk)

    def test_create_mushaf_version_where_publish_not_requested_should_stage_it(self):
        # Arrange
        published = publish(self._commit("1.0"))
        self._authorize(PermissionChoice.PORTAL_CREATE_MUSHAF)

        # Act
        response = self._upload(publish_now=False)

        # Assert
        self.assertEqual(201, response.status_code, response.content)
        self.assertFalse(response.json()["is_published"])
        self.assertEqual("not_released", response.json()["package_status"])
        self.assertEqual(published, self.mushaf.get_published_version())

    def test_create_mushaf_version_where_publish_requested_without_permission_should_return_403(self):
        # Arrange
        publish(self._commit("1.0"))
        self._authorize(PermissionChoice.PORTAL_CREATE_MUSHAF)

        # Act
        response = self._upload(publish_now=True)

        # Assert
        self.assertEqual(403, response.status_code, response.content)
        self.assertEqual("permission_denied", response.json()["error_name"])
        self.assertEqual(1, AssetVersion.objects.filter(asset=self.mushaf).count())

    def test_create_mushaf_where_file_given_should_publish_first_version(self):
        # Arrange
        self._authorize(PermissionChoice.PORTAL_CREATE_MUSHAF)
        file = SimpleUploadedFile("mushaf.pdf", b"mushaf_bytes", content_type="application/pdf")

        # Act
        response = self.client.post(
            "/portal/mushafs/",
            data={
                "name_en": "Mushaf With Version",
                "license": "CC-BY",
                "language": "ar",
                "publisher_id": self.publisher.id,
                "is_external": False,
                "version_number": "1.0",
                "version_label_ar": "الطبعة الأولى",
                "file": file,
            },
        )

        # Assert
        self.assertEqual(201, response.status_code, response.content)
        asset = Asset.objects.get(pk=response.json()["id"])
        self.assertEqual(AssetVersion.objects.get(asset=asset), asset.get_published_version())


class MushafSetPublishedTests(MushafPublishingBaseTest):
    def test_set_published_mushaf_version_where_newer_version_should_publish_it(self):
        # Arrange
        publish(self._commit("1.0"))
        staged = self._commit("1.1")
        self._authorize(PermissionChoice.PORTAL_PUBLISH_CONTENT)

        # Act
        response = self.client.post(self._publish_url(staged))

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual(staged, self.mushaf.get_published_version())

    def test_set_published_mushaf_version_where_rolling_back_without_reason_should_return_400(self):
        # Arrange
        older = publish(self._commit("1.0"))
        publish(self._commit("1.1"))
        self._authorize(PermissionChoice.PORTAL_PUBLISH_CONTENT)

        # Act
        response = self.client.post(self._publish_url(older))

        # Assert
        self.assertEqual(400, response.status_code, response.content)
        self.assertEqual("rollback_reason_required", response.json()["error_name"])

    def test_set_published_mushaf_version_where_rolling_back_should_serve_older_and_withdraw_newer(self):
        # Arrange
        older = publish(self._commit("1.0"))
        newer = publish(self._commit("1.1"))
        self._authorize(PermissionChoice.PORTAL_PUBLISH_CONTENT)

        # Act
        response = self.client.post(
            self._publish_url(older), data={"reason": "Wrong page order"}, content_type="application/json"
        )

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual(older, self.mushaf.get_published_version())
        resolved = self.client.get("/packages/resolve/m1/?version=1.1.0").json()["result"]
        self.assertTrue(resolved["withdrawn"])
        self.assertEqual("Wrong page order", resolved["withdrawal_reason"])
        self.assertEqual(
            "1.0.0", self.client.get("/packages/resolve/m1/?version=^1.0").json()["result"]["resolved_version"]
        )
        newer.refresh_from_db()
        self.assertEqual("Wrong page order", newer.withdrawal_reason)

    def test_set_published_mushaf_version_where_no_publish_permission_should_return_403(self):
        # Arrange
        staged = self._commit("1.0")
        self._authorize(PermissionChoice.PORTAL_UPDATE_MUSHAF)

        # Act
        response = self.client.post(self._publish_url(staged))

        # Assert
        self.assertEqual(403, response.status_code, response.content)
        self.assertEqual("permission_denied", response.json()["error_name"])

    def test_set_published_font_version_where_newer_version_should_publish_it(self):
        # Arrange
        font = baker.make(
            Asset, category=CategoryChoice.FONT, publisher=self.publisher, status=StatusChoice.READY, slug="f1"
        )
        publish(self._commit("1.0", asset=font))
        staged = self._commit("1.1", asset=font)
        self._authorize(PermissionChoice.PORTAL_PUBLISH_CONTENT)

        # Act
        response = self.client.post(self._publish_url(staged, kind="fonts", slug="f1"))

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual(staged, font.get_published_version())


class PublishedMushafVersionGuardTests(MushafPublishingBaseTest):
    def test_delete_mushaf_version_where_published_should_return_400(self):
        # Arrange
        published = publish(self._commit("1.0"))
        self._authorize(PermissionChoice.PORTAL_DELETE_MUSHAF)

        # Act
        response = self.client.delete(f"/portal/mushafs/m1/versions/{published.pk}/")

        # Assert
        self.assertEqual(400, response.status_code, response.content)
        self.assertEqual("version_is_published", response.json()["error_name"])

    def test_update_mushaf_version_where_published_and_file_replaced_should_return_400(self):
        # Arrange
        published = publish(self._commit("1.0"))
        self._authorize(PermissionChoice.PORTAL_UPDATE_MUSHAF)
        file = SimpleUploadedFile("other.pdf", b"other", content_type="application/pdf")

        # Act
        response = self.client.patch(
            f"/portal/mushafs/m1/versions/{published.pk}/", data={"file": file}, format="multipart"
        )

        # Assert
        self.assertEqual(400, response.status_code, response.content)
        self.assertEqual("version_is_published", response.json()["error_name"])

    def test_list_mushaf_versions_should_flag_published_and_rollback(self):
        # Arrange
        older = self._commit("1.0")
        published = publish(self._commit("1.1"))
        staged = self._commit("1.2")
        self._authorize(PermissionChoice.PORTAL_READ_MUSHAF)

        # Act
        response = self.client.get("/portal/mushafs/m1/versions/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        rows = {row["id"]: (row["is_published"], row["publishing_rolls_back"]) for row in response.json()["results"]}
        self.assertEqual({older.pk: (False, True), published.pk: (True, False), staged.pk: (False, False)}, rows)
