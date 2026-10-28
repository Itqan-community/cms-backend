from django.db import connection
from django.test.utils import CaptureQueriesContext
from model_bakery import baker

from apps.content.models import (
    Asset,
    AssetTemplateChoice,
    AssetVersion,
    AssetVersionChange,
    CategoryChoice,
    ChangeTypeChoice,
    StatusChoice,
    VersionStateChoice,
)
from apps.content.repositories.asset_review import AssetReviewRepository
from apps.content.tests.group_quran_data import GroupQuranDataMixin
from apps.content.unit_keys import encode_group_key
from apps.core.permissions import PermissionChoice
from apps.core.tests.base import BaseTestCase
from apps.users.models import User


class GroupReviewTests(GroupQuranDataMixin, BaseTestCase):
    def setUp(self):
        super().setUp()
        self.bake_group_quran()
        self.asset = baker.make(
            Asset,
            category=CategoryChoice.TAFSIR,
            status=StatusChoice.READY,
            template=AssetTemplateChoice.AYAH_GROUP,
            language="ar",
        )
        self.column = self.asset.ensure_text_columns()[0]
        self.version = baker.make(AssetVersion, asset=self.asset, state=VersionStateChoice.PUBLISHED, name="1.0")

    def _change(self, start: int, end: int, text: str = "t") -> AssetVersionChange:
        return AssetVersionChange.objects.create(
            version=self.version,
            column=self.column,
            change_type=ChangeTypeChoice.ADDED,
            new_text=text,
            order=start,
            from_ayah_id=start,
            to_ayah_id=end,
        )

    def test_pending_cells_by_version_where_overlapping_groups_should_count_each(self):
        # Arrange
        self._change(1, 3)
        self._change(1, 1)

        # Act
        pending = AssetReviewRepository().pending_cells_by_version(self.asset, "ar")

        # Assert
        self.assertEqual(pending, {self.version.pk: 2})

    def test_list_review_changes_where_group_change_should_return_range_label(self):
        # Arrange
        user = User.objects.create_user(email="reviewer@example.com", name="Reviewer", is_staff=True)
        self.authenticate_user(user)
        self.give_permission(user, PermissionChoice.PORTAL_REVIEW_CONTENT)
        self.give_permission(user, PermissionChoice.PORTAL_ACCESS_ALL_LANGUAGES)
        self._change(1, 3)

        # Act
        response = self.client.get(f"/portal/content/tafsirs/{self.asset.slug}/review/changes/?language=ar")

        # Assert
        self.assertEqual(response.status_code, 200, response.content)
        row = response.json()["results"][0]
        self.assertEqual((row["label"], row["unit_id"]), ("1:1 → 1:3", encode_group_key(1, 3)))

    def test_changes_for_where_group_changes_should_use_constant_queries(self):
        # Arrange
        repo = AssetReviewRepository()
        self._change(1, 2)
        self._change(3, 4)
        with CaptureQueriesContext(connection) as few:
            [str(change.from_ayah) + str(change.to_ayah) for change in repo.changes_for(self.asset, "ar")]
        for start in range(1, 6):
            for end in range(start, 6):
                if (start, end) not in ((1, 2), (3, 4)):
                    self._change(start, end)

        # Act
        with CaptureQueriesContext(connection) as many:
            labels = [str(change.from_ayah) + str(change.to_ayah) for change in repo.changes_for(self.asset, "ar")]

        # Assert
        self.assertEqual(len(labels), 15)
        self.assertEqual(len(many), len(few))
