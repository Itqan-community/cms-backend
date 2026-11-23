import json

from django.core.files.uploadedfile import SimpleUploadedFile
from model_bakery import baker

from apps.content.models import Asset, AssetColumn, AssetVersion
from apps.core.permissions import PermissionChoice
from apps.core.tests.base import BaseTestCase
from apps.publishers.models import Publisher
from apps.quran.models import Ayah, Surah
from apps.users.models import User

QA_COLUMNS = [
    {"key": "question", "label_en": "Question", "label_ar": "السؤال"},
    {"key": "answer", "label_en": "Answer", "label_ar": "الجواب"},
]


class TextAssetCreateColumnsTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.publisher = baker.make(Publisher, name="Test Publisher")
        self.user = User.objects.create_user(email="columns-create@example.com", name="Creator", is_staff=True)
        self.give_permission(self.user, PermissionChoice.PORTAL_CREATE_TEXT_ASSET)

    def give_column_permissions(self) -> None:
        self.give_permission(self.user, PermissionChoice.PORTAL_MANAGE_ASSET_COLUMNS)
        self.give_permission(self.user, PermissionChoice.PORTAL_ACCESS_ALL_LANGUAGES)

    def post(self, **extra):
        return self.client.post(
            "/portal/text-assets/",
            data={
                "name_en": "Questions and Answers",
                "license": "CC-BY",
                "language": "ar",
                "publisher_id": self.publisher.id,
                "template": "ayah",
                "tags": "tafsir",
                **extra,
            },
        )

    def test_create_text_asset_where_columns_given_and_permitted_should_create_them_in_order(self):
        # Arrange
        self.give_column_permissions()
        self.authenticate_user(self.user)

        # Act
        response = self.post(columns=json.dumps(QA_COLUMNS))

        # Assert
        self.assertEqual(201, response.status_code, response.content)
        columns = AssetColumn.objects.filter(asset_id=response.json()["id"])
        self.assertEqual(
            [("question", "Question", "السؤال", 0), ("answer", "Answer", "الجواب", 1)],
            [(c.key, c.label_en, c.label_ar, c.order) for c in columns],
        )

    def test_create_text_asset_where_columns_and_matching_file_given_should_import_every_column(self):
        # Arrange
        self.give_column_permissions()
        surah = baker.make(Surah, id=1, name="الفاتحة", ayahs_count=7)
        baker.make(Ayah, id=1, surah=surah, number_in_surah=1, text="a")
        csv = "surah,ayah,question,answer\n1,1,ما البسملة؟,آية\n".encode()
        self.authenticate_user(self.user)

        # Act
        response = self.post(
            columns=json.dumps(QA_COLUMNS),
            version_number="1.0",
            file=SimpleUploadedFile("qa.csv", csv, content_type="text/csv"),
        )

        # Assert
        self.assertEqual(201, response.status_code, response.content)
        version = AssetVersion.objects.get(asset_id=response.json()["id"])
        self.assertEqual(["question", "answer"], version.column_keys)
        self.assertEqual(
            {"question": "ما البسملة؟", "answer": "آية"},
            {entry.column.key: entry.text for entry in version.entries.select_related("column")},
        )

    def test_create_text_asset_where_columns_given_without_manage_permission_should_return_403(self):
        # Arrange
        self.give_permission(self.user, PermissionChoice.PORTAL_ACCESS_ALL_LANGUAGES)
        self.authenticate_user(self.user)

        # Act
        response = self.post(columns=json.dumps(QA_COLUMNS))

        # Assert
        self.assertEqual(403, response.status_code, response.content)
        self.assertEqual("permission_denied", response.json()["error_name"])
        self.assertFalse(Asset.objects.exists())

    def test_create_text_asset_where_columns_given_without_all_languages_should_return_403(self):
        # Arrange
        self.give_permission(self.user, PermissionChoice.PORTAL_MANAGE_ASSET_COLUMNS)
        self.authenticate_user(self.user)

        # Act
        response = self.post(columns=json.dumps(QA_COLUMNS))

        # Assert
        self.assertEqual(403, response.status_code, response.content)
        self.assertEqual("permission_denied", response.json()["error_name"])
        self.assertFalse(Asset.objects.exists())

    def test_create_text_asset_where_column_key_invalid_should_return_400_and_create_nothing(self):
        # Arrange
        self.give_column_permissions()
        self.authenticate_user(self.user)

        # Act
        response = self.post(columns=json.dumps([{"key": "surah"}]))

        # Assert
        self.assertEqual(400, response.status_code, response.content)
        self.assertEqual("column_key_invalid", response.json()["error_name"])
        self.assertFalse(Asset.objects.exists())

    def test_create_text_asset_where_column_keys_repeat_should_return_400(self):
        # Arrange
        self.give_column_permissions()
        self.authenticate_user(self.user)

        # Act
        response = self.post(columns=json.dumps([{"key": "answer"}, {"key": "answer"}]))

        # Assert
        self.assertEqual(400, response.status_code, response.content)
        self.assertEqual("column_key_taken", response.json()["error_name"])
        self.assertFalse(Asset.objects.exists())

    def test_create_text_asset_where_columns_empty_should_return_400(self):
        # Arrange
        self.give_column_permissions()
        self.authenticate_user(self.user)

        # Act
        response = self.post(columns="[]")

        # Assert
        self.assertEqual(400, response.status_code, response.content)
        self.assertEqual("column_last", response.json()["error_name"])
        self.assertFalse(Asset.objects.exists())

    def test_create_text_asset_where_columns_omitted_should_keep_default_column_unsaved(self):
        # Arrange
        self.authenticate_user(self.user)

        # Act
        response = self.post()

        # Assert
        self.assertEqual(201, response.status_code, response.content)
        asset = Asset.objects.get(id=response.json()["id"])
        self.assertFalse(AssetColumn.objects.filter(asset=asset).exists())
        self.assertEqual(["text"], [column.key for column in asset.text_columns()])
