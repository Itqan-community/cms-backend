import importlib

from django.apps import apps as django_apps
from django.core.files.uploadedfile import SimpleUploadedFile
from model_bakery import baker

from apps.content.models import (
    Asset,
    AssetLanguage,
    AssetTemplateChoice,
    AssetVersion,
    AssetVersionEntry,
    CategoryChoice,
    StatusChoice,
    VersionStateChoice,
)
from apps.core.permissions import PermissionChoice
from apps.core.tests.base import BaseTestCase
from apps.publishers.models import Publisher
from apps.quran.models import Ayah, Sura
from apps.users.models import User

# The module name starts with a digit, so a plain `from ... import` is illegal.
numbering_migration = importlib.import_module("apps.content.migrations.0071_number_tafsir_translation_versions")

CSV = b"surah,ayah,text\n1,1,in the name"


class VersionNumberingBaseTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.publisher = baker.make(Publisher, name="Test Publisher")
        self.tafsir = baker.make(
            Asset,
            category=CategoryChoice.TAFSIR,
            template=AssetTemplateChoice.AYAH,
            publisher=self.publisher,
            status=StatusChoice.READY,
            name="Tafsir Al-Tabari",
            slug="tafsir-al-tabari",
            language="ar",
        )
        self.user = User.objects.create_user(email="editor@example.com", name="Editor", is_staff=True)
        self.give_permission(self.user, PermissionChoice.PORTAL_ACCESS_ALL_LANGUAGES)
        sura = baker.make(Sura, id=1, name="الفاتحة", ayas_count=7)
        self.ayah = baker.make(Ayah, id=1, sura=sura, number_in_sura=1, text="a")

    def upload(self, **data):
        return self.client.post(
            f"/portal/tafsirs/{self.tafsir.slug}/versions/",
            data={
                "asset_id": self.tafsir.id,
                "file": SimpleUploadedFile("t.csv", CSV, content_type="text/csv"),
                **data,
            },
        )

    def make_version(self, name: str, language: str = "ar", **kwargs) -> AssetVersion:
        asset_language, _ = AssetLanguage.objects.get_or_create(
            asset=self.tafsir, language=language, defaults={"is_source": language == self.tafsir.language}
        )
        return baker.make(
            AssetVersion,
            asset=self.tafsir,
            asset_language=asset_language,
            name=name,
            state=kwargs.pop("state", VersionStateChoice.PUBLISHED),
            **kwargs,
        )


class UploadNumberingTest(VersionNumberingBaseTest):
    def test_create_version_where_first_without_number_should_return_400(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_EDIT_TAFSIR_CONTENT)

        # Act
        response = self.upload(label="First")

        # Assert
        self.assertEqual(400, response.status_code, response.content)
        self.assertEqual("version_number_required", response.json()["error_name"])
        self.assertFalse(AssetVersion.objects.filter(asset=self.tafsir).exists())

    def test_create_version_where_number_malformed_should_return_400(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_EDIT_TAFSIR_CONTENT)

        # Act
        response = self.upload(version_number="7")

        # Assert
        self.assertEqual(400, response.status_code, response.content)
        self.assertEqual("version_number_invalid", response.json()["error_name"])

    def test_create_version_where_first_with_number_should_start_sequence_there(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_EDIT_TAFSIR_CONTENT)

        # Act
        response = self.upload(version_number="07.00", label="First edition")

        # Assert — normalized, and the name is kept separately
        self.assertEqual(201, response.status_code, response.content)
        self.assertEqual("7.0", response.json()["name"])
        self.assertEqual("First edition", response.json()["label"])

    def test_create_version_where_sequence_exists_should_bump_minor_and_ignore_start(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_EDIT_TAFSIR_CONTENT)
        self.make_version("7.0")
        self.make_version("7.1")

        # Act
        response = self.upload(version_number="1.0")

        # Assert
        self.assertEqual(201, response.status_code, response.content)
        self.assertEqual("7.2", response.json()["name"])

    def test_create_version_where_bump_major_should_start_next_major(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_EDIT_TAFSIR_CONTENT)
        self.make_version("7.3")

        # Act
        response = self.upload(bump="major")

        # Assert
        self.assertEqual(201, response.status_code, response.content)
        self.assertEqual("8.0", response.json()["name"])

    def test_create_version_where_other_language_numbered_should_start_own_sequence(self):
        # Arrange — the source language is at 7.0; French has no versions yet
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_EDIT_TAFSIR_CONTENT)
        self.make_version("7.0")
        AssetLanguage.objects.create(asset=self.tafsir, language="fr")

        # Act
        without_number = self.upload(language="fr")
        with_number = self.upload(language="fr", version_number="1.0")

        # Assert
        self.assertEqual("version_number_required", without_number.json()["error_name"])
        self.assertEqual(201, with_number.status_code, with_number.content)
        self.assertEqual("1.0", with_number.json()["name"])

    def test_create_tafsir_where_file_uploaded_should_number_first_version(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_CREATE_TAFSIR)

        # Act
        response = self.client.post(
            "/portal/tafsirs/",
            data={
                "name_en": "New Tafsir",
                "license": "CC-BY",
                "language": "ar",
                "publisher_id": self.publisher.id,
                "template": "ayah",
                "version_label": "Original",
                "version_number": "3.0",
                "file": SimpleUploadedFile("t.csv", CSV, content_type="text/csv"),
            },
        )

        # Assert
        self.assertEqual(201, response.status_code, response.content)
        version = AssetVersion.objects.get(asset_id=response.json()["id"])
        self.assertEqual("3.0", version.name)
        self.assertEqual("Original", version.label)


class CommitNumberingTest(VersionNumberingBaseTest):
    def make_draft(self, language: str = "ar") -> AssetVersion:
        draft = self.make_version("", language=language, state=VersionStateChoice.DRAFT, content_edited=True)
        baker.make(AssetVersionEntry, version=draft, ayah=self.ayah, text="edited")
        return draft

    def commit(self, draft: AssetVersion, **data):
        return self.client.post(
            f"/portal/content/tafsirs/{self.tafsir.slug}/versions/{draft.id}/publish/",
            data={"message": "commit", **data},
            content_type="application/json",
        )

    def test_publish_draft_where_sequence_exists_should_issue_next_minor_and_set_label(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_EDIT_TAFSIR_CONTENT)
        self.make_version("7.0")
        draft = self.make_draft()

        # Act
        response = self.commit(draft, label="Revised")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        draft.refresh_from_db()
        self.assertEqual("7.1", draft.name)
        self.assertEqual("Revised", draft.label)

    def test_publish_draft_where_bump_major_should_issue_next_major(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_EDIT_TAFSIR_CONTENT)
        self.make_version("7.4")
        draft = self.make_draft()

        # Act
        response = self.commit(draft, bump="major")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual("8.0", response.json()["name"])

    def test_publish_draft_where_first_without_number_should_return_400_and_stay_draft(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_EDIT_TAFSIR_CONTENT)
        draft = self.make_draft()

        # Act
        response = self.commit(draft)

        # Assert
        self.assertEqual(400, response.status_code, response.content)
        self.assertEqual("version_number_required", response.json()["error_name"])
        draft.refresh_from_db()
        self.assertEqual(VersionStateChoice.DRAFT, draft.state)

    def test_publish_draft_where_first_with_number_should_start_sequence_there(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_EDIT_TAFSIR_CONTENT)
        draft = self.make_draft()

        # Act
        response = self.commit(draft, version_number="7.0")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual("7.0", response.json()["name"])

    def test_restore_version_where_bump_major_should_issue_next_major(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_EDIT_TAFSIR_CONTENT)
        old = self.make_version("7.0", label="Original")
        baker.make(AssetVersionEntry, version=old, ayah=self.ayah, text="old")
        head = self.make_version("7.1")
        baker.make(AssetVersionEntry, version=head, ayah=self.ayah, text="new")

        # Act
        response = self.client.post(
            f"/portal/content/tafsirs/{self.tafsir.slug}/versions/{old.id}/restore/",
            data={"bump": "major"},
            content_type="application/json",
        )

        # Assert — a new number, the restored version's name
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual("8.0", response.json()["name"])
        self.assertEqual("Original", response.json()["label"])


class NumberVersionsMigrationTest(VersionNumberingBaseTest):
    def test_number_versions_where_run_should_number_per_language_and_keep_old_names_as_labels(self):
        # Arrange — two Arabic commits, one French commit, one draft; old free-text names
        first = self.make_version("v1")
        second = self.make_version("Second edition")
        french = self.make_version("fr v1", language="fr")
        draft = self.make_version("wip", state=VersionStateChoice.DRAFT)
        AssetVersion.objects.filter(pk=second.pk).update(created_at=first.created_at.replace(year=2100))

        # Act
        numbering_migration.number_versions(django_apps, None)

        # Assert
        for version in (first, second, french, draft):
            version.refresh_from_db()
        self.assertEqual(("1.0", "v1"), (first.name, first.label))
        self.assertEqual(("1.1", "Second edition"), (second.name, second.label))
        self.assertEqual(("1.0", "fr v1"), (french.name, french.label))
        self.assertEqual(("", "wip"), (draft.name, draft.label))

    def test_restore_names_where_reversed_should_restore_labels_and_keep_unlabelled_numbers(self):
        # Arrange — a migrated version (old name in its label) and one created after, unnamed
        migrated = self.make_version("1.0", label="v1")
        unnamed = self.make_version("1.1", label="")

        # Act
        numbering_migration.restore_names(django_apps, None)

        # Assert
        migrated.refresh_from_db()
        unnamed.refresh_from_db()
        self.assertEqual("v1", migrated.name)
        self.assertEqual("1.1", unnamed.name)
