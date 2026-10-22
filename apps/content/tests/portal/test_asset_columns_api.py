from model_bakery import baker

from apps.content.models import (
    Asset,
    AssetColumn,
    AssetTemplateChoice,
    AssetVersion,
    CategoryChoice,
    StatusChoice,
    VersionStateChoice,
)
from apps.core.permissions import PermissionChoice
from apps.core.tests.base import BaseTestCase
from apps.publishers.models import Publisher, PublisherMember
from apps.users.models import User


class AssetColumnsApiTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.asset = baker.make(
            Asset, category=CategoryChoice.TAFSIR, template=AssetTemplateChoice.AYAH, status=StatusChoice.READY
        )
        self.url = f"/portal/content/tafsirs/{self.asset.slug}/columns/"
        self.user = User.objects.create_user(email="columns@example.com", name="Columns", is_staff=True)
        self.give_permission(self.user, PermissionChoice.PORTAL_READ_TAFSIR)

    def test_list_columns_where_read_permission_should_return_default_column(self):
        # Arrange
        self.authenticate_user(self.user)

        # Act
        response = self.client.get(self.url)

        # Assert
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(
            response.json(), [{"key": "text", "label_en": "", "label_ar": "", "order": 0, "committed": False}]
        )

    def test_list_columns_where_asset_has_no_column_rows_should_not_write_any(self):
        # Arrange
        self.authenticate_user(self.user)

        # Act
        response = self.client.get(self.url)

        # Assert
        self.assertEqual(response.status_code, 200, response.content)
        self.assertFalse(AssetColumn.objects.filter(asset=self.asset).exists())

    def test_create_column_where_missing_manage_permission_should_return_403(self):
        # Arrange
        self.give_permission(self.user, PermissionChoice.PORTAL_ACCESS_ALL_LANGUAGES)
        self.authenticate_user(self.user)

        # Act
        response = self.client.post(self.url, data={"key": "answer"}, content_type="application/json")

        # Assert
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["error_name"], "permission_denied")

    def test_create_column_where_missing_all_languages_should_return_403(self):
        # Arrange
        self.give_permission(self.user, PermissionChoice.PORTAL_MANAGE_ASSET_COLUMNS)
        self.authenticate_user(self.user)

        # Act
        response = self.client.post(self.url, data={"key": "answer"}, content_type="application/json")

        # Assert
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["error_name"], "permission_denied")

    def test_create_column_where_permitted_should_return_201(self):
        # Arrange
        self.give_permission(self.user, PermissionChoice.PORTAL_MANAGE_ASSET_COLUMNS)
        self.give_permission(self.user, PermissionChoice.PORTAL_ACCESS_ALL_LANGUAGES)
        self.authenticate_user(self.user)

        # Act
        response = self.client.post(
            self.url,
            data={"key": "answer", "label_en": "Answer", "label_ar": "الجواب"},
            content_type="application/json",
        )

        # Assert
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(
            response.json(),
            {"key": "answer", "label_en": "Answer", "label_ar": "الجواب", "order": 1, "committed": False},
        )

    def test_create_column_where_key_taken_should_return_400(self):
        # Arrange
        self.give_permission(self.user, PermissionChoice.PORTAL_MANAGE_ASSET_COLUMNS)
        self.give_permission(self.user, PermissionChoice.PORTAL_ACCESS_ALL_LANGUAGES)
        self.authenticate_user(self.user)

        # Act
        response = self.client.post(self.url, data={"key": "text"}, content_type="application/json")

        # Assert
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error_name"], "column_key_taken")

    def test_update_column_where_committed_key_change_should_return_400(self):
        # Arrange
        self.give_permission(self.user, PermissionChoice.PORTAL_MANAGE_ASSET_COLUMNS)
        self.give_permission(self.user, PermissionChoice.PORTAL_ACCESS_ALL_LANGUAGES)
        self.asset.ensure_text_columns()
        baker.make(AssetVersion, asset=self.asset, state=VersionStateChoice.PUBLISHED, column_keys=["text"])
        self.authenticate_user(self.user)

        # Act
        response = self.client.patch(f"{self.url}text/", data={"key": "question"}, content_type="application/json")

        # Assert
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error_name"], "column_committed")

    def test_list_columns_where_committed_should_report_it(self):
        # Arrange
        self.asset.ensure_text_columns()
        baker.make(AssetVersion, asset=self.asset, state=VersionStateChoice.PUBLISHED, column_keys=["text"])
        self.authenticate_user(self.user)

        # Act
        response = self.client.get(self.url)

        # Assert
        self.assertTrue(response.json()[0]["committed"])

    def test_reorder_columns_where_permitted_should_return_new_order(self):
        # Arrange
        self.give_permission(self.user, PermissionChoice.PORTAL_MANAGE_ASSET_COLUMNS)
        self.give_permission(self.user, PermissionChoice.PORTAL_ACCESS_ALL_LANGUAGES)
        self.asset.ensure_text_columns()
        AssetColumn.objects.create(asset=self.asset, key="answer", order=1)
        self.authenticate_user(self.user)

        # Act
        response = self.client.put(
            f"{self.url}order/", data={"keys": ["answer", "text"]}, content_type="application/json"
        )

        # Assert
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual([c["key"] for c in response.json()], ["answer", "text"])

    def test_delete_column_where_unknown_key_should_return_404(self):
        # Arrange
        self.give_permission(self.user, PermissionChoice.PORTAL_MANAGE_ASSET_COLUMNS)
        self.give_permission(self.user, PermissionChoice.PORTAL_ACCESS_ALL_LANGUAGES)
        self.authenticate_user(self.user)

        # Act
        response = self.client.delete(f"{self.url}nope/")

        # Assert
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error_name"], "column_not_found")

    def test_delete_column_where_uncommitted_should_return_204(self):
        # Arrange
        self.give_permission(self.user, PermissionChoice.PORTAL_MANAGE_ASSET_COLUMNS)
        self.give_permission(self.user, PermissionChoice.PORTAL_ACCESS_ALL_LANGUAGES)
        self.asset.ensure_text_columns()
        AssetColumn.objects.create(asset=self.asset, key="answer", order=1)
        self.authenticate_user(self.user)

        # Act
        response = self.client.delete(f"{self.url}answer/")

        # Assert
        self.assertEqual(response.status_code, 204)
        self.assertFalse(AssetColumn.objects.filter(asset=self.asset, key="answer").exists())

    def test_create_column_where_member_of_another_publisher_should_return_404(self):
        # Arrange
        self.asset.publisher = baker.make(Publisher, name="Owner")
        self.asset.save(update_fields=["publisher"])
        outsider = User.objects.create_user(email="outsider@example.com", name="Outsider")  # not staff: scoped
        baker.make(
            PublisherMember,
            user=outsider,
            publisher=baker.make(Publisher, name="Other"),
            status=PublisherMember.StatusChoice.ACTIVE,
        )
        for permission in (
            PermissionChoice.PORTAL_ACCESS,
            PermissionChoice.PORTAL_READ_TAFSIR,
            PermissionChoice.PORTAL_MANAGE_ASSET_COLUMNS,
            PermissionChoice.PORTAL_ACCESS_ALL_LANGUAGES,
        ):
            self.give_permission(outsider, permission)
        self.authenticate_user(outsider)

        # Act
        response = self.client.post(self.url, data={"key": "answer"}, content_type="application/json")

        # Assert
        self.assertEqual(response.status_code, 404, response.content)
        self.assertEqual(response.json()["error_name"], "tafsir_not_found")
        self.assertFalse(AssetColumn.objects.filter(asset=self.asset, key="answer").exists())
