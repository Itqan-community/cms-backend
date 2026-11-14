from datetime import timedelta
import json
from unittest.mock import patch

from django.core.cache import cache
from django.db import connection
from django.test import override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from model_bakery import baker

from apps.content.models import (
    Asset,
    AssetAccess,
    AssetAccessRequest,
    AssetColumn,
    AssetTemplateChoice,
    AssetVersion,
    AssetVersionChange,
    AssetVersionEntry,
    CategoryChoice,
    ChangeTypeChoice,
    StatusChoice,
    VersionStateChoice,
)
from apps.content.tests.group_quran_data import GroupQuranDataMixin
from apps.content.tests.publishing import publish
from apps.content.tests.tagging import tagged
from apps.core.tests.base import BaseTestCase
from apps.publishers.models import Publisher
from apps.usage_tracking.decorators import track_usage as track_usage_module
from apps.usage_tracking.decorators.track_usage import _get_tracking_redis
from apps.users.models import APIKey, User


class AyahTextPublicApiTest(GroupQuranDataMixin, BaseTestCase):
    """``GET /ayahs/{ayah_key}/?assets=``: several text assets' content for one ayah (or range).

    Quran slice (GroupQuranDataMixin): ayahs 1:1, 1:2, 1:3, 2:1, 2:2 (ids 1-5);
    words 1-3 in 1:1, 4-5 in 1:2, 6 in 1:3, 7-8 in 2:1.
    """

    def setUp(self):
        super().setUp()
        cache.clear()
        self.bake_group_quran()
        self.publisher = baker.make(Publisher, name="Publisher")
        self.user = User.objects.create_user(email="dev@example.com", name="Developer")

    # --- fixtures -------------------------------------------------------------

    def _text_asset(
        self,
        slug: str,
        *,
        template: str = AssetTemplateChoice.AYAH,
        columns: tuple[tuple[str, str, str], ...] = (("text", "", ""),),
        is_open_access: bool = True,
        tag: str = "tafsir",
        **fields,
    ) -> Asset:
        defaults = {
            "name_en": f"{slug} en",
            "name_ar": f"{slug} ar",
            "category": CategoryChoice.TEXT,
            "template": template,
            "status": StatusChoice.READY,
            "language": "ar",
            "publisher": self.publisher,
            "is_open_access": is_open_access,
            "in_public_api": True,
        }
        asset = baker.make(Asset, slug=slug, **{**defaults, **fields})
        for order, (key, label_en, label_ar) in enumerate(columns):
            baker.make(AssetColumn, asset=asset, key=key, label_en=label_en, label_ar=label_ar, order=order)
        return tagged(asset, tag)

    def _version(self, asset: Asset, name: str, cells: dict, *, published: bool = True) -> AssetVersion:
        """A committed version holding ``cells``: ``{unit_kwargs_tuple: {column_key: text}}``."""
        rendition = asset.get_or_create_source_language()
        columns = {column.key: column for column in asset.columns.all()}
        version = baker.make(
            AssetVersion,
            asset=asset,
            asset_language=rendition,
            state=VersionStateChoice.PUBLISHED,
            column_keys=list(columns),
            name=name,
        )
        for unit, texts in cells.items():
            for key, text in texts.items():
                AssetVersionEntry.objects.create(version=version, column=columns[key], text=text, **dict(unit))
        return publish(version) if published else version

    def _authenticate_with_api_key(self, user: User) -> None:
        _, raw_key = APIKey.objects.create_key(name="test-key", user=user)
        self.client.credentials(HTTP_X_API_KEY=raw_key)

    def _grant_access(self, user: User, asset: Asset) -> AssetAccess:
        request = baker.make(
            AssetAccessRequest, developer_user=user, asset=asset, status=AssetAccessRequest.StatusChoice.APPROVED
        )
        return baker.make(AssetAccess, asset_access_request=request, user=user, asset=asset, expires_at=None)

    @staticmethod
    def _ayah(ayah_id: int) -> tuple:
        return (("ayah_id", ayah_id),)

    # --- success --------------------------------------------------------------

    def test_get_ayah_text_where_ayah_template_asset_should_return_published_cells_with_column_labels(self):
        # Arrange
        asset = self._text_asset("muyassar", columns=(("text", "Text", "النص"), ("note", "Note", "حاشية")))
        self._version(asset, "1.0", {self._ayah(1): {"text": "tafsir 1:1", "note": "note 1:1"}})

        # Act
        response = self.client.get("/ayahs/1:1/?assets=muyassar")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual("public, max-age=300, s-maxage=300", response.headers.get("Cache-Control"))
        body = response.json()
        self.assertEqual((1, 1, 1), (body["surah_number"], body["from_ayah"], body["to_ayah"]))
        self.assertEqual(1, len(body["assets"]))
        item = body["assets"][0]
        self.assertEqual("muyassar", item["slug"])
        self.assertEqual("muyassar en", item["name_en"])
        self.assertEqual("muyassar ar", item["name_ar"])
        self.assertEqual("text", item["category"])
        self.assertEqual(["tafsir"], item["tags"])
        self.assertEqual("ayah", item["template"])
        self.assertEqual("ar", item["language"])
        self.assertEqual("1.0", item["version"])
        self.assertEqual(
            [
                {"key": "text", "label_en": "Text", "label_ar": "النص"},
                {"key": "note", "label_en": "Note", "label_ar": "حاشية"},
            ],
            item["columns"],
        )
        self.assertEqual(
            [
                {
                    "start": {"ayah_key": "1:1", "word_position": None},
                    "end": {"ayah_key": "1:1", "word_position": None},
                    "cells": {"text": "tafsir 1:1", "note": "note 1:1"},
                }
            ],
            item["rows"],
        )

    def test_get_ayah_text_where_several_assets_should_keep_requested_order_and_accept_both_list_styles(self):
        # Arrange
        tafsir = self._text_asset("tafsir-a")
        translation = self._text_asset("translation-b", tag="translation")
        self._version(tafsir, "1.0", {self._ayah(2): {"text": "tafsir 1:2"}})
        self._version(translation, "2.1", {self._ayah(2): {"text": "translation 1:2"}})

        # Act
        comma = self.client.get("/ayahs/1:2/?assets=translation-b,tafsir-a")
        repeated = self.client.get("/ayahs/1:2/?assets=translation-b&assets=tafsir-a")

        # Assert
        self.assertEqual(200, comma.status_code, comma.content)
        self.assertEqual(comma.json(), repeated.json())
        items = comma.json()["assets"]
        self.assertEqual(["translation-b", "tafsir-a"], [item["slug"] for item in items])
        self.assertEqual(["2.1", "1.0"], [item["version"] for item in items])
        self.assertEqual(["translation"], items[0]["tags"])
        self.assertEqual("translation 1:2", items[0]["rows"][0]["cells"]["text"])

    def test_get_ayah_text_where_duplicate_slugs_should_return_the_asset_once(self):
        # Arrange
        asset = self._text_asset("tafsir-a")
        self._version(asset, "1.0", {self._ayah(1): {"text": "t"}})

        # Act
        response = self.client.get("/ayahs/1:1/?assets=tafsir-a,tafsir-a")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual(1, len(response.json()["assets"]))

    def test_get_ayah_text_where_ayah_has_no_text_should_return_the_asset_with_no_rows(self):
        # Arrange
        asset = self._text_asset("tafsir-a")
        self._version(asset, "1.0", {self._ayah(1): {"text": "only 1:1"}})

        # Act
        response = self.client.get("/ayahs/1:3/?assets=tafsir-a")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual([], response.json()["assets"][0]["rows"])

    def test_get_ayah_text_where_newer_version_is_unpublished_should_serve_the_published_version(self):
        # Arrange
        asset = self._text_asset("tafsir-a")
        self._version(asset, "1.0", {self._ayah(1): {"text": "published"}})
        self._version(asset, "1.1", {self._ayah(1): {"text": "committed, not published"}}, published=False)

        # Act
        response = self.client.get("/ayahs/1:1/?assets=tafsir-a")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        item = response.json()["assets"][0]
        self.assertEqual("1.0", item["version"])
        self.assertEqual("published", item["rows"][0]["cells"]["text"])

    def test_get_ayah_text_where_published_version_kept_only_its_deltas_should_rebuild_its_cells(self):
        # Arrange: v1.0 holds the full snapshot; v1.1 (rolled back to, so published) only its delta.
        asset = self._text_asset("tafsir-a")
        self._version(asset, "1.0", {self._ayah(1): {"text": "old 1:1"}, self._ayah(2): {"text": "kept 1:2"}})
        delta_only = self._version(asset, "1.1", {})
        AssetVersionChange.objects.create(
            version=delta_only,
            column=asset.columns.get(key="text"),
            change_type=ChangeTypeChoice.MODIFIED,
            old_text="old 1:1",
            new_text="new 1:1",
            ayah_id=1,
        )

        # Act
        response = self.client.get("/ayahs/1:1/?assets=tafsir-a&to=2")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        rows = response.json()["assets"][0]["rows"]
        self.assertEqual(["new 1:1", "kept 1:2"], [row["cells"]["text"] for row in rows])

    def test_get_ayah_text_where_ayah_group_asset_should_return_the_group_covering_the_ayah(self):
        # Arrange
        asset = self._text_asset("grouped", template=AssetTemplateChoice.AYAH_GROUP)
        self._version(
            asset,
            "1.0",
            {
                (("from_ayah_id", 1), ("to_ayah_id", 3)): {"text": "group 1:1-1:3"},
                (("from_ayah_id", 4), ("to_ayah_id", 5)): {"text": "group 2:1-2:2"},
            },
        )

        # Act
        response = self.client.get("/ayahs/1:2/?assets=grouped")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual(
            [
                {
                    "start": {"ayah_key": "1:1", "word_position": None},
                    "end": {"ayah_key": "1:3", "word_position": None},
                    "cells": {"text": "group 1:1-1:3"},
                }
            ],
            response.json()["assets"][0]["rows"],
        )

    def test_get_ayah_text_where_word_asset_should_return_one_row_per_word_in_order(self):
        # Arrange
        asset = self._text_asset("words", template=AssetTemplateChoice.WORD, tag="translation")
        self._version(
            asset,
            "1.0",
            {
                (("word_id", 3),): {"text": "w3"},
                (("word_id", 1),): {"text": "w1"},
                (("word_id", 4),): {"text": "w4 (next ayah)"},
            },
        )

        # Act
        response = self.client.get("/ayahs/1:1/?assets=words")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        rows = response.json()["assets"][0]["rows"]
        self.assertEqual(
            [({"ayah_key": "1:1", "word_position": 1}, "w1"), ({"ayah_key": "1:1", "word_position": 3}, "w3")],
            [(row["start"], row["cells"]["text"]) for row in rows],
        )
        self.assertEqual(rows[0]["start"], rows[0]["end"])

    def test_get_ayah_text_where_word_group_spans_two_ayahs_should_return_it_for_each(self):
        # Arrange: words 3-4 run from the last word of 1:1 into the first of 1:2.
        asset = self._text_asset("word-groups", template=AssetTemplateChoice.WORD_GROUP)
        self._version(asset, "1.0", {(("from_word_id", 3), ("to_word_id", 4)): {"text": "spans"}})

        # Act
        first = self.client.get("/ayahs/1:1/?assets=word-groups")
        second = self.client.get("/ayahs/1:2/?assets=word-groups")
        third = self.client.get("/ayahs/1:3/?assets=word-groups")

        # Assert
        expected = [
            {
                "start": {"ayah_key": "1:1", "word_position": 3},
                "end": {"ayah_key": "1:2", "word_position": 1},
                "cells": {"text": "spans"},
            }
        ]
        self.assertEqual(expected, first.json()["assets"][0]["rows"])
        self.assertEqual(expected, second.json()["assets"][0]["rows"])
        self.assertEqual([], third.json()["assets"][0]["rows"])

    def test_get_ayah_text_where_range_given_should_return_rows_for_every_ayah_in_it(self):
        # Arrange
        asset = self._text_asset("tafsir-a")
        self._version(
            asset,
            "1.0",
            {self._ayah(3): {"text": "1:3"}, self._ayah(1): {"text": "1:1"}, self._ayah(4): {"text": "2:1"}},
        )

        # Act
        response = self.client.get("/ayahs/1:1/?assets=tafsir-a&to=3")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual((1, 1, 3), (body["surah_number"], body["from_ayah"], body["to_ayah"]))
        self.assertEqual(["1:1", "1:3"], [row["cells"]["text"] for row in body["assets"][0]["rows"]])

    # --- request validation ---------------------------------------------------

    def test_get_ayah_text_where_no_assets_given_should_return_400_assets_required(self):
        # Act
        response = self.client.get("/ayahs/1:1/")

        # Assert
        self.assertEqual(400, response.status_code, response.content)
        self.assertEqual("assets_required", response.json()["error_name"])

    def test_get_ayah_text_where_too_many_assets_given_should_return_400_too_many_assets(self):
        # Arrange
        slugs = ",".join(f"asset-{i}" for i in range(21))

        # Act
        response = self.client.get(f"/ayahs/1:1/?assets={slugs}")

        # Assert
        self.assertEqual(400, response.status_code, response.content)
        self.assertEqual("too_many_assets", response.json()["error_name"])

    def test_get_ayah_text_where_ayah_key_is_malformed_or_missing_should_return_404_ayah_not_found(self):
        # Arrange
        self._version(self._text_asset("tafsir-a"), "1.0", {self._ayah(1): {"text": "t"}})

        for key in ("1-1", "x:1", "1:9", "115:1", "0:1"):
            # Act
            response = self.client.get(f"/ayahs/{key}/?assets=tafsir-a")

            # Assert
            self.assertEqual(404, response.status_code, (key, response.content))
            self.assertEqual("ayah_not_found", response.json()["error_name"])

    def test_get_ayah_text_where_range_is_invalid_should_return_400_invalid_ayah_range(self):
        # Arrange
        self._version(self._text_asset("tafsir-a"), "1.0", {self._ayah(1): {"text": "t"}})

        for query in ("to=1", "to=9"):  # before the start; past the surah's last ayah
            # Act
            response = self.client.get(f"/ayahs/1:2/?assets=tafsir-a&{query}")

            # Assert
            self.assertEqual(400, response.status_code, (query, response.content))
            self.assertEqual("invalid_ayah_range", response.json()["error_name"])

    def test_get_ayah_text_where_range_is_too_long_should_return_400_invalid_ayah_range(self):
        # Arrange
        self._version(self._text_asset("tafsir-a"), "1.0", {self._ayah(1): {"text": "t"}})

        # Act
        response = self.client.get("/ayahs/1:1/?assets=tafsir-a&to=51")

        # Assert
        self.assertEqual(400, response.status_code, response.content)
        self.assertEqual("invalid_ayah_range", response.json()["error_name"])

    # --- asset validation -----------------------------------------------------

    def test_get_ayah_text_where_slug_is_unknown_should_return_404_asset_not_found_naming_it(self):
        # Arrange
        self._version(self._text_asset("tafsir-a"), "1.0", {self._ayah(1): {"text": "t"}})

        # Act
        response = self.client.get("/ayahs/1:1/?assets=tafsir-a,nope,missing")

        # Assert
        self.assertEqual(404, response.status_code, response.content)
        body = response.json()
        self.assertEqual("asset_not_found", body["error_name"])
        self.assertEqual({"assets": ["nope", "missing"]}, body["extra"])

    def test_get_ayah_text_where_asset_is_not_served_to_consumers_should_return_404_asset_not_found(self):
        # Arrange
        off_channel = self._text_asset("off-channel", in_public_api=False)
        self._version(off_channel, "1.0", {self._ayah(1): {"text": "t"}})
        draft = self._text_asset("draft", status=StatusChoice.DRAFT)
        self._version(draft, "1.0", {self._ayah(1): {"text": "t"}})
        unpublished = self._text_asset("unpublished")
        self._version(unpublished, "1.0", {self._ayah(1): {"text": "t"}}, published=False)
        hidden = self._text_asset("hidden-language")
        self._version(hidden, "1.0", {self._ayah(1): {"text": "t"}})
        hidden.languages.update(status=StatusChoice.DRAFT)

        for slug in ("off-channel", "draft", "unpublished", "hidden-language"):
            # Act
            response = self.client.get(f"/ayahs/1:1/?assets={slug}")

            # Assert
            self.assertEqual(404, response.status_code, (slug, response.content))
            self.assertEqual("asset_not_found", response.json()["error_name"])

    def test_get_ayah_text_where_asset_is_not_text_should_return_400_asset_not_text(self):
        # Arrange
        baker.make(
            Asset,
            slug="a-mushaf",
            category=CategoryChoice.MUSHAF,
            status=StatusChoice.READY,
            publisher=self.publisher,
            in_public_api=True,
        )
        self._version(self._text_asset("tafsir-a"), "1.0", {self._ayah(1): {"text": "t"}})

        # Act
        response = self.client.get("/ayahs/1:1/?assets=tafsir-a,a-mushaf")

        # Assert
        self.assertEqual(400, response.status_code, response.content)
        body = response.json()
        self.assertEqual("asset_not_text", body["error_name"])
        self.assertEqual({"assets": ["a-mushaf"]}, body["extra"])

    def test_get_ayah_text_where_asset_is_surah_based_should_return_400_asset_not_ayah_based(self):
        # Arrange
        asset = self._text_asset("surah-intros", template=AssetTemplateChoice.SURAH)
        self._version(asset, "1.0", {(("surah_id", 1),): {"text": "intro"}})

        # Act
        response = self.client.get("/ayahs/1:1/?assets=surah-intros")

        # Assert
        self.assertEqual(400, response.status_code, response.content)
        body = response.json()
        self.assertEqual("asset_not_ayah_based", body["error_name"])
        self.assertEqual({"assets": ["surah-intros"]}, body["extra"])

    # --- access ---------------------------------------------------------------

    @override_settings(ENFORCE_ASSET_ACCESS_ON_PUBLIC_API=True)
    def test_get_ayah_text_where_restricted_asset_and_no_api_key_should_return_401_authentication_required(self):
        # Arrange
        restricted = self._text_asset("restricted", is_open_access=False)
        self._version(restricted, "1.0", {self._ayah(1): {"text": "t"}})

        # Act
        response = self.client.get("/ayahs/1:1/?assets=restricted")

        # Assert
        self.assertEqual(401, response.status_code, response.content)
        self.assertEqual("authentication_required", response.json()["error_name"])

    @override_settings(ENFORCE_ASSET_ACCESS_ON_PUBLIC_API=True)
    def test_get_ayah_text_where_api_key_lacks_approved_access_should_return_403_access_denied_naming_assets(self):
        # Arrange
        granted = self._text_asset("granted", is_open_access=False)
        self._version(granted, "1.0", {self._ayah(1): {"text": "t"}})
        denied = self._text_asset("denied", is_open_access=False)
        self._version(denied, "1.0", {self._ayah(1): {"text": "t"}})
        self._grant_access(self.user, granted)
        baker.make(
            AssetAccessRequest,
            developer_user=self.user,
            asset=denied,
            status=AssetAccessRequest.StatusChoice.PENDING,
        )
        self._authenticate_with_api_key(self.user)

        # Act
        response = self.client.get("/ayahs/1:1/?assets=granted,denied")

        # Assert
        self.assertEqual(403, response.status_code, response.content)
        body = response.json()
        self.assertEqual("access_denied", body["error_name"])
        self.assertEqual({"assets": ["denied"]}, body["extra"])

    @override_settings(ENFORCE_ASSET_ACCESS_ON_PUBLIC_API=True)
    def test_get_ayah_text_where_access_grant_expired_should_return_403_access_denied(self):
        # Arrange
        restricted = self._text_asset("restricted", is_open_access=False)
        self._version(restricted, "1.0", {self._ayah(1): {"text": "secret"}})
        access = self._grant_access(self.user, restricted)
        access.expires_at = timezone.now() - timedelta(days=1)
        access.save(update_fields=["expires_at"])
        self._authenticate_with_api_key(self.user)

        # Act
        response = self.client.get("/ayahs/1:1/?assets=restricted")

        # Assert
        self.assertEqual(403, response.status_code, response.content)
        self.assertEqual("access_denied", response.json()["error_name"])

    @override_settings(ENFORCE_ASSET_ACCESS_ON_PUBLIC_API=True)
    def test_get_ayah_text_where_api_key_has_approved_access_should_return_200_privately_cached(self):
        # Arrange
        restricted = self._text_asset("restricted", is_open_access=False)
        self._version(restricted, "1.0", {self._ayah(1): {"text": "secret"}})
        open_asset = self._text_asset("open")
        self._version(open_asset, "1.0", {self._ayah(1): {"text": "open"}})
        self._grant_access(self.user, restricted)
        self._authenticate_with_api_key(self.user)

        # Act
        response = self.client.get("/ayahs/1:1/?assets=open,restricted")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual("private, no-cache", response.headers.get("Cache-Control"))
        self.assertEqual("secret", response.json()["assets"][1]["rows"][0]["cells"]["text"])

    @override_settings(ENFORCE_ASSET_ACCESS_ON_PUBLIC_API=True)
    def test_get_ayah_text_where_cached_response_and_access_revoked_should_return_403_access_denied(self):
        # Arrange: warm the cache with access, then revoke it.
        restricted = self._text_asset("restricted", is_open_access=False)
        self._version(restricted, "1.0", {self._ayah(1): {"text": "secret"}})
        access = self._grant_access(self.user, restricted)
        self._authenticate_with_api_key(self.user)
        self.assertEqual(200, self.client.get("/ayahs/1:1/?assets=restricted").status_code)
        access.delete()

        # Act
        response = self.client.get("/ayahs/1:1/?assets=restricted")

        # Assert
        self.assertEqual(403, response.status_code, response.content)
        self.assertEqual("access_denied", response.json()["error_name"])

    # --- performance ----------------------------------------------------------

    def _bake_mixed_assets(self, count: int) -> list[str]:
        templates = [
            AssetTemplateChoice.AYAH,
            AssetTemplateChoice.AYAH_GROUP,
            AssetTemplateChoice.WORD,
            AssetTemplateChoice.WORD_GROUP,
        ]
        units = {
            AssetTemplateChoice.AYAH: (("ayah_id", 1),),
            AssetTemplateChoice.AYAH_GROUP: (("from_ayah_id", 1), ("to_ayah_id", 2)),
            AssetTemplateChoice.WORD: (("word_id", 2),),
            AssetTemplateChoice.WORD_GROUP: (("from_word_id", 3), ("to_word_id", 4)),
        }
        slugs = []
        for index in range(count):
            template = templates[index % len(templates)]
            slug = f"perf-{count}-{index}"
            asset = self._text_asset(slug, template=template, is_open_access=index % 2 == 0)
            self._version(asset, "1.0", {units[template]: {"text": slug}})
            self._grant_access(self.user, asset)
            slugs.append(slug)
        return slugs

    @override_settings(ENFORCE_ASSET_ACCESS_ON_PUBLIC_API=True)
    def test_get_ayah_text_where_more_assets_requested_should_run_the_same_number_of_queries(self):
        # Arrange
        few = self._bake_mixed_assets(4)
        many = self._bake_mixed_assets(12)
        self._authenticate_with_api_key(self.user)
        self.client.get(f"/ayahs/2:1/?assets={few[0]}")  # warm the per-key app lookup the middleware caches

        # Act
        with CaptureQueriesContext(connection) as few_queries:
            few_response = self.client.get(f"/ayahs/1:1/?assets={','.join(few)}")
        with CaptureQueriesContext(connection) as many_queries:
            many_response = self.client.get(f"/ayahs/1:1/?assets={','.join(many)}")

        # Assert
        self.assertEqual(200, few_response.status_code, few_response.content)
        self.assertEqual(200, many_response.status_code, many_response.content)
        self.assertEqual(12, len(many_response.json()["assets"]))
        self.assertTrue(all(item["rows"] for item in many_response.json()["assets"]))
        self.assertEqual(len(few_queries), len(many_queries))

    def test_get_ayah_text_where_open_assets_response_is_cached_should_run_no_queries(self):
        # Arrange
        asset = self._text_asset("tafsir-a")
        self._version(asset, "1.0", {self._ayah(1): {"text": "t"}})
        first = self.client.get("/ayahs/1:1/?assets=tafsir-a")

        # Act
        with CaptureQueriesContext(connection) as queries:
            second = self.client.get("/ayahs/1:1/?assets=tafsir-a")

        # Assert
        self.assertEqual(first.content, second.content)
        self.assertEqual(0, len(queries), [query["sql"] for query in queries.captured_queries])

    # --- usage ----------------------------------------------------------------

    def test_get_ayah_text_where_served_should_record_usage_for_every_asset(self):
        # Arrange
        first = self._text_asset("tafsir-a")
        second = self._text_asset("translation-b", tag="translation")
        self._version(first, "1.0", {self._ayah(1): {"text": "t"}})
        self._version(second, "1.0", {self._ayah(1): {"text": "t"}})

        for attempt in ("cold", "warm"):
            with patch.object(track_usage_module, _get_tracking_redis.__name__) as get_redis:
                # Act
                response = self.client.get("/ayahs/1:1/?assets=tafsir-a,translation-b")

                # Assert
                self.assertEqual(200, response.status_code, response.content)
                props = json.loads(get_redis.return_value.rpush.call_args[0][1])["properties"]
                self.assertEqual("text", props["entity_type"], attempt)
                self.assertEqual([first.id, second.id], props["entity_ids"], attempt)
                self.assertEqual(["tafsir-a ar", "translation-b ar"], props["entity_names"], attempt)
                self.assertEqual([self.publisher.id], props["publisher_ids"], attempt)
                self.assertEqual("1:1", props["ayah_key"], attempt)
