import json
from urllib.parse import quote

from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from model_bakery import baker

from apps.content.models import (
    AssetColumn,
    AssetVersion,
    AssetVersionChange,
    AssetVersionChangeReview,
    ReviewStateChoice,
)
from apps.content.tests.portal.test_asset_review import AssetReviewApiBaseTest
from apps.core.permissions import PermissionChoice
from apps.publishers.models import MemberLanguage
from apps.quran.models import Ayah, Surah
from apps.users.models import User


def _filters(model: dict) -> str:
    """The grid's filter model as the `filters` query param."""
    return "filters=" + quote(json.dumps(model))


def _text(kind: str, value: str = "") -> dict:
    return {"filterType": "text", "type": kind, "filter": value}


def _number(kind: str, value: int, value_to: int | None = None) -> dict:
    model = {"filterType": "number", "type": kind, "filter": value}
    if value_to is not None:
        model["filterTo"] = value_to
    return model


class ReviewFiltersTest(AssetReviewApiBaseTest):
    """`self.change` (1:1, added "au nom", v1) plus a modified 2:3 change in v2
    by another author, reviewed with a comment."""

    def setUp(self):
        super().setUp()
        self.surah2 = baker.make(Surah, id=2, name="البقرة", ayahs_count=286)
        self.ayah23 = baker.make(Ayah, id=10, surah=self.surah2, number_in_surah=3, text="c")
        self.author = User.objects.create_user(email="ed@example.com", name="Editor Ed", is_staff=True)
        self.v2 = baker.make(AssetVersion, asset=self.asset, asset_language=self.fr, name="v2", created_by=self.author)
        self.modified = baker.make(
            AssetVersionChange,
            version=self.v2,
            ayah=self.ayah23,
            change_type="modified",
            old_text="ancien texte",
            new_text="الْحَمْدُ لِلَّهِ",
            order=1,
        )
        self.reviewer = User.objects.create_user(email="r2@example.com", name="Reviewer Ray", is_staff=True)
        AssetVersionChangeReview.objects.create(
            change=self.modified,
            state=ReviewStateChoice.COMMENTED,
            comment="fix the spelling",
            reviewed_by=self.reviewer,
            reviewed_at=timezone.now(),
        )

    def _auth_reviewer(self):
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_REVIEW_CONTENT)
        MemberLanguage.objects.create(member=self.membership, language="fr")

    def _list(self, model: dict):
        return self.client.get(self._changes_url(f"?language=fr&{_filters(model)}"))

    def _ids(self, response) -> list[int]:
        return [row["id"] for row in response.json()["results"]]

    def test_list_changes_should_return_the_units_surah_and_ayah_numbers(self):
        # Arrange
        self._auth_reviewer()

        # Act
        response = self.client.get(self._changes_url("?language=fr"))

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        rows = {row["id"]: (row["surah"], row["ayah"]) for row in response.json()["results"]}
        self.assertEqual({self.change.id: (1, 1), self.modified.id: (2, 3)}, rows)

    def test_list_changes_where_unit_surah_filtered_should_return_only_that_surahs_changes(self):
        # Arrange
        self._auth_reviewer()

        # Act
        response = self._list({"unit_surah": _number("equals", 2)})

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual([self.modified.id], self._ids(response))
        self.assertEqual(1, response.json()["count"])

    def test_list_changes_where_ayah_in_range_should_include_both_ends(self):
        # Arrange
        self._auth_reviewer()

        # Act
        response = self._list({"ayah": _number("inRange", 2, 3)})

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual([self.modified.id], self._ids(response))

    def test_list_changes_where_text_filtered_should_match_the_new_text(self):
        # Arrange
        self._auth_reviewer()

        # Act
        response = self._list({"text": _text("contains", "AU NOM")})

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual([self.change.id], self._ids(response))

    def test_list_changes_where_text_filtered_should_match_the_old_text(self):
        # Arrange
        self._auth_reviewer()

        # Act
        response = self._list({"text": _text("contains", "ancien")})

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual([self.modified.id], self._ids(response))

    def test_list_changes_where_text_filtered_without_vocalization_should_match_vocalized_text(self):
        # Arrange
        self._auth_reviewer()

        # Act
        response = self._list({"text": _text("contains", "الحمد")})

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual([self.modified.id], self._ids(response))

    def test_list_changes_where_text_not_contains_should_exclude_a_match_on_either_side(self):
        # Arrange
        self._auth_reviewer()

        # Act
        response = self._list({"text": _text("notContains", "ancien")})

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual([self.change.id], self._ids(response))

    def test_list_changes_where_change_type_filtered_should_return_only_that_type(self):
        # Arrange
        self._auth_reviewer()

        # Act
        response = self._list({"change_type": _text("equals", "modified")})

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual([self.modified.id], self._ids(response))

    def test_list_changes_where_column_filtered_should_return_only_that_columns_changes(self):
        # Arrange
        self._auth_reviewer()
        notes = AssetColumn.objects.create(asset=self.asset, key="notes", order=5)
        in_notes = baker.make(
            AssetVersionChange, version=self.v2, ayah=self.ayah23, column=notes, change_type="added", order=2
        )

        # Act
        response = self._list({"column": _text("equals", "notes")})

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual([in_notes.id], self._ids(response))

    def test_list_changes_where_people_and_comment_filtered_should_match_case_insensitively(self):
        # Arrange
        self._auth_reviewer()
        models = [
            {"edited_by": _text("contains", "editor")},
            {"reviewed_by": _text("startsWith", "reviewer")},
            {"comment": _text("contains", "SPELLING")},
            {"commit_ref": _text("equals", "v2")},
        ]

        # Act
        responses = [self._list(model) for model in models]

        # Assert
        for model, response in zip(models, responses, strict=True):
            self.assertEqual(200, response.status_code, (model, response.content))
            self.assertEqual([self.modified.id], self._ids(response), model)

    def test_list_changes_where_no_reviewer_and_blank_filter_should_match_unreviewed_changes(self):
        # Arrange
        self._auth_reviewer()

        # Act
        response = self._list({"reviewed_by": _text("blank")})

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual([self.change.id], self._ids(response))

    def test_list_changes_where_filters_combined_with_or_should_match_either(self):
        # Arrange
        self._auth_reviewer()
        model = {
            "text": {
                "filterType": "text",
                "operator": "OR",
                "conditions": [_text("contains", "au nom"), _text("contains", "ancien")],
            }
        }

        # Act
        response = self._list(model)

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual({self.change.id, self.modified.id}, set(self._ids(response)))

    def test_list_changes_where_unknown_filter_key_should_return_400(self):
        # Arrange
        self._auth_reviewer()

        # Act
        response = self._list({"label": _text("contains", "x")})

        # Assert
        self.assertEqual(400, response.status_code, response.content)
        self.assertEqual("validation_error", response.json()["error_name"])

    def test_list_changes_where_filtered_should_not_add_queries_per_row(self):
        # Arrange
        self._auth_reviewer()
        for number in range(4, 14):
            ayah = baker.make(Ayah, id=100 + number, surah=self.surah2, number_in_surah=number, text="x")
            baker.make(
                AssetVersionChange, version=self.v2, ayah=ayah, change_type="added", new_text="ancien", order=number
            )
        model = {"text": _text("contains", "ancien"), "unit_surah": _number("equals", 2)}
        with CaptureQueriesContext(connection) as few:
            self._list({"text": _text("contains", "ancien"), "ayah": _number("equals", 3)})

        # Act
        with CaptureQueriesContext(connection) as many:
            response = self._list(model)

        # Assert
        self.assertEqual(11, response.json()["count"])
        self.assertEqual(len(few), len(many))

    def test_bulk_approve_where_filters_given_should_approve_only_the_matching_changes(self):
        # Arrange
        self._auth_reviewer()
        body = {"language": "fr", "filters": {"unit_surah": _number("equals", 1)}}

        # Act
        response = self.client.post(
            f"/portal/content/translations/{self.asset.slug}/review/changes/bulk-approve/",
            data=body,
            content_type="application/json",
        )

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual({"approved": 1}, response.json())
        self.assertEqual(ReviewStateChoice.APPROVED, AssetVersionChangeReview.objects.get(change=self.change).state)
        self.assertEqual(ReviewStateChoice.COMMENTED, AssetVersionChangeReview.objects.get(change=self.modified).state)

    def test_bulk_approve_where_change_ids_and_filters_given_should_return_400(self):
        # Arrange
        self._auth_reviewer()
        body = {"language": "fr", "change_ids": [self.change.id], "filters": {"ayah": _number("equals", 3)}}

        # Act
        response = self.client.post(
            f"/portal/content/translations/{self.asset.slug}/review/changes/bulk-approve/",
            data=body,
            content_type="application/json",
        )

        # Assert
        self.assertEqual(400, response.status_code, response.content)
        self.assertEqual("validation_error", response.json()["error_name"])
