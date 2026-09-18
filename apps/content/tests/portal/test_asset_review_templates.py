from model_bakery import baker

from apps.content.models import (
    Asset,
    AssetTemplateChoice,
    AssetVersion,
    AssetVersionChange,
    CategoryChoice,
    ChangeTypeChoice,
    MushafLayout,
    StatusChoice,
)
from apps.content.tests.quran_data import QuranDataMixin
from apps.core.permissions import PermissionChoice
from apps.core.tests.base import BaseTestCase
from apps.users.models import User


class ReviewTemplateTests(QuranDataMixin, BaseTestCase):
    """Every unit kind must render on the review surface without raising.

    Before Task 7A, ``ReviewChangeOut`` resolved ``obj.ayah.sura_id`` /
    ``obj.ayah.number_in_sura`` / ``obj.ayah.sura.name`` unconditionally, so a
    surah/word/page change row (``ayah`` is null on those) raised
    ``AttributeError`` -> a 500. See the surah test below, which is the one
    recorded (pre-fix) as failing with exactly that error.
    """

    def setUp(self):
        super().setUp()
        self.bake_quran()
        self.user = User.objects.create_user(email="reviewer@example.com", name="Reviewer", is_staff=True)

    def _draft_for(
        self, template: AssetTemplateChoice, layout: MushafLayout | None = None
    ) -> tuple[Asset, AssetVersion]:
        asset = baker.make(
            Asset,
            category=CategoryChoice.TRANSLATION,
            status=StatusChoice.READY,
            template=template,
            language="en",
            mushaf_layout=layout,
        )
        version = baker.make(AssetVersion, asset=asset)
        return asset, version

    def _changes_url(self, asset: Asset) -> str:
        return f"/portal/content/translations/{asset.slug}/review/changes/?language=en"

    def _authenticate_reviewer(self) -> None:
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_REVIEW_CONTENT)
        self.give_permission(self.user, PermissionChoice.PORTAL_ACCESS_ALL_LANGUAGES)

    def test_review_changes_where_surah_template_should_not_raise_and_should_label_the_unit(self):
        # Arrange — QuranDataMixin bakes sura 2 with transliterated_name "Al-Baqara"
        self._authenticate_reviewer()
        asset, version = self._draft_for(AssetTemplateChoice.SURAH)
        AssetVersionChange.objects.create(
            version=version,
            sura_id=self.sura2.id,
            change_type=ChangeTypeChoice.ADDED,
            old_text="",
            new_text="cow",
            order=2,
        )

        # Act
        response = self.client.get(self._changes_url(asset))

        # Assert
        self.assertEqual(response.status_code, 200, response.content)
        row = response.json()["results"][0]
        self.assertEqual(row["unit_type"], "surah")
        self.assertEqual(row["unit_id"], self.sura2.id)
        self.assertEqual(row["label"], "2. Al-Baqara")

    def test_review_changes_where_ayah_template_should_keep_the_colon_label(self):
        # Arrange — ayah1 is sura 1, number_in_sura 1 (see QuranDataMixin)
        self._authenticate_reviewer()
        asset, version = self._draft_for(AssetTemplateChoice.AYAH)
        AssetVersionChange.objects.create(
            version=version,
            ayah_id=self.ayah1.id,
            change_type=ChangeTypeChoice.ADDED,
            old_text="",
            new_text="bismillah",
            order=1,
        )

        # Act
        response = self.client.get(self._changes_url(asset))

        # Assert
        self.assertEqual(response.status_code, 200, response.content)
        row = response.json()["results"][0]
        self.assertEqual(row["unit_type"], "ayah")
        self.assertEqual(row["unit_id"], self.ayah1.id)
        self.assertEqual(row["label"], "1:1")

    def test_review_changes_where_word_template_should_include_sura_ayah_and_position_in_the_label(self):
        # Arrange — word1 is sura 1, ayah 1 (number_in_sura 1), position_in_ayah 1
        self._authenticate_reviewer()
        asset, version = self._draft_for(AssetTemplateChoice.WORD)
        AssetVersionChange.objects.create(
            version=version,
            word_id=self.word1.id,
            change_type=ChangeTypeChoice.ADDED,
            old_text="",
            new_text="w1-new",
            order=1,
        )

        # Act
        response = self.client.get(self._changes_url(asset))

        # Assert
        self.assertEqual(response.status_code, 200, response.content)
        row = response.json()["results"][0]
        self.assertEqual(row["unit_type"], "word")
        self.assertEqual(row["unit_id"], self.word1.id)
        self.assertEqual(row["label"], "1:1:1")

    def test_review_changes_where_page_template_should_use_the_translated_page_label(self):
        # Arrange — page has no FK at all, a genuinely different code path
        self._authenticate_reviewer()
        layout = baker.make(MushafLayout, name="Madani 604", page_count=604)
        asset, version = self._draft_for(AssetTemplateChoice.PAGE, layout=layout)
        AssetVersionChange.objects.create(
            version=version,
            page_no=5,
            change_type=ChangeTypeChoice.ADDED,
            old_text="",
            new_text="page 5 text",
            order=5,
        )

        # Act
        response = self.client.get(self._changes_url(asset))

        # Assert
        self.assertEqual(response.status_code, 200, response.content)
        row = response.json()["results"][0]
        self.assertEqual(row["unit_type"], "page")
        self.assertEqual(row["unit_id"], 5)
        self.assertEqual(row["label"], "Page 5")
