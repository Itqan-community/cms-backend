from django.utils import timezone
from model_bakery import baker

from apps.content.models import (
    Asset,
    AssetTemplateChoice,
    AssetVersion,
    AssetVersionChange,
    AssetVersionChangeReview,
    CategoryChoice,
    ChangeTypeChoice,
    ReviewStateChoice,
    StatusChoice,
    VersionStateChoice,
)
from apps.core.permissions import PermissionChoice
from apps.core.tests.base import BaseTestCase
from apps.publishers.models import Publisher
from apps.quran.models import Ayah, Sura
from apps.users.models import User


class VersionReviewCommentsTests(BaseTestCase):
    """Reviewers' outcomes show up where editors look at versions."""

    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user(email="history-reader@example.com", name="Reader", is_staff=True)
        self.reviewer = User.objects.create_user(email="reviewer@example.com", name="Aisha", is_staff=True)
        self.give_permission(self.user, PermissionChoice.PORTAL_ACCESS_ALL_LANGUAGES)
        self.give_permission(self.user, PermissionChoice.PORTAL_READ_TAFSIR)
        sura = baker.make(Sura, id=1, name="الفاتحة", ayas_count=2)
        self.ayahs = [baker.make(Ayah, id=i, sura=sura, number_in_sura=i, text=f"ayah {i}") for i in (1, 2)]
        self.tafsir = baker.make(
            Asset,
            publisher=baker.make(Publisher, name="Review Publisher"),
            category=CategoryChoice.TAFSIR,
            template=AssetTemplateChoice.AYAH,
            status=StatusChoice.READY,
            slug="reviewed-tafsir",
            language="ar",
        )
        self.version = baker.make(
            AssetVersion,
            asset=self.tafsir,
            asset_language=self.tafsir.get_or_create_source_language(),
            name="v1",
            state=VersionStateChoice.PUBLISHED,
        )
        self.commented = AssetVersionChange.objects.create(
            version=self.version,
            ayah=self.ayahs[0],
            change_type=ChangeTypeChoice.ADDED,
            old_text="",
            new_text="a",
            order=1,
        )
        self.untouched = AssetVersionChange.objects.create(
            version=self.version,
            ayah=self.ayahs[1],
            change_type=ChangeTypeChoice.ADDED,
            old_text="",
            new_text="b",
            order=2,
        )
        AssetVersionChangeReview.objects.create(
            change=self.commented,
            state=ReviewStateChoice.COMMENTED,
            comment="Spelling of the first word",
            reviewed_by=self.reviewer,
            reviewed_at=timezone.now(),
        )

    def test_version_diff_where_change_was_commented_should_return_the_review(self):
        # Arrange
        self.authenticate_user(self.user)

        # Act
        response = self.client.get(f"/portal/content/tafsirs/{self.tafsir.slug}/versions/{self.version.id}/diff/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        rows = {row["unit_id"]: row for row in response.json()["results"]}
        commented = rows[self.ayahs[0].id]
        self.assertEqual(commented["review_state"], "commented")
        self.assertEqual(commented["review_comment"], "Spelling of the first word")
        self.assertEqual(commented["reviewed_by"], "Aisha")
        self.assertIsNotNone(commented["reviewed_at"])

    def test_version_diff_where_change_not_reviewed_should_say_unreviewed(self):
        # Arrange
        self.authenticate_user(self.user)

        # Act
        response = self.client.get(f"/portal/content/tafsirs/{self.tafsir.slug}/versions/{self.version.id}/diff/")

        # Assert
        rows = {row["unit_id"]: row for row in response.json()["results"]}
        untouched = rows[self.ayahs[1].id]
        self.assertEqual(untouched["review_state"], "unreviewed")
        self.assertEqual(untouched["review_comment"], "")
        self.assertIsNone(untouched["reviewed_by"])

    def test_list_versions_where_a_change_has_a_comment_should_count_it(self):
        # Arrange
        self.authenticate_user(self.user)
        AssetVersionChangeReview.objects.create(
            change=self.untouched,
            state=ReviewStateChoice.APPROVED,
            comment="",
            reviewed_by=self.reviewer,
            reviewed_at=timezone.now(),
        )

        # Act
        response = self.client.get(f"/portal/tafsirs/{self.tafsir.slug}/versions/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual(response.json()["results"][0]["review_comments_count"], 1)
