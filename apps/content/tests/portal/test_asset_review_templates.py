from datetime import timedelta

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
    MushafLayout,
    ReviewStateChoice,
    StatusChoice,
)
from apps.content.tests.quran_data import QuranDataMixin
from apps.core.permissions import PermissionChoice
from apps.core.tests.base import BaseTestCase
from apps.quran.models import Sura
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


class ReviewDedupAndBaselineTests(QuranDataMixin, BaseTestCase):
    """The dedup ("latest change per unit") and baseline ("last approved text")
    logic in ``AssetReviewRepository.changes_for`` used to key on ``ayah_id``
    alone. Every non-ayah row has ``ayah_id IS NULL``, which is a defect, not
    merely an ayah-only feature, for two independent reasons:

    - Postgres ``DISTINCT ON (ayah_id)`` collapses ALL non-ayah rows (they
      share the same NULL key) into a single surviving row, so editing ten
      surahs would show the reviewer only one.
    - The correlated baseline subquery filters ``ayah_id = OuterRef("ayah_id")``,
      which in SQL is ``NULL = NULL`` -> NULL -> never true, so ``baseline_text``
      was always empty for non-ayah changes regardless of review history.
    """

    def setUp(self):
        super().setUp()
        self.bake_quran()
        self.user = User.objects.create_user(email="reviewer2@example.com", name="Reviewer", is_staff=True)

    def _draft_for(self, template: AssetTemplateChoice) -> tuple[Asset, AssetVersion]:
        asset = baker.make(
            Asset,
            category=CategoryChoice.TRANSLATION,
            status=StatusChoice.READY,
            template=template,
            language="en",
        )
        version = baker.make(AssetVersion, asset=asset)
        return asset, version

    def _changes_url(self, asset: Asset) -> str:
        return f"/portal/content/translations/{asset.slug}/review/changes/?language=en"

    def _authenticate_reviewer(self) -> None:
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_REVIEW_CONTENT)
        self.give_permission(self.user, PermissionChoice.PORTAL_ACCESS_ALL_LANGUAGES)

    def test_review_changes_where_multiple_surah_changes_should_return_all_units_not_just_one(self):
        # Arrange — three DIFFERENT suras changed in the same asset/version.
        # QuranDataMixin only bakes 2 suras, so bake a third explicitly.
        self._authenticate_reviewer()
        sura3 = baker.make(
            Sura,
            id=3,
            name="آل عمران",
            transliterated_name="Aal-E-Imran",
            english_name="The Family of Imran",
            ayas_count=1,
            start_offset=3,
            revelation_type="Medinan",
            revelation_order=89,
            rukus_count=1,
        )
        asset, version = self._draft_for(AssetTemplateChoice.SURAH)
        for sura in (self.sura1, self.sura2, sura3):
            AssetVersionChange.objects.create(
                version=version,
                sura_id=sura.id,
                change_type=ChangeTypeChoice.ADDED,
                old_text="",
                new_text=f"text-{sura.id}",
                order=sura.id,
            )

        # Act
        response = self.client.get(self._changes_url(asset))

        # Assert — all three surah changes are visible, not collapsed to one
        self.assertEqual(response.status_code, 200, response.content)
        results = response.json()["results"]
        self.assertEqual(len(results), 3)
        self.assertEqual({row["unit_id"] for row in results}, {self.sura1.id, self.sura2.id, sura3.id})
        self.assertEqual(
            {row["label"] for row in results},
            {"1. Al-Fatiha", "2. Al-Baqara", "3. Aal-E-Imran"},
        )

    def test_review_changes_where_surah_change_has_earlier_approved_change_should_resolve_baseline_text(self):
        # Arrange — v1's surah 2 change is approved (the last-approved text); a
        # newer commit (v2) then modifies the same surah again.
        self._authenticate_reviewer()
        asset, v1 = self._draft_for(AssetTemplateChoice.SURAH)
        change1 = AssetVersionChange.objects.create(
            version=v1,
            sura_id=self.sura2.id,
            change_type=ChangeTypeChoice.ADDED,
            old_text="",
            new_text="approved cow",
            order=self.sura2.id,
        )
        AssetVersionChangeReview.objects.create(
            change=change1, state=ReviewStateChoice.APPROVED, reviewed_by=self.user, reviewed_at=timezone.now()
        )
        v2 = baker.make(AssetVersion, asset=asset)
        AssetVersion.objects.filter(pk=v2.pk).update(created_at=timezone.now() + timedelta(hours=1))
        AssetVersionChange.objects.create(
            version=v2,
            sura_id=self.sura2.id,
            change_type=ChangeTypeChoice.MODIFIED,
            old_text="approved cow",
            new_text="revised cow",
            order=self.sura2.id,
        )

        # Act
        response = self.client.get(self._changes_url(asset))

        # Assert — only the latest change is reviewable, and its baseline is the
        # last-approved text, not empty
        self.assertEqual(response.status_code, 200, response.content)
        results = response.json()["results"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["new_text"], "revised cow")
        self.assertEqual(results[0]["baseline_text"], "approved cow")

    def test_review_changes_where_ayah_template_has_multiple_versions_should_dedup_and_baseline_like_before(self):
        # Arrange — the long-standing ayah behaviour (mirrors
        # apps/content/tests/services/test_asset_review.py::
        # AssetReviewServiceTest.test_list_changes_shows_only_latest_change_per_ayah_with_last_approved_baseline)
        # exercised through the HTTP endpoint, to prove generalising the dedup/
        # baseline logic to all four templates did not regress the ayah path.
        self._authenticate_reviewer()
        asset, v1 = self._draft_for(AssetTemplateChoice.AYAH)
        change1 = AssetVersionChange.objects.create(
            version=v1,
            ayah_id=self.ayah1.id,
            change_type=ChangeTypeChoice.ADDED,
            old_text="",
            new_text="au nom",
            order=self.ayah1.id,
        )
        AssetVersionChangeReview.objects.create(
            change=change1, state=ReviewStateChoice.APPROVED, reviewed_by=self.user, reviewed_at=timezone.now()
        )
        v2 = baker.make(AssetVersion, asset=asset)
        AssetVersion.objects.filter(pk=v2.pk).update(created_at=timezone.now() + timedelta(hours=1))
        change2 = AssetVersionChange.objects.create(
            version=v2,
            ayah_id=self.ayah1.id,
            change_type=ChangeTypeChoice.MODIFIED,
            old_text="au nom",
            new_text="révisé",
            order=self.ayah1.id,
        )

        # Act
        response = self.client.get(self._changes_url(asset))

        # Assert — only the newer change (change2) is reviewable, with baseline
        # equal to the approved text of change1
        self.assertEqual(response.status_code, 200, response.content)
        results = response.json()["results"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["id"], change2.id)
        self.assertEqual(results[0]["new_text"], "révisé")
        self.assertEqual(results[0]["baseline_text"], "au nom")
