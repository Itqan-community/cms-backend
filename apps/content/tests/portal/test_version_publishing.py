from datetime import timedelta

from django.core import mail
from django.core.files.base import ContentFile
from django.utils import timezone
from model_bakery import baker

from apps.content.models import (
    Asset,
    AssetAccess,
    AssetAccessRequest,
    AssetLanguage,
    AssetTemplateChoice,
    AssetVersion,
    AssetVersionChange,
    AssetVersionChangeReview,
    AssetVersionEntry,
    CategoryChoice,
    ReviewStateChoice,
    StatusChoice,
    VersionStateChoice,
)
from apps.content.repositories.asset_content import AssetContentRepository
from apps.content.repositories.asset_review import AssetReviewRepository
from apps.core.permissions import PermissionChoice
from apps.core.tests.base import BaseTestCase
from apps.publishers.models import MemberLanguage, Publisher, PublisherMember
from apps.quran.models import Ayah, Sura
from apps.users.models import User


class VersionPublishingBaseTest(BaseTestCase):
    """A French translation rendition with a commit timeline v1 -> v2 -> v3."""

    def setUp(self):
        super().setUp()
        self.publisher = baker.make(Publisher, name="P")
        self.asset = baker.make(
            Asset,
            category=CategoryChoice.TRANSLATION,
            template=AssetTemplateChoice.AYAH,
            publisher=self.publisher,
            status=StatusChoice.READY,
            language="ar",
            slug="t1",
        )
        self.fr = AssetLanguage.objects.create(asset=self.asset, language="fr", status=StatusChoice.READY)
        sura = baker.make(Sura, id=1, name="الفاتحة", ayas_count=7)
        self.ayah1 = baker.make(Ayah, id=1, sura=sura, number_in_sura=1, text="a")
        self.ayah2 = baker.make(Ayah, id=2, sura=sura, number_in_sura=2, text="b")
        self.user = User.objects.create_user(email="pub@example.com", name="Pub", is_staff=True)
        self.membership = baker.make(
            PublisherMember, user=self.user, publisher=self.publisher, status=PublisherMember.StatusChoice.ACTIVE
        )
        self._clock = timezone.now() - timedelta(days=10)

    def _commit(self, name: str, changes: dict[Ayah, tuple[str, str]], *, entries: bool = True) -> AssetVersion:
        """A committed version recording ``{ayah: (change_type, new_text)}``, created after the previous one."""
        self._clock += timedelta(hours=1)
        version = baker.make(
            AssetVersion,
            asset=self.asset,
            asset_language=self.fr,
            name=name,
            state=VersionStateChoice.PUBLISHED,
            file_url=ContentFile(b"surah,ayah,text\n", name=f"{name}.csv"),
        )
        AssetVersion.objects.filter(pk=version.pk).update(created_at=self._clock)
        version.refresh_from_db()
        for ayah, (change_type, new_text) in changes.items():
            baker.make(
                AssetVersionChange,
                version=version,
                ayah=ayah,
                change_type=change_type,
                new_text=new_text,
                order=ayah.id,
            )
            if entries:
                baker.make(AssetVersionEntry, version=version, ayah=ayah, text=new_text, order=ayah.id)
        return version

    def _review(self, version: AssetVersion, ayah: Ayah, state: str = ReviewStateChoice.APPROVED) -> None:
        change = AssetVersionChange.objects.get(version=version, ayah=ayah)
        AssetVersionChangeReview.objects.create(
            change=change,
            state=state,
            comment="fix" if state == ReviewStateChoice.COMMENTED else "",
            reviewed_by=self.user,
            reviewed_at=timezone.now(),
        )

    def _publish_url(self, version: AssetVersion) -> str:
        return f"/portal/content/translations/{self.asset.slug}/versions/{version.id}/set-published/"

    def _authorize(self) -> None:
        self.give_permission(self.user, PermissionChoice.PORTAL_PUBLISH_CONTENT)
        MemberLanguage.objects.create(member=self.membership, language="fr")


class PendingUnitsByVersionTest(VersionPublishingBaseTest):
    def test_pending_units_by_version_where_all_latest_changes_approved_should_be_zero(self):
        # Arrange
        v1 = self._commit("v1", {self.ayah1: ("added", "x"), self.ayah2: ("added", "y")})
        self._review(v1, self.ayah1)
        self._review(v1, self.ayah2)

        # Act
        result = AssetReviewRepository().pending_units_by_version(self.asset, "fr")

        # Assert
        self.assertEqual({v1.id: 0}, result)

    def test_pending_units_by_version_where_unit_unreviewed_or_commented_should_count_it(self):
        # Arrange
        v1 = self._commit("v1", {self.ayah1: ("added", "x"), self.ayah2: ("added", "y")})
        self._review(v1, self.ayah1, ReviewStateChoice.COMMENTED)

        # Act
        result = AssetReviewRepository().pending_units_by_version(self.asset, "fr")

        # Assert — ayah1 commented, ayah2 unreviewed
        self.assertEqual({v1.id: 2}, result)

    def test_pending_units_by_version_where_earlier_change_unreviewed_should_count_in_later_versions(self):
        # Arrange — v1's ayah2 change is never reviewed and is still v2's content
        v1 = self._commit("v1", {self.ayah1: ("added", "x"), self.ayah2: ("added", "y")})
        v2 = self._commit("v2", {self.ayah1: ("modified", "x2")})
        self._review(v2, self.ayah1)

        # Act
        result = AssetReviewRepository().pending_units_by_version(self.asset, "fr")

        # Assert
        self.assertEqual({v1.id: 2, v2.id: 1}, result)

    def test_pending_units_by_version_where_later_change_supersedes_unreviewed_one_should_approve_later_only(self):
        # Arrange — v1's ayah1 text is superseded by v2's approved text
        v1 = self._commit("v1", {self.ayah1: ("added", "x")})
        v2 = self._commit("v2", {self.ayah1: ("modified", "x2")})
        self._review(v2, self.ayah1)

        # Act
        result = AssetReviewRepository().pending_units_by_version(self.asset, "fr")

        # Assert — v1 itself was never approved
        self.assertEqual({v1.id: 1, v2.id: 0}, result)

    def test_pending_units_by_version_where_version_has_no_changes_should_inherit_previous_state(self):
        # Arrange — v2 is an upload identical to v1 (no change rows)
        v1 = self._commit("v1", {self.ayah1: ("added", "x")})
        v2 = self._commit("v2", {})
        self._review(v1, self.ayah1)

        # Act
        result = AssetReviewRepository().pending_units_by_version(self.asset, "fr")

        # Assert
        self.assertEqual({v1.id: 0, v2.id: 0}, result)


class SetPublishedVersionApiTest(VersionPublishingBaseTest):
    def test_set_published_where_no_publish_permission_should_return_403(self):
        # Arrange
        v1 = self._commit("v1", {self.ayah1: ("added", "x")})
        self._review(v1, self.ayah1)
        MemberLanguage.objects.create(member=self.membership, language="fr")
        self.authenticate_user(self.user)

        # Act
        response = self.client.post(self._publish_url(v1))

        # Assert
        self.assertEqual(403, response.status_code, response.content)
        self.assertEqual("permission_denied", response.json()["error_name"])

    def test_set_published_where_language_not_assigned_should_return_403(self):
        # Arrange
        v1 = self._commit("v1", {self.ayah1: ("added", "x")})
        self._review(v1, self.ayah1)
        self.give_permission(self.user, PermissionChoice.PORTAL_PUBLISH_CONTENT)
        self.authenticate_user(self.user)

        # Act
        response = self.client.post(self._publish_url(v1))

        # Assert
        self.assertEqual(403, response.status_code, response.content)
        self.assertEqual("language_not_assigned", response.json()["error_name"])

    def test_set_published_where_changes_not_approved_should_return_400(self):
        # Arrange
        v1 = self._commit("v1", {self.ayah1: ("added", "x"), self.ayah2: ("added", "y")})
        self._review(v1, self.ayah1)
        self._authorize()
        self.authenticate_user(self.user)

        # Act
        response = self.client.post(self._publish_url(v1))

        # Assert
        self.assertEqual(400, response.status_code, response.content)
        self.assertEqual("version_not_approved", response.json()["error_name"])
        self.fr.refresh_from_db()
        self.assertIsNone(self.fr.published_version_id)

    def test_set_published_where_version_is_draft_should_return_400(self):
        # Arrange
        draft = baker.make(AssetVersion, asset=self.asset, asset_language=self.fr, state=VersionStateChoice.DRAFT)
        self._authorize()
        self.authenticate_user(self.user)

        # Act
        response = self.client.post(self._publish_url(draft))

        # Assert
        self.assertEqual(400, response.status_code, response.content)
        self.assertEqual("version_not_publishable", response.json()["error_name"])

    def test_set_published_where_approved_should_make_it_the_consumer_version(self):
        # Arrange
        v1 = self._commit("v1", {self.ayah1: ("added", "x")})
        self._review(v1, self.ayah1)
        self._authorize()
        self.authenticate_user(self.user)

        # Act
        response = self.client.post(self._publish_url(v1))

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual(v1.id, response.json()["id"])
        self.fr.refresh_from_db()
        self.assertEqual(v1.id, self.fr.published_version_id)
        self.assertEqual(v1, self.asset.get_published_version("fr"))

    def test_set_published_where_older_approved_version_should_roll_back_to_it(self):
        # Arrange — v2 is live; roll back to v1
        v1 = self._commit("v1", {self.ayah1: ("added", "x")})
        self._review(v1, self.ayah1)
        v2 = self._commit("v2", {self.ayah1: ("modified", "x2")})
        self._review(v2, self.ayah1)
        AssetLanguage.objects.filter(pk=self.fr.pk).update(published_version=v2)
        self._authorize()
        self.authenticate_user(self.user)

        # Act
        response = self.client.post(self._publish_url(v1))

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.fr.refresh_from_db()
        self.assertEqual(v1.id, self.fr.published_version_id)

    def test_set_published_where_version_was_pruned_should_rematerialize_its_file(self):
        # Arrange — v1 keeps its entries as the anchor; v2 was pruned to deltas (no file)
        v1 = self._commit("v1", {self.ayah1: ("added", "x")})
        self._review(v1, self.ayah1)
        v2 = self._commit("v2", {self.ayah2: ("added", "y")}, entries=False)
        self._review(v2, self.ayah2)
        v2.file_url.delete(save=True)
        self._authorize()
        self.authenticate_user(self.user)

        # Act
        response = self.client.post(self._publish_url(v2))

        # Assert — consumers download the file, so it is rebuilt from v1 + v2's delta
        self.assertEqual(200, response.status_code, response.content)
        v2.refresh_from_db()
        self.assertTrue(v2.file_url)
        with v2.file_url.open("rb") as handle:
            content = handle.read().decode("utf-8")
        self.assertIn("1,1,x", content)
        self.assertIn("1,2,y", content)

    def test_set_published_where_previous_version_was_published_should_notify_subscribers(self):
        # Arrange
        v1 = self._commit("v1", {self.ayah1: ("added", "x")})
        self._review(v1, self.ayah1)
        v2 = self._commit("v2", {self.ayah1: ("modified", "x2")})
        self._review(v2, self.ayah1)
        AssetLanguage.objects.filter(pk=self.fr.pk).update(published_version=v1)
        subscriber = baker.make(User, email="subscriber@example.com")
        access_request = baker.make(AssetAccessRequest, developer_user=subscriber, asset=self.asset, status="approved")
        baker.make(
            AssetAccess, asset_access_request=access_request, user=subscriber, asset=self.asset, effective_license="CC0"
        )
        self._authorize()
        self.authenticate_user(self.user)

        # Act
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(self._publish_url(v2))

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        recipients = [email for message in mail.outbox for email in message.to]
        self.assertIn("subscriber@example.com", recipients)


class VersionListApprovalFieldsTest(VersionPublishingBaseTest):
    def test_list_versions_should_expose_published_and_approval_state(self):
        # Arrange — v1 approved and published, v2 pending review
        v1 = self._commit("v1", {self.ayah1: ("added", "x")})
        self._review(v1, self.ayah1)
        v2 = self._commit("v2", {self.ayah2: ("added", "y")})
        AssetLanguage.objects.filter(pk=self.fr.pk).update(published_version=v1)
        self.give_permission(self.user, PermissionChoice.PORTAL_READ_TRANSLATION)
        MemberLanguage.objects.create(member=self.membership, language="fr")
        self.authenticate_user(self.user)

        # Act
        response = self.client.get(f"/portal/translations/{self.asset.slug}/versions/?language=fr")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        rows = {row["id"]: row for row in response.json()["results"]}
        self.assertEqual(
            (True, True, 0, False),
            tuple(rows[v1.id][k] for k in ("is_published", "is_approved", "pending_review_count", "is_active")),
        )
        self.assertEqual(
            (False, False, 1, True),
            tuple(rows[v2.id][k] for k in ("is_published", "is_approved", "pending_review_count", "is_active")),
        )
        self.assertTrue(rows[v1.id]["is_first"])
        self.assertFalse(rows[v2.id]["is_first"])


class CommitDoesNotPrunePublishedVersionTest(VersionPublishingBaseTest):
    def test_publish_draft_where_previous_head_is_published_should_keep_its_file(self):
        # Arrange — v1 is the published head; a new commit supersedes it
        v1 = self._commit("v1", {self.ayah1: ("added", "x")})
        AssetLanguage.objects.filter(pk=self.fr.pk).update(published_version=v1)
        draft = baker.make(
            AssetVersion, asset=self.asset, asset_language=self.fr, name="v2", state=VersionStateChoice.DRAFT
        )
        baker.make(AssetVersionEntry, version=draft, ayah=self.ayah1, text="x2", order=1)

        # Act
        AssetContentRepository().publish_draft(draft)

        # Assert — consumers still download v1, so neither its file nor entries are dropped
        v1.refresh_from_db()
        self.assertTrue(v1.file_url)
        self.assertTrue(v1.entries.exists())
        self.assertEqual(v1, self.asset.get_published_version("fr"))
