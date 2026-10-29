"""Withdrawn and removed versions in the package registry, and the portal
actions that cause them.

Withdrawn: the publisher rolled back past it (with a reason); ranges skip it, an
exact (lockfile) pin still installs it with a warning. Removed: an Itqan admin
removed it; never installed or served again.
"""

from datetime import timedelta

from django.core.cache import cache
from django.core.files.base import ContentFile
from django.utils import timezone
from model_bakery import baker

from apps.content.models import (
    Asset,
    AssetLanguage,
    AssetTemplateChoice,
    AssetVersion,
    AssetVersionChange,
    AssetVersionChangeReview,
    CategoryChoice,
    ReviewStateChoice,
    StatusChoice,
    VersionStateChoice,
)
from apps.content.tests.publishing import publish
from apps.core.permissions import PermissionChoice
from apps.core.tests.base import BaseTestCase
from apps.publishers.models import MemberLanguage, Publisher, PublisherMember
from apps.quran.models import Ayah, Surah
from apps.users.models import User


class WithdrawalBaseTest(BaseTestCase):
    """A French translation rendition (timeline built per test) and a mushaf."""

    def setUp(self):
        super().setUp()
        cache.clear()  # the public package API is throttled per client
        self.publisher = baker.make(Publisher, name="P")
        self.asset = baker.make(
            Asset,
            category=CategoryChoice.TRANSLATION,
            template=AssetTemplateChoice.AYAH,
            publisher=self.publisher,
            status=StatusChoice.READY,
            is_open_access=True,
            language="ar",
            slug="t1",
            name="T1",
        )
        self.fr = AssetLanguage.objects.create(asset=self.asset, language="fr", status=StatusChoice.READY)
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
        surah = baker.make(Surah, id=1, name="الفاتحة", ayahs_count=7)
        self.ayah1 = baker.make(Ayah, id=1, surah=surah, number_in_surah=1, text="a")
        self.user = User.objects.create_user(email="pub@example.com", name="Pub")
        self.membership = baker.make(
            PublisherMember, user=self.user, publisher=self.publisher, status=PublisherMember.StatusChoice.ACTIVE
        )
        self._clock = timezone.now() - timedelta(days=10)

    def _commit(self, name: str, *, asset: Asset | None = None) -> AssetVersion:
        """A committed version created after the previous one. Translation
        versions change ayah 1 and are approved; mushaf versions carry a file and
        are published, as an upload with "publish now" is."""
        asset = asset or self.asset
        self._clock += timedelta(hours=1)
        version = baker.make(
            AssetVersion,
            asset=asset,
            asset_language=self.fr if asset == self.asset else asset.get_or_create_source_language(),
            name=name,
            state=VersionStateChoice.PUBLISHED,
            file_url=ContentFile(b"surah,ayah,text\n", name=f"{name}.csv"),
        )
        AssetVersion.objects.filter(pk=version.pk).update(created_at=self._clock)
        version.refresh_from_db()
        if asset == self.asset:
            change = baker.make(
                AssetVersionChange, version=version, ayah=self.ayah1, change_type="modified", new_text=name, order=1
            )
            AssetVersionChangeReview.objects.create(
                change=change, state=ReviewStateChoice.APPROVED, reviewed_by=self.user, reviewed_at=timezone.now()
            )
        else:
            publish(version)
        return version

    def _roll_back(self, version: AssetVersion, reason: str = "Errors in the newer version"):
        """Publish ``version`` through the portal, as a publisher rolling back does."""
        self._authorize_publisher()
        return self.client.post(
            f"/portal/content/translations/t1/versions/{version.pk}/set-published/",
            data={"reason": reason},
            content_type="application/json",
        )

    def _remove(self, version: AssetVersion, reason: str = "") -> None:
        AssetVersion.objects.filter(pk=version.pk).update(removed_at=timezone.now(), removal_reason=reason)

    def _resolve(self, slug: str, version: str, language: str | None = None):
        query = f"?version={version}" + (f"&language={language}" if language else "")
        return self.client.get(f"/packages/resolve/{slug}/{query}")

    def _authorize_publisher(self) -> None:
        self.give_permission(self.user, PermissionChoice.PORTAL_PUBLISH_CONTENT)
        self.give_permission(self.user, PermissionChoice.PORTAL_READ_TRANSLATION)
        MemberLanguage.objects.get_or_create(member=self.membership, language="fr")
        self.authenticate_user(self.user)


class RollbackTests(WithdrawalBaseTest):
    def test_set_published_version_where_rolling_back_should_record_reason_on_rolled_back_versions(self):
        # Arrange
        v1 = publish(self._commit("1.0"))
        v2 = publish(self._commit("1.1"))
        v3 = publish(self._commit("1.2"))

        # Act
        response = self._roll_back(v1, reason="Errors in Surah 2")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        for version in (v1, v2, v3):
            version.refresh_from_db()
        self.assertEqual("", v1.withdrawal_reason)
        self.assertEqual("Errors in Surah 2", v2.withdrawal_reason)
        self.assertEqual("Errors in Surah 2", v3.withdrawal_reason)

    def test_set_published_version_where_rolled_back_twice_should_keep_each_versions_reason(self):
        # Arrange
        v1 = publish(self._commit("1.0"))
        v2 = publish(self._commit("1.1"))
        v3 = publish(self._commit("1.2"))
        self._roll_back(v2, reason="First reason")

        # Act
        self._roll_back(v1, reason="Second reason")

        # Assert
        v2.refresh_from_db()
        v3.refresh_from_db()
        self.assertEqual("Second reason", v2.withdrawal_reason)
        self.assertEqual("First reason", v3.withdrawal_reason)

    def test_set_published_version_where_rolled_back_version_published_again_should_clear_its_reason(self):
        # Arrange
        v1 = publish(self._commit("1.0"))
        v2 = publish(self._commit("1.1"))
        self._roll_back(v1)

        # Act
        response = self.client.post(f"/portal/content/translations/t1/versions/{v2.pk}/set-published/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        v2.refresh_from_db()
        self.assertEqual("", v2.withdrawal_reason)

    def test_set_published_version_where_publishing_a_newer_version_should_not_need_a_reason(self):
        # Arrange
        publish(self._commit("1.0"))
        v2 = self._commit("1.1")
        self._authorize_publisher()

        # Act
        response = self.client.post(f"/portal/content/translations/t1/versions/{v2.pk}/set-published/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)

    def test_resolve_package_single_where_publisher_rolled_back_should_resolve_rolled_back_version(self):
        # Arrange
        v1 = publish(self._commit("1.0"))
        publish(self._commit("1.1"))
        self._roll_back(v1)

        # Act
        response = self._resolve("t1", "^1.0", "fr")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual("1.0.0", response.json()["result"]["resolved_version"])
        self.assertFalse(response.json()["result"]["withdrawn"])

    def test_resolve_package_single_where_pinned_to_rolled_back_version_should_return_it_with_reason(self):
        # Arrange
        v1 = publish(self._commit("1.0"))
        publish(self._commit("1.1"))
        self._roll_back(v1, reason="Errors in Surah 2")

        # Act
        response = self._resolve("t1", "1.1.0", "fr")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        result = response.json()["result"]
        self.assertEqual("1.1.0", result["resolved_version"])
        self.assertTrue(result["withdrawn"])
        self.assertEqual("Errors in Surah 2", result["withdrawal_reason"])

    def test_resolve_package_single_where_pinned_to_never_published_commit_should_return_404(self):
        # Arrange
        publish(self._commit("1.0"))
        self._commit("1.1")

        # Act
        response = self._resolve("t1", "1.1.0", "fr")

        # Assert
        self.assertEqual(404, response.status_code, response.content)
        self.assertEqual("version_not_found", response.json()["error_name"])

    def test_resolve_package_manifest_where_pinned_to_rolled_back_version_should_flag_it(self):
        # Arrange
        v1 = publish(self._commit("1.0"))
        publish(self._commit("1.1"))
        self._roll_back(v1)

        # Act
        response = self.client.post(
            "/packages/resolve/manifest/",
            data={"assets": {"t1-fr": {"asset": "t1", "language": "fr", "version": "1.1.0"}}},
            content_type="application/json",
        )

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual([True], [r["withdrawn"] for r in response.json()["results"]])

    def test_download_package_file_where_version_rolled_back_should_redirect(self):
        # Arrange
        v1 = publish(self._commit("1.0"))
        v2 = publish(self._commit("1.1"))
        self._roll_back(v1)

        # Act
        response = self.client.get(f"/packages/download/{v2.pk}/t1-fr-1.1.csv/")

        # Assert
        self.assertEqual(302, response.status_code, response.content)

    def test_list_translation_versions_where_rolled_back_should_report_each_package_status(self):
        # Arrange
        v1 = publish(self._commit("1.0"))
        v2 = publish(self._commit("1.1"))
        v3 = self._commit("1.2")
        self._roll_back(v1, reason="Errors in Surah 2")

        # Act
        response = self.client.get("/portal/translations/t1/versions/?language=fr")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        rows = {row["id"]: row for row in response.json()["results"]}
        self.assertEqual("released", rows[v1.pk]["package_status"])
        self.assertEqual("withdrawn", rows[v2.pk]["package_status"])
        self.assertEqual("Errors in Surah 2", rows[v2.pk]["withdrawal_reason"])
        self.assertEqual("not_released", rows[v3.pk]["package_status"])

    def test_list_translation_versions_where_version_older_than_published_should_flag_rollback(self):
        # Arrange
        v1 = self._commit("1.0")
        v2 = publish(self._commit("1.1"))
        v3 = self._commit("1.2")
        self._authorize_publisher()

        # Act
        response = self.client.get("/portal/translations/t1/versions/?language=fr")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        rows = {row["id"]: row["publishing_rolls_back"] for row in response.json()["results"]}
        self.assertEqual({v1.pk: True, v2.pk: False, v3.pk: False}, rows)

    def test_list_mushaf_versions_where_version_removed_should_report_removed(self):
        # Arrange
        removed = self._commit("1.0", asset=self.mushaf)
        self._remove(removed, reason="Licence revoked")
        newest = self._commit("1.1", asset=self.mushaf)
        self.give_permission(self.user, PermissionChoice.PORTAL_READ_MUSHAF)
        self.authenticate_user(self.user)

        # Act
        response = self.client.get("/portal/mushafs/m1/versions/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        rows = {row["id"]: row for row in response.json()["results"]}
        self.assertEqual("removed", rows[removed.pk]["package_status"])
        self.assertEqual("Licence revoked", rows[removed.pk]["removal_reason"])
        self.assertEqual("released", rows[newest.pk]["package_status"])

    def test_resolve_package_single_where_pinned_to_removed_version_should_return_410(self):
        # Arrange
        self._remove(self._commit("1.0", asset=self.mushaf), reason="Licence revoked.")
        self._commit("1.1", asset=self.mushaf)

        # Act
        response = self._resolve("m1", "1.0.0")

        # Assert
        self.assertEqual(410, response.status_code, response.content)
        self.assertEqual("version_removed", response.json()["error_name"])
        self.assertIn("Licence revoked.", response.json()["message"])

    def test_download_package_file_where_version_removed_should_return_404(self):
        # Arrange
        removed = self._commit("1.0", asset=self.mushaf)
        self._remove(removed)
        self._commit("1.1", asset=self.mushaf)

        # Act
        response = self.client.get(f"/packages/download/{removed.pk}/m1-ar-1.0.csv/")

        # Assert
        self.assertEqual(404, response.status_code, response.content)
        self.assertEqual("version_not_found", response.json()["error_name"])


class RemovedVersionServingTests(WithdrawalBaseTest):
    def test_set_published_version_where_version_removed_should_return_400(self):
        # Arrange
        publish(self._commit("1.0"))
        removed = self._commit("1.1")
        self._remove(removed)
        self._authorize_publisher()

        # Act
        response = self.client.post(f"/portal/content/translations/t1/versions/{removed.pk}/set-published/")

        # Assert
        self.assertEqual(400, response.status_code, response.content)
        self.assertEqual("version_removed", response.json()["error_name"])

    def test_set_published_version_where_first_published_should_record_first_published_at(self):
        # Arrange
        version = self._commit("1.0")
        self._authorize_publisher()

        # Act
        response = self.client.post(f"/portal/content/translations/t1/versions/{version.pk}/set-published/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        version.refresh_from_db()
        self.assertIsNotNone(version.first_published_at)


class PortalRemovePackageVersionTests(WithdrawalBaseTest):
    def setUp(self):
        super().setUp()
        self.admin = User.objects.create_user(email="admin@itqan.dev", name="Admin", is_staff=True)

    def _remove_url(self, version: AssetVersion) -> str:
        return f"/portal/packages/versions/{version.pk}/remove/"

    def test_remove_package_version_where_admin_and_version_not_served_should_remove_it(self):
        # Arrange
        old = self._commit("1.0", asset=self.mushaf)
        self._commit("1.1", asset=self.mushaf)
        self.give_permission(self.admin, PermissionChoice.PORTAL_REMOVE_PACKAGE_VERSION)
        self.authenticate_user(self.admin)

        # Act
        response = self.client.post(
            self._remove_url(old), data={"reason": "Licence revoked"}, content_type="application/json"
        )

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual("removed", response.json()["package_status"])
        old.refresh_from_db()
        self.assertEqual(self.admin, old.removed_by)
        self.assertEqual("Licence revoked", old.removal_reason)

    def test_remove_package_version_where_version_is_served_should_return_400(self):
        # Arrange
        served = publish(self._commit("1.0"))
        self.give_permission(self.admin, PermissionChoice.PORTAL_REMOVE_PACKAGE_VERSION)
        self.authenticate_user(self.admin)

        # Act
        response = self.client.post(self._remove_url(served), data={"reason": "x"}, content_type="application/json")

        # Assert
        self.assertEqual(400, response.status_code, response.content)
        self.assertEqual("version_is_served", response.json()["error_name"])

    def test_remove_package_version_where_already_removed_should_return_400(self):
        # Arrange
        old = self._commit("1.0", asset=self.mushaf)
        self._commit("1.1", asset=self.mushaf)
        self._remove(old)
        self.give_permission(self.admin, PermissionChoice.PORTAL_REMOVE_PACKAGE_VERSION)
        self.authenticate_user(self.admin)

        # Act
        response = self.client.post(self._remove_url(old), data={"reason": "x"}, content_type="application/json")

        # Assert
        self.assertEqual(400, response.status_code, response.content)
        self.assertEqual("version_already_removed", response.json()["error_name"])

    def test_remove_package_version_where_publisher_without_permission_should_return_403(self):
        # Arrange
        old = self._commit("1.0", asset=self.mushaf)
        self._commit("1.1", asset=self.mushaf)
        self.give_permission(self.user, PermissionChoice.PORTAL_UPDATE_MUSHAF)
        self.give_permission(self.user, PermissionChoice.PORTAL_PUBLISH_CONTENT)
        self.authenticate_user(self.user)

        # Act
        response = self.client.post(self._remove_url(old), data={"reason": "x"}, content_type="application/json")

        # Assert
        self.assertEqual(403, response.status_code, response.content)
        self.assertEqual("permission_denied", response.json()["error_name"])

    def test_remove_package_version_where_reason_missing_should_return_400(self):
        # Arrange
        old = self._commit("1.0", asset=self.mushaf)
        self._commit("1.1", asset=self.mushaf)
        self.give_permission(self.admin, PermissionChoice.PORTAL_REMOVE_PACKAGE_VERSION)
        self.authenticate_user(self.admin)

        # Act
        response = self.client.post(self._remove_url(old), data={"reason": ""}, content_type="application/json")

        # Assert
        self.assertEqual(400, response.status_code, response.content)
        self.assertEqual("validation_error", response.json()["error_name"])


class PortalReinstatePackageVersionTests(WithdrawalBaseTest):
    def setUp(self):
        super().setUp()
        self.admin = User.objects.create_user(email="admin@itqan.dev", name="Admin", is_staff=True)

    def _reinstate(self, version: AssetVersion, reason: str = "Licence confirmed"):
        return self.client.post(
            f"/portal/packages/versions/{version.pk}/reinstate/",
            data={"reason": reason},
            content_type="application/json",
        )

    def _authorize_admin(self) -> None:
        self.give_permission(self.admin, PermissionChoice.PORTAL_REMOVE_PACKAGE_VERSION)
        self.authenticate_user(self.admin)

    def test_reinstate_package_version_where_admin_and_version_removed_should_clear_removal(self):
        # Arrange
        old = self._commit("1.0", asset=self.mushaf)
        self._commit("1.1", asset=self.mushaf)
        self._remove(old, reason="Licence revoked")
        self._authorize_admin()

        # Act
        response = self._reinstate(old)

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual("released", response.json()["package_status"])
        old.refresh_from_db()
        self.assertIsNone(old.removed_at)
        self.assertIsNone(old.removed_by)
        self.assertEqual("", old.removal_reason)

    def test_reinstate_package_version_where_admin_gives_reason_should_record_it_in_history(self):
        # Arrange
        old = self._commit("1.0", asset=self.mushaf)
        self._commit("1.1", asset=self.mushaf)
        self._remove(old, reason="Licence revoked")
        self._authorize_admin()

        # Act
        self._reinstate(old, reason="Licence confirmed")

        # Assert
        latest = old.history.order_by("-history_date").first()
        self.assertEqual("Licence confirmed", latest.history_change_reason)
        self.assertEqual(self.admin.pk, latest.history_user_id)

    def test_reinstate_package_version_where_publisher_rolled_back_past_it_should_be_withdrawn(self):
        # Arrange
        v1 = publish(self._commit("1.0"))
        v2 = self._commit("1.1")
        publish(v2)
        self.assertEqual(200, self._roll_back(v1, reason="Errors in 1.1").status_code)
        self._remove(v2, reason="Wrong content")
        self._authorize_admin()

        # Act
        response = self._reinstate(v2)

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual("withdrawn", response.json()["package_status"])
        resolved = self._resolve("t1", "1.1.0", language="fr")
        self.assertEqual(200, resolved.status_code, resolved.content)
        self.assertEqual("Errors in 1.1", resolved.json()["result"]["withdrawal_reason"])

    def test_resolve_package_single_where_pinned_version_reinstated_should_resolve_it(self):
        # Arrange
        old = self._commit("1.0", asset=self.mushaf)
        self._commit("1.1", asset=self.mushaf)
        self._remove(old, reason="Licence revoked")
        self._authorize_admin()
        self._reinstate(old)

        # Act
        response = self._resolve("m1", "1.0.0")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual("1.0.0", response.json()["result"]["resolved_version"])

    def test_reinstate_package_version_where_version_not_removed_should_return_400(self):
        # Arrange
        old = self._commit("1.0", asset=self.mushaf)
        self._authorize_admin()

        # Act
        response = self._reinstate(old)

        # Assert
        self.assertEqual(400, response.status_code, response.content)
        self.assertEqual("version_not_removed", response.json()["error_name"])

    def test_reinstate_package_version_where_publisher_without_permission_should_return_403(self):
        # Arrange
        old = self._commit("1.0", asset=self.mushaf)
        self._commit("1.1", asset=self.mushaf)
        self._remove(old)
        self.give_permission(self.user, PermissionChoice.PORTAL_UPDATE_MUSHAF)
        self.give_permission(self.user, PermissionChoice.PORTAL_PUBLISH_CONTENT)
        self.authenticate_user(self.user)

        # Act
        response = self._reinstate(old)

        # Assert
        self.assertEqual(403, response.status_code, response.content)
        self.assertEqual("permission_denied", response.json()["error_name"])

    def test_reinstate_package_version_where_reason_missing_should_return_400(self):
        # Arrange
        old = self._commit("1.0", asset=self.mushaf)
        self._commit("1.1", asset=self.mushaf)
        self._remove(old)
        self._authorize_admin()

        # Act
        response = self._reinstate(old, reason="")

        # Assert
        self.assertEqual(400, response.status_code, response.content)
        self.assertEqual("validation_error", response.json()["error_name"])

    def test_reinstate_package_version_where_version_has_no_language_should_be_released_again(self):
        # Arrange
        old = self._commit("1.0", asset=self.mushaf)
        self._commit("1.1", asset=self.mushaf)
        AssetVersion.objects.filter(pk=old.pk).update(asset_language=None)
        self._remove(old)
        self._authorize_admin()

        # Act
        response = self._reinstate(old)

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual("released", response.json()["package_status"])
        old.refresh_from_db()
        self.assertEqual(self.mushaf.get_or_create_source_language(), old.asset_language)
