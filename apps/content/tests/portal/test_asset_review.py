from django.utils import timezone
from model_bakery import baker

from apps.content.models import (
    Asset,
    AssetLanguage,
    AssetVersion,
    AssetVersionChange,
    AssetVersionChangeReview,
    CategoryChoice,
    ReviewerLanguage,
    ReviewStateChoice,
    StatusChoice,
)
from apps.core.permissions import PermissionChoice
from apps.core.tests.base import BaseTestCase
from apps.publishers.models import Publisher, PublisherMember
from apps.quran.models import Ayah, Sura
from apps.users.models import User


class AssetReviewApiBaseTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.publisher = baker.make(Publisher, name="P")
        self.asset = baker.make(
            Asset,
            category=CategoryChoice.TRANSLATION,
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
        ReviewerLanguage.objects.create(member=self.membership, language="fr")

        # Act
        response = self.client.get(self._changes_url("?language=fr"))

        # Assert
        self.assertEqual(403, response.status_code, response.content)


class ReviewAssignmentTest(AssetReviewApiBaseTest):
    def test_list_changes_where_language_not_assigned_should_return_403(self):
        # Arrange — assigned 'es', not 'fr'
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_REVIEW_CONTENT)
        ReviewerLanguage.objects.create(member=self.membership, language="es")

        # Act
        response = self.client.get(self._changes_url("?language=fr"))

        # Assert
        self.assertEqual(403, response.status_code, response.content)
        self.assertEqual("language_not_assigned", response.json()["error_name"])

    def test_list_languages_should_return_only_assigned(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_REVIEW_CONTENT)
        ReviewerLanguage.objects.create(member=self.membership, language="fr")

        # Act
        response = self.client.get(f"/portal/content/translations/{self.asset.slug}/review/languages/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual(["fr"], response.json())


class ReviewActionTest(AssetReviewApiBaseTest):
    def _auth_reviewer(self):
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_REVIEW_CONTENT)
        ReviewerLanguage.objects.create(member=self.membership, language="fr")

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
        self.assertEqual(1, row["sura"])
        self.assertEqual(1, row["aya"])
        self.assertEqual("added", row["change_type"])
        self.assertEqual("unreviewed", row["review_state"])
        self.assertIn("baseline_text", row)
