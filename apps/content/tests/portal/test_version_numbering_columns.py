from model_bakery import baker

from apps.content.columns import requires_major_bump
from apps.content.models import (
    Asset,
    AssetColumn,
    AssetTemplateChoice,
    AssetVersion,
    AssetVersionEntry,
    CategoryChoice,
    StatusChoice,
    VersionStateChoice,
)
from apps.content.repositories.asset_content import AssetContentRepository
from apps.content.tests.quran_data import QuranDataMixin
from apps.core.permissions import PermissionChoice
from apps.core.tests.base import BaseTestCase
from apps.users.models import User


class RequiresMajorBumpTests(BaseTestCase):
    def test_requires_major_bump_where_column_appended_should_be_false(self):
        # Arrange / Act / Assert
        self.assertFalse(requires_major_bump(["a", "b"], ["a", "b", "c"]))

    def test_requires_major_bump_where_column_inserted_first_should_be_false(self):
        # Arrange / Act / Assert
        self.assertFalse(requires_major_bump(["a", "b"], ["c", "a", "b"]))

    def test_requires_major_bump_where_columns_swapped_should_be_true(self):
        # Arrange / Act / Assert
        self.assertTrue(requires_major_bump(["a", "b"], ["b", "a"]))


class ColumnReorderVersioningTests(QuranDataMixin, BaseTestCase):
    def setUp(self):
        super().setUp()
        self.bake_quran()
        self.user = User.objects.create_user(email="committer@example.com", name="Committer", is_staff=True)
        for permission in (
            PermissionChoice.PORTAL_READ_TAFSIR,
            PermissionChoice.PORTAL_EDIT_TAFSIR_CONTENT,
            PermissionChoice.PORTAL_ACCESS_ALL_LANGUAGES,
        ):
            self.give_permission(self.user, permission)
        self.asset = baker.make(
            Asset,
            category=CategoryChoice.TAFSIR,
            template=AssetTemplateChoice.AYAH,
            status=StatusChoice.READY,
            language="ar",
        )
        self.question = AssetColumn.objects.create(asset=self.asset, key="question", order=0)
        self.answer = AssetColumn.objects.create(asset=self.asset, key="answer", order=1)
        self.source = self.asset.get_or_create_source_language()
        first = self._draft("Q1")
        first.name = "1.0"
        AssetContentRepository().publish_draft(first)

    def _draft(self, text: str) -> AssetVersion:
        draft = baker.make(
            AssetVersion,
            asset=self.asset,
            asset_language=self.source,
            state=VersionStateChoice.DRAFT,
            content_edited=True,
        )
        AssetVersionEntry.objects.create(version=draft, ayah=self.ayah1, column=self.question, text=text)
        return draft

    def _reorder(self) -> None:
        AssetColumn.objects.filter(pk=self.answer.pk).update(order=0)
        AssetColumn.objects.filter(pk=self.question.pk).update(order=1)

    def _publish(self, draft: AssetVersion, bump: str):
        return self.client.post(
            f"/portal/content/tafsirs/{self.asset.slug}/versions/{draft.id}/publish/",
            data={"summary_en": "change", "bump": bump},
            content_type="application/json",
        )

    def test_publish_draft_where_columns_reordered_and_minor_should_return_major_bump_required(self):
        # Arrange
        draft = self._draft("Q2")
        self._reorder()
        self.authenticate_user(self.user)

        # Act
        response = self._publish(draft, "minor")

        # Assert
        self.assertEqual(response.status_code, 400, response.content)
        self.assertEqual(response.json()["error_name"], "major_bump_required")

    def test_publish_draft_where_columns_reordered_and_major_should_publish_next_major(self):
        # Arrange
        draft = self._draft("Q2")
        self._reorder()
        self.authenticate_user(self.user)

        # Act
        response = self._publish(draft, "major")

        # Assert
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["name"], "2.0")

    def test_publish_draft_where_column_added_and_minor_should_publish_next_minor(self):
        # Arrange
        draft = self._draft("Q2")
        AssetColumn.objects.create(asset=self.asset, key="extra", order=2)
        self.authenticate_user(self.user)

        # Act
        response = self._publish(draft, "minor")

        # Assert
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["name"], "1.1")

    def test_get_version_where_draft_after_reorder_should_report_requires_major(self):
        # Arrange
        draft = self._draft("Q2")
        self._reorder()
        self.authenticate_user(self.user)

        # Act
        response = self.client.get(f"/portal/content/tafsirs/{self.asset.slug}/versions/{draft.id}/")

        # Assert
        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(response.json()["requires_major"])
