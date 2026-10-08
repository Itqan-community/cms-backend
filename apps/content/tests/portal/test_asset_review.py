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
)
from apps.core.permissions import PermissionChoice
from apps.core.tests.base import BaseTestCase
from apps.publishers.models import MemberLanguage, Publisher, PublisherMember
from apps.quran.models import Ayah, Sura
from apps.users.models import User


class AssetReviewApiBaseTest(BaseTestCase):
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
        self.fr = AssetLanguage.objects.create(asset=self.asset, language="fr")
        self.version = baker.make(AssetVersion, asset=self.asset, asset_language=self.fr, name="v1")
        self.sura = baker.make(Sura, id=1, name="الفاتحة", ayas_count=3)
        self.ayah = baker.make(Ayah, id=1, sura=self.sura, number_in_sura=1, text="a")
        self.change = baker.make(
            AssetVersionChange, version=self.version, ayah=self.ayah, change_type="added", new_text="au nom", order=1
        )
        self.user = User.objects.create_user(email="rev@example.com", name="Rev", is_staff=True)
        self.membership = baker.make(
            PublisherMember,
            user=self.user,
            publisher=self.publisher,
            status=PublisherMember.StatusChoice.ACTIVE,
        )

    def _changes_url(self, query=""):
        return f"/portal/content/translations/{self.asset.slug}/review/changes/{query}"


class ReviewPermissionTest(AssetReviewApiBaseTest):
    def test_list_changes_where_no_review_permission_should_return_403(self):
        # Arrange — assigned the language but lacking the review permission
        self.authenticate_user(self.user)
        MemberLanguage.objects.create(member=self.membership, language="fr")

        # Act
        response = self.client.get(self._changes_url("?language=fr"))

        # Assert
        self.assertEqual(403, response.status_code, response.content)


class ReviewAssignmentTest(AssetReviewApiBaseTest):
    def test_list_changes_where_language_not_assigned_should_return_403(self):
        # Arrange — assigned 'es', not 'fr'
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_REVIEW_CONTENT)
        MemberLanguage.objects.create(member=self.membership, language="es")

        # Act
        response = self.client.get(self._changes_url("?language=fr"))

        # Assert
        self.assertEqual(403, response.status_code, response.content)
        self.assertEqual("language_not_assigned", response.json()["error_name"])

    def test_list_languages_should_return_only_assigned(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_REVIEW_CONTENT)
        MemberLanguage.objects.create(member=self.membership, language="fr")

        # Act
        response = self.client.get(f"/portal/content/translations/{self.asset.slug}/review/languages/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual(["fr"], response.json())


class ReviewActionTest(AssetReviewApiBaseTest):
    def _auth_reviewer(self):
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_REVIEW_CONTENT)
        MemberLanguage.objects.create(member=self.membership, language="fr")

    def _patch_url(self, change_id):
        return f"/portal/content/translations/{self.asset.slug}/review/changes/{change_id}/"

    def test_approve_change_where_assigned_should_set_state_and_auditing(self):
        # Arrange
        self._auth_reviewer()

        # Act
        response = self.client.patch(
            self._patch_url(self.change.id), data={"state": "approved"}, content_type="application/json"
        )

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual("approved", body["review_state"])
        self.assertEqual("Rev", body["reviewed_by"])
        self.assertTrue(AssetVersionChangeReview.objects.filter(change=self.change, state="approved").exists())

    def test_comment_change_where_no_text_should_return_400(self):
        # Arrange
        self._auth_reviewer()

        # Act
        response = self.client.patch(
            self._patch_url(self.change.id),
            data={"state": "commented", "comment": "  "},
            content_type="application/json",
        )

        # Assert
        self.assertEqual(400, response.status_code, response.content)
        self.assertEqual("review_comment_required", response.json()["error_name"])

    def test_unreviewed_where_row_exists_should_clear_it(self):
        # Arrange
        self._auth_reviewer()
        AssetVersionChangeReview.objects.create(
            change=self.change, state=ReviewStateChoice.APPROVED, reviewed_by=self.user, reviewed_at=timezone.now()
        )

        # Act
        response = self.client.patch(
            self._patch_url(self.change.id), data={"state": "unreviewed"}, content_type="application/json"
        )

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual("unreviewed", response.json()["review_state"])
        self.assertFalse(AssetVersionChangeReview.objects.filter(change=self.change).exists())

    def test_list_changes_where_assigned_should_return_change_fields(self):
        # Arrange
        self._auth_reviewer()

        # Act
        response = self.client.get(self._changes_url("?language=fr"))

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        row = response.json()["results"][0]
        self.assertEqual(self.change.id, row["id"])
        self.assertEqual("ayah", row["unit_type"])
        self.assertEqual(1, row["unit_id"])
        self.assertEqual("1:1", row["label"])
        self.assertEqual("added", row["change_type"])
        self.assertEqual("unreviewed", row["review_state"])
        self.assertIn("baseline_text", row)

    def test_list_changes_should_name_the_editor_who_made_the_change(self):
        # Arrange
        self._auth_reviewer()
        editor = User.objects.create_user(email="editor@example.com", name="Editor Name", is_staff=True)
        AssetVersion.objects.filter(pk=self.version.pk).update(created_by=editor)

        # Act
        response = self.client.get(self._changes_url("?language=fr"))

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual("Editor Name", response.json()["results"][0]["edited_by"])

    def test_list_changes_where_version_has_no_author_should_return_null_editor(self):
        # Arrange
        self._auth_reviewer()

        # Act
        response = self.client.get(self._changes_url("?language=fr"))

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertIsNone(response.json()["results"][0]["edited_by"])


class ReviewVersionFilterTest(AssetReviewApiBaseTest):
    def _auth_reviewer(self):
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_REVIEW_CONTENT)
        MemberLanguage.objects.create(member=self.membership, language="fr")

    def test_list_review_versions_should_return_the_languages_committed_versions_newest_first(self):
        # Arrange
        self._auth_reviewer()
        v2 = baker.make(AssetVersion, asset=self.asset, asset_language=self.fr, name="v2")
        AssetVersion.objects.filter(pk=v2.pk).update(created_at=timezone.now() + timezone.timedelta(hours=1))

        # Act
        response = self.client.get(f"/portal/content/translations/{self.asset.slug}/review/versions/?language=fr")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual(["v2", "v1"], [row["name"] for row in response.json()])

    def test_list_review_versions_where_language_not_assigned_should_return_403(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_REVIEW_CONTENT)

        # Act
        response = self.client.get(f"/portal/content/translations/{self.asset.slug}/review/versions/?language=fr")

        # Assert
        self.assertEqual(403, response.status_code, response.content)
        self.assertEqual("language_not_assigned", response.json()["error_name"])

    def test_list_changes_where_version_unknown_should_return_404(self):
        # Arrange
        self._auth_reviewer()

        # Act
        response = self.client.get(self._changes_url("?language=fr&version=999999"))

        # Assert
        self.assertEqual(404, response.status_code, response.content)
        self.assertEqual("version_not_found", response.json()["error_name"])

    def test_list_changes_where_version_given_should_return_the_changes_that_make_it_up(self):
        # Arrange
        self._auth_reviewer()

        # Act
        response = self.client.get(self._changes_url(f"?language=fr&version={self.version.id}"))

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual([self.change.id], [row["id"] for row in response.json()["results"]])


class ReviewBulkApproveTest(AssetReviewApiBaseTest):
    def setUp(self):
        super().setUp()
        self.ayah2 = baker.make(Ayah, id=2, sura=self.sura, number_in_sura=2, text="b")
        self.change2 = baker.make(
            AssetVersionChange, version=self.version, ayah=self.ayah2, change_type="added", new_text="louange", order=2
        )

    def _auth_reviewer(self):
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_REVIEW_CONTENT)
        MemberLanguage.objects.create(member=self.membership, language="fr")

    def _bulk_url(self):
        return f"/portal/content/translations/{self.asset.slug}/review/changes/bulk-approve/"

    def test_bulk_approve_where_change_ids_given_should_approve_only_those(self):
        # Arrange
        self._auth_reviewer()

        # Act
        response = self.client.post(
            self._bulk_url(), data={"language": "fr", "change_ids": [self.change.id]}, content_type="application/json"
        )

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual({"approved": 1}, response.json())
        review = AssetVersionChangeReview.objects.get(change=self.change)
        self.assertEqual((ReviewStateChoice.APPROVED, self.user), (review.state, review.reviewed_by))
        self.assertFalse(AssetVersionChangeReview.objects.filter(change=self.change2).exists())

    def test_bulk_approve_where_no_change_ids_should_approve_every_matching_change(self):
        # Arrange
        self._auth_reviewer()

        # Act
        response = self.client.post(self._bulk_url(), data={"language": "fr"}, content_type="application/json")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual({"approved": 2}, response.json())
        self.assertEqual(
            2, AssetVersionChangeReview.objects.filter(state=ReviewStateChoice.APPROVED, reviewed_by=self.user).count()
        )

    def test_bulk_approve_where_already_approved_should_skip_it(self):
        # Arrange
        self._auth_reviewer()
        other = User.objects.create_user(email="other@example.com", name="Other", is_staff=True)
        reviewed_at = timezone.now() - timezone.timedelta(days=1)
        AssetVersionChangeReview.objects.create(
            change=self.change, state=ReviewStateChoice.APPROVED, reviewed_by=other, reviewed_at=reviewed_at
        )

        # Act
        response = self.client.post(self._bulk_url(), data={"language": "fr"}, content_type="application/json")

        # Assert — the earlier approval keeps its auditing
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual({"approved": 1}, response.json())
        review = AssetVersionChangeReview.objects.get(change=self.change)
        self.assertEqual((other, reviewed_at), (review.reviewed_by, review.reviewed_at))

    def test_bulk_approve_where_commented_should_approve_and_clear_comment(self):
        # Arrange
        self._auth_reviewer()
        AssetVersionChangeReview.objects.create(
            change=self.change,
            state=ReviewStateChoice.COMMENTED,
            comment="typo",
            reviewed_by=self.user,
            reviewed_at=timezone.now(),
        )

        # Act
        response = self.client.post(
            self._bulk_url(), data={"language": "fr", "state": "commented"}, content_type="application/json"
        )

        # Assert — the state filter scopes it to the commented change
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual({"approved": 1}, response.json())
        review = AssetVersionChangeReview.objects.get(change=self.change)
        self.assertEqual((ReviewStateChoice.APPROVED, ""), (review.state, review.comment))
        self.assertFalse(AssetVersionChangeReview.objects.filter(change=self.change2).exists())

    def test_bulk_approve_where_version_given_should_approve_only_the_changes_that_make_it_up(self):
        # Arrange
        self._auth_reviewer()
        v2 = baker.make(AssetVersion, asset=self.asset, asset_language=self.fr, name="v2")
        AssetVersion.objects.filter(pk=v2.pk).update(created_at=timezone.now() + timezone.timedelta(hours=1))
        later = baker.make(
            AssetVersionChange, version=v2, ayah=self.ayah, change_type="modified", new_text="x", order=1
        )

        # Act
        response = self.client.post(
            self._bulk_url(), data={"language": "fr", "version": self.version.id}, content_type="application/json"
        )

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual({"approved": 2}, response.json())
        self.assertFalse(AssetVersionChangeReview.objects.filter(change=later).exists())

    def test_bulk_approve_where_change_of_another_language_should_return_404(self):
        # Arrange
        self._auth_reviewer()
        es = AssetLanguage.objects.create(asset=self.asset, language="es")
        es_version = baker.make(AssetVersion, asset=self.asset, asset_language=es, name="v1")
        es_change = baker.make(AssetVersionChange, version=es_version, ayah=self.ayah, change_type="added", order=1)

        # Act
        response = self.client.post(
            self._bulk_url(),
            data={"language": "fr", "change_ids": [self.change.id, es_change.id]},
            content_type="application/json",
        )

        # Assert — nothing is approved
        self.assertEqual(404, response.status_code, response.content)
        self.assertEqual("change_not_found", response.json()["error_name"])
        self.assertFalse(AssetVersionChangeReview.objects.exists())

    def test_bulk_approve_where_version_unknown_should_return_404(self):
        # Arrange
        self._auth_reviewer()

        # Act
        response = self.client.post(
            self._bulk_url(), data={"language": "fr", "version": 999999}, content_type="application/json"
        )

        # Assert
        self.assertEqual(404, response.status_code, response.content)
        self.assertEqual("version_not_found", response.json()["error_name"])

    def test_bulk_approve_where_language_not_assigned_should_return_403(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_REVIEW_CONTENT)

        # Act
        response = self.client.post(self._bulk_url(), data={"language": "fr"}, content_type="application/json")

        # Assert
        self.assertEqual(403, response.status_code, response.content)
        self.assertEqual("language_not_assigned", response.json()["error_name"])
        self.assertFalse(AssetVersionChangeReview.objects.exists())

    def test_bulk_approve_where_no_review_permission_should_return_403(self):
        # Arrange
        self.authenticate_user(self.user)
        MemberLanguage.objects.create(member=self.membership, language="fr")

        # Act
        response = self.client.post(self._bulk_url(), data={"language": "fr"}, content_type="application/json")

        # Assert
        self.assertEqual(403, response.status_code, response.content)
        self.assertFalse(AssetVersionChangeReview.objects.exists())
