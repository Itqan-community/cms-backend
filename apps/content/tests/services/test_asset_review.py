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
from apps.content.services.asset_review import AssetReviewService
from apps.core.ninja_utils.errors import ItqanError
from apps.core.tests.base import BaseTestCase
from apps.quran.models import Ayah, Sura
from apps.users.models import User


class AssetReviewServiceTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.asset = baker.make(
            Asset, category=CategoryChoice.TRANSLATION, status=StatusChoice.READY, language="ar", slug="t1"
        )
        self.fr = AssetLanguage.objects.create(asset=self.asset, language="fr")
        self.version = baker.make(AssetVersion, asset=self.asset, asset_language=self.fr, name="v1")
        self.sura = baker.make(Sura, id=1, name="الفاتحة", ayas_count=3)
        self.ayah = baker.make(Ayah, id=1, sura=self.sura, number_in_sura=1, text="a")
        self.change = baker.make(
            AssetVersionChange, version=self.version, ayah=self.ayah, change_type="added", new_text="au nom", order=1
        )
        self.reviewer = User.objects.create_user(email="rev@example.com", name="Rev")
        ReviewerLanguage.objects.create(user=self.reviewer, language="fr")

    def test_set_review_state_where_assigned_should_approve_and_record_auditing(self):
        # Act
        change = AssetReviewService().set_review_state(
            "t1",
            CategoryChoice.TRANSLATION,
            change_id=self.change.id,
            user=self.reviewer,
            state="approved",
            comment="",
        )

        # Assert
        self.assertEqual(ReviewStateChoice.APPROVED, change.review.state)
        self.assertEqual(self.reviewer, change.review.reviewed_by)
        self.assertIsNotNone(change.review.reviewed_at)

    def test_set_review_state_where_commented_without_text_should_raise(self):
        # Act / Assert
        with self.assertRaises(ItqanError) as ctx:
            AssetReviewService().set_review_state(
                "t1",
                CategoryChoice.TRANSLATION,
                change_id=self.change.id,
                user=self.reviewer,
                state="commented",
                comment="   ",
            )
        self.assertEqual("review_comment_required", ctx.exception.error_name)

    def test_set_review_state_where_language_not_assigned_should_raise_403(self):
        # Arrange — reviewer is only assigned 'fr'; make an 'ar' (source) change
        source = self.asset.get_or_create_source_language()
        src_version = baker.make(AssetVersion, asset=self.asset, asset_language=source, name="src")
        src_change = baker.make(
            AssetVersionChange, version=src_version, ayah=self.ayah, change_type="added", new_text="بسم", order=1
        )

        # Act / Assert
        with self.assertRaises(ItqanError) as ctx:
            AssetReviewService().set_review_state(
                "t1",
                CategoryChoice.TRANSLATION,
                change_id=src_change.id,
                user=self.reviewer,
                state="approved",
                comment="",
            )
        self.assertEqual("language_not_assigned", ctx.exception.error_name)
        self.assertEqual(403, ctx.exception.status_code)

    def test_set_review_state_where_unreviewed_should_delete_row(self):
        # Arrange
        svc = AssetReviewService()
        svc.set_review_state(
            "t1", CategoryChoice.TRANSLATION, change_id=self.change.id, user=self.reviewer, state="approved", comment=""
        )

        # Act
        svc.set_review_state(
            "t1",
            CategoryChoice.TRANSLATION,
            change_id=self.change.id,
            user=self.reviewer,
            state="unreviewed",
            comment="",
        )

        # Assert
        self.assertFalse(AssetVersionChangeReview.objects.filter(change=self.change).exists())

    def test_list_review_languages_should_return_intersection_of_assigned_and_asset(self):
        # Act
        langs = AssetReviewService().list_review_languages("t1", CategoryChoice.TRANSLATION, user=self.reviewer)

        # Assert — only 'fr' (assigned), even though the asset also has 'ar'
        self.assertEqual(["fr"], langs)

    def test_list_changes_where_unreviewed_filter_should_return_pending_change(self):
        # Act
        qs = AssetReviewService().list_changes(
            "t1", CategoryChoice.TRANSLATION, language="fr", user=self.reviewer, state="unreviewed"
        )

        # Assert
        self.assertEqual([self.change.id], [c.id for c in qs])

    def test_list_changes_where_language_not_assigned_should_raise_403(self):
        # Act / Assert
        with self.assertRaises(ItqanError) as ctx:
            AssetReviewService().list_changes(
                "t1", CategoryChoice.TRANSLATION, language="ar", user=self.reviewer, state=None
            )
        self.assertEqual("language_not_assigned", ctx.exception.error_name)
