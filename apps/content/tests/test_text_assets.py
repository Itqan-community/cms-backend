"""Text assets: tafsirs and translations merged into one category that carries tags."""

import importlib

from django.apps import apps as django_apps
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.db import connection
from django.test.utils import CaptureQueriesContext
from model_bakery import baker
from plain_permissions.models import Permission as CustomPermission

from apps.content.models import (
    Asset,
    AssetTag,
    AssetTemplateChoice,
    AssetVersion,
    CategoryChoice,
    StatusChoice,
)
from apps.content.services.recommendations import _score_pairs, _visible_asset_values
from apps.content.tests.publishing import make_visible, publish
from apps.content.tests.tagging import tagged
from apps.core.permissions import PermissionChoice
from apps.core.tests.base import BaseTestCase
from apps.publishers.models import Publisher
from apps.users.models import User

# The module name starts with a digit, so a plain `from ... import` is illegal.
migration = importlib.import_module("apps.content.migrations.0015_text_assets")


def _text_asset(*tags: str, **fields) -> Asset:
    defaults = {"category": CategoryChoice.TEXT, "template": AssetTemplateChoice.AYAH, "status": StatusChoice.READY}
    return tagged(baker.make(Asset, **(defaults | fields)), *tags)


class TextAssetMigrationTests(BaseTestCase):
    def test_merge_categories_where_tafsir_and_translation_exist_should_become_text_with_their_tag(self):
        # Arrange: pre-merge rows, which the current check constraint would reject. The
        # migration drops it before merging; the test transaction restores it afterwards.
        constraint = next(c for c in Asset._meta.constraints if c.name == "asset_template_required_for_text")
        with connection.schema_editor() as editor:
            editor.remove_constraint(Asset, constraint)
        tafsir = baker.make(Asset, category="tafsir", template=AssetTemplateChoice.AYAH)
        translation = baker.make(Asset, category="translation", template=AssetTemplateChoice.AYAH)
        mushaf = baker.make(Asset, category=CategoryChoice.MUSHAF)

        # Act
        migration.merge_categories(django_apps, None)

        # Assert
        tafsir.refresh_from_db()
        translation.refresh_from_db()
        mushaf.refresh_from_db()
        self.assertEqual(("text", ["tafsir"]), (tafsir.category, [t.slug for t in tafsir.tags.all()]))
        self.assertEqual(("text", ["translation"]), (translation.category, [t.slug for t in translation.tags.all()]))
        self.assertEqual((CategoryChoice.MUSHAF, []), (mushaf.category, list(mushaf.tags.all())))
        self.assertTrue(AssetTag.objects.get(slug="tafsir").is_builtin)

    def test_merge_permissions_where_role_holds_either_old_permission_should_get_the_merged_one(self):
        # Arrange
        content_type = ContentType.objects.get_for_model(CustomPermission)
        old_tafsir = Permission.objects.create(content_type=content_type, codename="portal_read_tafsir", name="t")
        old_translation = Permission.objects.create(
            content_type=content_type, codename="portal_read_translation", name="t"
        )
        tafsir_role = baker.make(Group, name="Tafsir editors")
        tafsir_role.permissions.add(old_tafsir)
        translator = baker.make(User, email="translator@example.com")
        translator.user_permissions.add(old_translation)
        bystander = baker.make(Group, name="Recitations only")

        # Act
        migration.merge_permissions(django_apps, None)

        # Assert
        merged = PermissionChoice.PORTAL_READ_TEXT_ASSET.value
        self.assertTrue(tafsir_role.permissions.filter(codename=merged).exists())
        self.assertTrue(translator.user_permissions.filter(codename=merged).exists())
        self.assertFalse(bystander.permissions.exists())
        self.assertFalse(Permission.objects.filter(codename__in=["portal_read_tafsir", "portal_read_translation"]))


class TextAssetPortalTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.publisher = baker.make(Publisher, name="Publisher")
        self.user = User.objects.create_user(email="editor@example.com", name="Editor", is_staff=True)

    def _create(self, **overrides):
        data = {
            "name_en": "Ibn Kathir",
            "license": "CC0",
            "language": "en",
            "publisher_id": self.publisher.id,
            "template": "ayah",
        } | overrides
        return self.client.post("/portal/text-assets/", data=data)

    def test_create_text_asset_where_no_tag_should_return_400_text_asset_tag_required(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_CREATE_TEXT_ASSET)

        # Act
        response = self._create()

        # Assert
        self.assertEqual(400, response.status_code, response.content)
        self.assertEqual("text_asset_tag_required", response.json()["error_name"])
        self.assertFalse(Asset.objects.exists())

    def test_create_text_asset_where_tag_unknown_should_return_400_asset_tag_not_found(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_CREATE_TEXT_ASSET)

        # Act
        response = self._create(tags="poetry")

        # Assert
        self.assertEqual(400, response.status_code, response.content)
        self.assertEqual("asset_tag_not_found", response.json()["error_name"])

    def test_create_text_asset_where_staff_added_tag_should_prefix_the_slug_with_the_first_tag(self):
        # Arrange
        AssetTag.objects.create(slug="irab", name="إعراب", name_en="Irab", name_ar="إعراب")
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_CREATE_TEXT_ASSET)

        # Act
        response = self._create(tags=["irab", "tafsir"])

        # Assert
        self.assertEqual(201, response.status_code, response.content)
        body = response.json()
        self.assertEqual(["irab", "tafsir"], sorted(tag["slug"] for tag in body["tags"]))
        self.assertTrue(Asset.objects.get(id=body["id"]).slug.startswith("irab-"))

    def test_create_text_asset_where_translation_tag_should_put_language_in_slug(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_CREATE_TEXT_ASSET)

        # Act
        response = self._create(tags="translation", name_en="Sahih International")

        # Assert
        self.assertEqual(201, response.status_code, response.content)
        self.assertEqual("translation-en-sahih-international", Asset.objects.get(id=response.json()["id"]).slug)

    def test_patch_text_asset_where_group_tafsir_loses_tafsir_tag_should_return_400_template_not_allowed(self):
        # Arrange
        asset = _text_asset("tafsir", publisher=self.publisher, template=AssetTemplateChoice.AYAH_GROUP)
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_UPDATE_TEXT_ASSET)

        # Act
        response = self.client.patch(
            f"/portal/text-assets/{asset.slug}/", data={"tags": "translation"}, format="multipart"
        )

        # Assert
        self.assertEqual(400, response.status_code, response.content)
        self.assertEqual("template_not_allowed", response.json()["error_name"])
        self.assertEqual(["tafsir"], [tag.slug for tag in asset.tags.all()])

    def test_patch_text_asset_where_tags_sent_should_replace_them(self):
        # Arrange
        asset = _text_asset("tafsir", publisher=self.publisher)
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_UPDATE_TEXT_ASSET)

        # Act
        response = self.client.patch(
            f"/portal/text-assets/{asset.slug}/", data={"tags": ["translation"]}, format="multipart"
        )

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual(["translation"], [tag["slug"] for tag in response.json()["tags"]])

    def test_list_text_assets_where_tag_filter_given_should_list_only_those(self):
        # Arrange
        tafsir = _text_asset("tafsir", publisher=self.publisher)
        _text_asset("translation", publisher=self.publisher)
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_READ_TEXT_ASSET)

        # Act
        response = self.client.get("/portal/text-assets/", {"tag": "tafsir"})

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual([tafsir.id], [row["id"] for row in response.json()["results"]])


class TextAssetConsumerTests(BaseTestCase):
    def test_gallery_list_where_tag_filter_given_should_list_matching_assets_once(self):
        # Arrange: two matching tags must not list the asset twice
        both = make_visible(_text_asset("tafsir", "translation"))
        make_visible(_text_asset("translation"))
        make_visible(baker.make(Asset, category=CategoryChoice.MUSHAF, status=StatusChoice.READY))

        # Act
        response = self.client.get("/cms-api/assets/", {"tag": ["tafsir", "translation"], "category": "text"})

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        ids = [row["id"] for row in response.json()["results"]]
        self.assertEqual(2, len(ids))
        self.assertEqual(1, ids.count(both.id))

    def test_gallery_list_where_old_category_sent_should_return_400_category_renamed(self):
        # Act
        response = self.client.get("/cms-api/assets/", {"category": "tafsir"})

        # Assert
        self.assertEqual(400, response.status_code, response.content)
        self.assertEqual("category_renamed", response.json()["error_name"])

    def test_gallery_list_where_more_tagged_assets_should_not_add_queries(self):
        # Arrange
        make_visible(_text_asset("tafsir"))
        with CaptureQueriesContext(connection) as few:
            self.client.get("/cms-api/assets/")
        for _ in range(4):
            make_visible(_text_asset("tafsir", "translation"))

        # Act
        with CaptureQueriesContext(connection) as many:
            response = self.client.get("/cms-api/assets/")

        # Assert
        self.assertEqual(5, len(response.json()["results"]))
        self.assertEqual(len(few.captured_queries), len(many.captured_queries))

    def test_gallery_detail_where_text_asset_should_expose_tags(self):
        # Arrange
        asset = make_visible(_text_asset("translation"))

        # Act
        response = self.client.get(f"/cms-api/assets/{asset.id}/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual(
            ("text", ["translation"]), (response.json()["category"], [t["slug"] for t in response.json()["tags"]])
        )

    def test_asset_tags_list_should_return_builtin_tags(self):
        # Act
        response = self.client.get("/cms-api/asset-tags/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual(["tafsir", "translation"], [tag["slug"] for tag in response.json()])

    def test_catalog_where_old_category_sent_should_return_400_category_renamed(self):
        # Act
        response = self.client.get("/packages/", {"category": "translation"})

        # Assert
        self.assertEqual(400, response.status_code, response.content)
        self.assertEqual("category_renamed", response.json()["error_name"])

    def test_recommendations_where_text_assets_share_no_tag_should_not_score_category_match(self):
        # Arrange
        tafsir_a = _text_asset("tafsir", in_public_api=True)
        tafsir_b = _text_asset("tafsir", in_public_api=True)
        translation = _text_asset("translation", in_public_api=True)
        for asset in (tafsir_a, tafsir_b, translation):
            publish(baker.make(AssetVersion, asset=asset))

        # Act
        scores = _score_pairs(_visible_asset_values())

        # Assert
        self.assertGreater(scores[tafsir_a.id][tafsir_b.id], 0)
        self.assertNotIn(translation.id, scores[tafsir_a.id])


class TextAssetGalleryFilterTests(BaseTestCase):
    def test_gallery_list_where_other_category_and_tag_given_should_list_both(self):
        # Arrange
        mushaf = make_visible(baker.make(Asset, category=CategoryChoice.MUSHAF, status=StatusChoice.READY))
        tafsir = make_visible(_text_asset("tafsir"))
        make_visible(_text_asset("translation"))

        # Act
        response = self.client.get("/cms-api/assets/", {"category": ["mushaf", "text"], "tag": "tafsir"})

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual({mushaf.id, tafsir.id}, {row["id"] for row in response.json()["results"]})

    def test_gallery_list_where_search_matches_two_tags_should_list_asset_once(self):
        # Arrange: "t" matches both tag slugs
        asset = make_visible(_text_asset("tafsir", "translation", name="Zzz"))

        # Act
        response = self.client.get("/cms-api/assets/", {"search": "t"})

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual(1, [row["id"] for row in response.json()["results"]].count(asset.id))
