from django.db import IntegrityError
from django.utils import timezone
from model_bakery import baker

from apps.content.models import (
    Asset,
    AssetTemplateChoice,
    AssetVersion,
    AssetVersionChange,
    AssetVersionChangeReview,
    CategoryChoice,
    ReviewStateChoice,
)
from apps.core.tests.base import BaseTestCase
from apps.publishers.models import MemberLanguage, PublisherMember
from apps.quran.models import Ayah, Sura
from apps.users.models import User


class MemberLanguageModelTest(BaseTestCase):
    def test_member_language_where_duplicate_on_member_should_raise_integrity_error(self):
        # Arrange
        member = baker.make(PublisherMember)
        MemberLanguage.objects.create(member=member, language="fr")

        # Act / Assert
        with self.assertRaises(IntegrityError):
            MemberLanguage.objects.create(member=member, language="fr")


class AssetVersionChangeReviewModelTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.asset = baker.make(
            Asset, category=CategoryChoice.TRANSLATION, template=AssetTemplateChoice.AYAH, language="ar"
        )
        self.version = baker.make(AssetVersion, asset=self.asset)
        self.sura = baker.make(Sura, id=1, name="الفاتحة", ayas_count=3)
        self.ayah = baker.make(Ayah, id=1, sura=self.sura, number_in_sura=1, text="a")
        self.change = baker.make(
            AssetVersionChange, version=self.version, ayah=self.ayah, change_type="added", new_text="x", order=1
        )
        self.user = User.objects.create_user(email="r@example.com", name="R")

    def test_review_where_second_row_for_same_change_should_raise_integrity_error(self):
        # Arrange
        AssetVersionChangeReview.objects.create(
            change=self.change, state=ReviewStateChoice.APPROVED, reviewed_by=self.user, reviewed_at=timezone.now()
        )

        # Act / Assert — OneToOne rejects a second row for the same change
        with self.assertRaises(IntegrityError):
            AssetVersionChangeReview.objects.create(
                change=self.change, state=ReviewStateChoice.COMMENTED, reviewed_by=self.user, reviewed_at=timezone.now()
            )

    def test_review_where_created_should_be_reachable_via_related_name(self):
        # Arrange
        AssetVersionChangeReview.objects.create(
            change=self.change, state=ReviewStateChoice.APPROVED, reviewed_by=self.user, reviewed_at=timezone.now()
        )

        # Act
        self.change.refresh_from_db()

        # Assert
        self.assertEqual(ReviewStateChoice.APPROVED, self.change.review.state)
