import importlib

from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
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
split_migration = importlib.import_module("apps.content.migrations.0074_split_version_label_summary_by_script")

CSV = b"surah,ayah,text\n1,1,in the name"
TEXT = {
    "label_en": "First edition",
    "label_ar": "الطبعة الأولى",
    "summary_en": "Initial release",
    "summary_ar": "الإصدار الأول",
}


class VersionTextBaseTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.publisher = baker.make(Publisher, name="Test Publisher")
        self.translation = baker.make(
            Asset,
            category=CategoryChoice.TRANSLATION,
            template=AssetTemplateChoice.AYAH,
            publisher=self.publisher,
            status=StatusChoice.READY,
            name="Sahih",
            slug="sahih",
            language="ar",
        )
        self.user = User.objects.create_user(email="editor@example.com", name="Editor", is_staff=True)
        self.give_permission(self.user, PermissionChoice.PORTAL_ACCESS_ALL_LANGUAGES)
        sura = baker.make(Sura, id=1, name="الفاتحة", ayas_count=7)
        self.ayah = baker.make(Ayah, id=1, sura=sura, number_in_sura=1, text="a")

    def _versions_url(self, suffix=""):
        return f"/portal/translations/{self.translation.slug}/versions/{suffix}"

    def _make_version(self, name="1.0", **kwargs) -> AssetVersion:
        return baker.make(
            AssetVersion,
            asset=self.translation,
            name=name,
            state=kwargs.pop("state", VersionStateChoice.PUBLISHED),
            **kwargs,
        )


class VersionTextApiTest(VersionTextBaseTest):
    def test_create_version_where_both_languages_given_should_store_and_return_both(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_EDIT_TRANSLATION_CONTENT)
        file = SimpleUploadedFile("t.csv", CSV, content_type="text/csv")

        # Act
        response = self.client.post(
            self._versions_url(),
            data={"asset_id": self.translation.id, "version_number": "1.0", "file": file, **TEXT},
        )

        # Assert
        self.assertEqual(201, response.status_code, response.content)
        body = response.json()
        self.assertEqual(TEXT, {key: body[key] for key in TEXT})
        version = AssetVersion.objects.get(pk=body["id"])
        self.assertEqual(TEXT, {key: getattr(version, key) for key in TEXT})

    def test_patch_version_where_one_language_sent_should_keep_the_other(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_UPDATE_TRANSLATION)
        version = self._make_version(**TEXT)

        # Act
        response = self.client.patch(
            self._versions_url(f"{version.id}/"),
            data="summary_ar=ملخص جديد",
            content_type="application/x-www-form-urlencoded; charset=utf-8",
        )

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        version.refresh_from_db()
        self.assertEqual(("ملخص جديد", "Initial release"), (version.summary_ar, version.summary_en))

    def test_list_versions_where_only_one_language_set_should_return_empty_for_the_other(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_READ_TRANSLATION)
        self._make_version(label_ar="نسخة", summary_ar="ملخص")

        # Act
        response = self.client.get(self._versions_url())

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        row = response.json()["results"][0]
        self.assertEqual(
            ("", "نسخة", "", "ملخص"), (row["label_en"], row["label_ar"], row["summary_en"], row["summary_ar"])
        )

    def test_list_versions_where_searching_arabic_summary_should_find_it(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_READ_TRANSLATION)
        found = self._make_version(summary_ar="تصحيح الأخطاء")
        self._make_version(name="1.1", summary_en="Unrelated")

        # Act
        response = self.client.get(self._versions_url(), data={"search": "تصحيح"})

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual([found.id], [row["id"] for row in response.json()["results"]])

    def test_create_translation_where_version_text_given_should_store_it_on_the_first_version(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_CREATE_TRANSLATION)

        # Act
        response = self.client.post(
            "/portal/translations/",
            data={
                "name_en": "New Translation",
                "license": "CC-BY",
                "language": "ar",
                "publisher_id": self.publisher.id,
                "template": "ayah",
                "version_number": "1.0",
                "version_label_en": "First edition",
                "version_label_ar": "الطبعة الأولى",
                "version_summary_ar": "الإصدار الأول",
                "file": SimpleUploadedFile("t.csv", CSV, content_type="text/csv"),
            },
        )

        # Assert
        self.assertEqual(201, response.status_code, response.content)
        version = AssetVersion.objects.get(asset_id=response.json()["id"])
        self.assertEqual(
            ("First edition", "الطبعة الأولى", "", "الإصدار الأول"),
            (version.label_en, version.label_ar, version.summary_en, version.summary_ar),
        )

    def test_add_language_where_version_label_given_should_name_its_first_version(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_READ_TRANSLATION)
        self.give_permission(self.user, PermissionChoice.PORTAL_ADD_ASSET_LANGUAGE)

        # Act
        response = self.client.post(
            f"/portal/content/translations/{self.translation.slug}/languages/",
            data={
                "language": "fr",
                "file": SimpleUploadedFile("fr.csv", CSV, content_type="text/csv"),
                "version_label_en": "French",
                "version_label_ar": "الفرنسية",
                "version_number": "1.0",
            },
        )

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        version = AssetVersion.objects.get(asset=self.translation, asset_language__language="fr")
        self.assertEqual(("French", "الفرنسية"), (version.label_en, version.label_ar))


class VersionTextDraftTest(VersionTextBaseTest):
    def _draft(self) -> AssetVersion:
        source = AssetLanguage.objects.get_or_create(
            asset=self.translation, language="ar", defaults={"is_source": True}
        )[0]
        draft = self._make_version("", asset_language=source, state=VersionStateChoice.DRAFT, content_edited=True)
        baker.make(AssetVersionEntry, version=draft, ayah=self.ayah, text="edited")
        return draft

    def _commit(self, draft: AssetVersion, **data):
        return self.client.post(
            f"/portal/content/translations/{self.translation.slug}/versions/{draft.id}/publish/",
            data={"version_number": "1.0", **data},
            content_type="application/json",
        )

    def test_get_or_create_draft_where_published_exists_should_carry_both_languages(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_EDIT_TRANSLATION_CONTENT)
        self._make_version(**TEXT)

        # Act
        response = self.client.post(
            f"/portal/content/translations/{self.translation.slug}/draft/",
            data={"language": "ar"},
            content_type="application/json",
        )

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual(TEXT, {key: body[key] for key in TEXT})

    def test_publish_draft_where_only_arabic_summary_should_commit_it(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_EDIT_TRANSLATION_CONTENT)
        draft = self._draft()

        # Act
        response = self._commit(draft, summary_ar="تعديل الآية", label_ar="مراجعة")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        draft.refresh_from_db()
        self.assertEqual(
            (VersionStateChoice.PUBLISHED, "تعديل الآية", "", "مراجعة"),
            (draft.state, draft.summary_ar, draft.summary_en, draft.label_ar),
        )

    def test_publish_draft_where_no_summary_in_either_language_should_return_400(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_EDIT_TRANSLATION_CONTENT)
        draft = self._draft()

        # Act
        response = self._commit(draft, summary_en=" ", summary_ar="")

        # Assert
        self.assertEqual(400, response.status_code, response.content)
        self.assertEqual("commit_message_required", response.json()["error_name"])

    def test_restore_version_should_copy_both_languages(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_EDIT_TRANSLATION_CONTENT)
        old = self._make_version("1.0", **TEXT)
        baker.make(AssetVersionEntry, version=old, ayah=self.ayah, text="old")
        head = self._make_version("1.1")
        baker.make(AssetVersionEntry, version=head, ayah=self.ayah, text="new")

        # Act
        response = self.client.post(
            f"/portal/content/translations/{self.translation.slug}/versions/{old.id}/restore/",
            data={},
            content_type="application/json",
        )

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        restored = AssetVersion.objects.get(pk=response.json()["id"])
        self.assertEqual(TEXT, {key: getattr(restored, key) for key in TEXT})


class VersionTextHistoryTest(VersionTextBaseTest):
    def test_version_history_should_record_both_languages(self):
        # Arrange
        version = self._make_version(**TEXT)

        # Act
        version.summary_ar = "ملخص معدل"
        version.save()

        # Assert
        latest = version.history.order_by("-history_date").first()
        self.assertEqual(("ملخص معدل", "Initial release"), (latest.summary_ar, latest.summary_en))


class SplitByScriptMigrationTest(VersionTextBaseTest):
    def test_split_by_script_should_move_text_into_the_language_it_is_written_in(self):
        # Arrange — models as of the migration before the split, which see the single
        # label/summary columns as plain fields (no modeltranslation rewriting).
        state_apps = (
            MigrationExecutor(connection)
            .loader.project_state(("content", "0073_assetversion_bilingual_label_summary"))
            .apps
        )
        HistoricVersion = state_apps.get_model("content", "AssetVersion")
        arabic = self._make_version("1.0")
        english = self._make_version("1.1")
        HistoricVersion.objects.filter(pk=arabic.pk).update(label="الطبعة الأولى", summary="Fixes in سورة")
        HistoricVersion.objects.filter(pk=english.pk).update(label="v2", summary="تصحيح الأخطاء typo")

        # Act
        split_migration.split_by_script(state_apps, None)

        # Assert — mostly Arabic letters → _ar; anything else → _en
        arabic.refresh_from_db()
        english.refresh_from_db()
        self.assertEqual(
            ("", "الطبعة الأولى", "Fixes in سورة", ""),
            (arabic.label_en, arabic.label_ar, arabic.summary_en, arabic.summary_ar),
        )
        self.assertEqual(
            ("v2", "", "", "تصحيح الأخطاء typo"),
            (english.label_en, english.label_ar, english.summary_en, english.summary_ar),
        )
