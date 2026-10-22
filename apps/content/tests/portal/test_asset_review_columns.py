from django.utils import timezone
from model_bakery import baker

from apps.content.models import (
    Asset,
    AssetColumn,
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
from apps.content.tests.quran_data import QuranDataMixin
from apps.core.permissions import PermissionChoice
from apps.core.tests.base import BaseTestCase
from apps.users.models import User


class MultiColumnReviewTests(QuranDataMixin, BaseTestCase):
    def setUp(self):
        super().setUp()
        self.bake_quran()
        self.asset = baker.make(
            Asset,
            category=CategoryChoice.TAFSIR,
            template=AssetTemplateChoice.AYAH,
            status=StatusChoice.READY,
            language="ar",
        )
        self.question = AssetColumn.objects.create(asset=self.asset, key="question", order=0, label_en="Question")
        self.answer = AssetColumn.objects.create(asset=self.asset, key="answer", order=1, label_ar="الجواب")
        self.content = AssetContentRepository()
        self.reviews = AssetReviewRepository()

    def _commit(self, cells: dict, name: str) -> AssetVersion:
        draft = baker.make(AssetVersion, asset=self.asset, state=VersionStateChoice.DRAFT, content_edited=True)
        for (ayah, column), text in cells.items():
            AssetVersionEntry.objects.create(version=draft, ayah=ayah, column=column, text=text, order=ayah.id)
        draft.name = name
        return self.content.publish_draft(draft)

    def _approve(self, version: AssetVersion, column: AssetColumn) -> None:
        change = AssetVersionChange.objects.get(version=version, column=column)
        AssetVersionChangeReview.objects.create(
            change=change, state=ReviewStateChoice.APPROVED, reviewed_at=timezone.now()
        )

    def test_pending_cells_by_version_where_two_cells_of_one_ayah_changed_should_count_two(self):
        # Arrange
        version = self._commit({(self.ayah1, self.question): "Q", (self.ayah1, self.answer): "A"}, "1.0")

        # Act
        pending = self.reviews.pending_cells_by_version(self.asset, "ar")

        # Assert
        self.assertEqual(pending[version.pk], 2)

    def test_pending_cells_by_version_where_one_cell_approved_should_leave_the_other_pending(self):
        # Arrange
        version = self._commit({(self.ayah1, self.question): "Q", (self.ayah1, self.answer): "A"}, "1.0")
        self._approve(version, self.question)

        # Act
        pending = self.reviews.pending_cells_by_version(self.asset, "ar")

        # Assert
        self.assertEqual(pending[version.pk], 1)

    def test_set_published_where_one_cell_unapproved_should_return_version_not_approved(self):
        # Arrange
        version = self._commit({(self.ayah1, self.question): "Q", (self.ayah1, self.answer): "A"}, "1.0")
        self._approve(version, self.question)
        user = User.objects.create_user(email="pub@example.com", name="Publisher", is_staff=True)
        for permission in (
            PermissionChoice.PORTAL_READ_TAFSIR,
            PermissionChoice.PORTAL_PUBLISH_CONTENT,
            PermissionChoice.PORTAL_ACCESS_ALL_LANGUAGES,
        ):
            self.give_permission(user, permission)
        self.authenticate_user(user)

        # Act
        response = self.client.post(
            f"/portal/content/tafsirs/{self.asset.slug}/versions/{version.id}/set-published/",
            data={},
            content_type="application/json",
        )

        # Assert
        self.assertEqual(response.status_code, 400, response.content)
        self.assertEqual(response.json()["error_name"], "version_not_approved")

    def test_changes_for_where_as_of_version_should_list_both_cells(self):
        # Arrange
        version = self._commit({(self.ayah1, self.question): "Q", (self.ayah1, self.answer): "A"}, "1.0")

        # Act
        changes = list(self.reviews.changes_for(self.asset, "ar", as_of=version))

        # Assert
        self.assertEqual(sorted(change.column.key for change in changes), ["answer", "question"])

    def test_changes_for_where_other_column_approved_should_not_use_it_as_baseline(self):
        # Arrange
        first = self._commit({(self.ayah1, self.question): "Q"}, "1.0")
        self._approve(first, self.question)
        self._commit({(self.ayah1, self.question): "Q", (self.ayah1, self.answer): "A"}, "1.1")

        # Act
        answer_change = next(
            change for change in self.reviews.changes_for(self.asset, "ar") if change.column.key == "answer"
        )

        # Assert
        self.assertIsNone(answer_change.baseline_text)

    def test_list_review_changes_where_two_columns_should_include_column_and_labels(self):
        # Arrange
        self._commit({(self.ayah1, self.answer): "A"}, "1.0")
        user = User.objects.create_user(email="rev@example.com", name="Reviewer", is_staff=True)
        for permission in (
            PermissionChoice.PORTAL_READ_TAFSIR,
            PermissionChoice.PORTAL_REVIEW_CONTENT,
            PermissionChoice.PORTAL_ACCESS_ALL_LANGUAGES,
        ):
            self.give_permission(user, permission)
        self.authenticate_user(user)

        # Act
        response = self.client.get(f"/portal/content/tafsirs/{self.asset.slug}/review/changes/?language=ar")

        # Assert
        self.assertEqual(response.status_code, 200, response.content)
        item = response.json()["results"][0]
        self.assertEqual((item["column"], item["column_label_en"], item["column_label_ar"]), ("answer", "", "الجواب"))
