from django.core.cache import cache
from django.db import connection
from django.test.utils import CaptureQueriesContext
from model_bakery import baker

from apps.content.models import Asset, AssetTag, AssetTemplateChoice, CategoryChoice, Qiraah, Reciter, StatusChoice
from apps.core.permissions import PermissionChoice
from apps.core.tests.base import BaseTestCase
from apps.publishers.models import Publisher, PublisherMember
from apps.publishers.tests.services.test_effective_permissions import join, role
from apps.users.models import User

URL = "/portal/asset-counts/"
READ_ALL = (
    PermissionChoice.PORTAL_ACCESS,
    PermissionChoice.PORTAL_READ_TEXT_ASSET,
    PermissionChoice.PORTAL_READ_MUSHAF,
    PermissionChoice.PORTAL_READ_FONT,
    PermissionChoice.PORTAL_READ_RECITATION,
)


def _count_queries(context: CaptureQueriesContext) -> list[str]:
    """The queries that read assets or tags (the rest is session, user and permission lookups)."""
    return [query["sql"] for query in context.captured_queries if '"content_asset' in query["sql"]]


class PortalAssetCountsTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        cache.clear()
        self.publisher = baker.make(Publisher, name="Mine")
        self.other = baker.make(Publisher, name="Other")
        self.reciter = baker.make(Reciter)
        self.qiraah = baker.make(Qiraah)
        self.tafsir, _ = AssetTag.objects.update_or_create(
            slug="tafsir", defaults={"name": "Tafsir", "name_en": "Tafsir", "name_ar": "تفسير"}
        )
        self.translation, _ = AssetTag.objects.update_or_create(
            slug="translation", defaults={"name": "Translation", "name_en": "Translation", "name_ar": "ترجمة"}
        )
        self.member = User.objects.create_user(email="member@example.com", name="Member")

    def _member_of(self, publisher: Publisher, *permissions: PermissionChoice) -> PublisherMember:
        return join(self.member, publisher, role(publisher, *permissions))

    def _asset(self, category: CategoryChoice, publisher: Publisher | None = None, **kwargs) -> Asset:
        extra = {"status": StatusChoice.READY}
        if category == CategoryChoice.RECITATION:
            extra.update(reciter=self.reciter, qiraah=self.qiraah)
        if category == CategoryChoice.TEXT:
            extra["template"] = AssetTemplateChoice.AYAH
        tags = kwargs.pop("tags", [])
        asset = baker.make(Asset, category=category, publisher=publisher or self.publisher, **{**extra, **kwargs})
        asset.tags.set(tags)
        return asset

    def _seed(self, per_type: int = 1) -> None:
        for _ in range(per_type):
            self._asset(CategoryChoice.MUSHAF)
            self._asset(CategoryChoice.FONT)
            self._asset(CategoryChoice.RECITATION)
            self._asset(CategoryChoice.TEXT, tags=[self.tafsir])
            self._asset(CategoryChoice.TEXT, tags=[self.translation])

    def _get(self):
        response = self.client.get(URL)
        self.assertEqual(200, response.status_code, response.content)
        return {row["category"]: row for row in response.json()["categories"]}

    def test_asset_counts_where_member_reads_every_type_should_count_own_assets_with_drafts(self):
        # Arrange
        self._member_of(self.publisher, *READ_ALL)
        self._asset(CategoryChoice.MUSHAF)
        self._asset(CategoryChoice.MUSHAF, status=StatusChoice.DRAFT)
        self._asset(CategoryChoice.RECITATION)
        self._asset(CategoryChoice.PROGRAM)
        self._asset(CategoryChoice.MUSHAF, publisher=self.other)
        self._asset(CategoryChoice.FONT, publisher=self.other)
        self.authenticate_user(self.member, HTTP_X_TENANT=str(self.publisher.id))

        # Act
        response = self.client.get(URL)

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual(
            [
                {"category": "text", "total": 0, "drafts": 0, "tags": []},
                {"category": "mushaf", "total": 2, "drafts": 1, "tags": []},
                {"category": "font", "total": 0, "drafts": 0, "tags": []},
                {"category": "recitation", "total": 1, "drafts": 0, "tags": []},
            ],
            response.json()["categories"],
        )

    def test_asset_counts_where_text_assets_are_tagged_should_break_text_down_by_tag(self):
        # Arrange
        self._member_of(self.publisher, *READ_ALL)
        self._asset(CategoryChoice.TEXT, tags=[self.tafsir])
        self._asset(CategoryChoice.TEXT, tags=[self.translation], status=StatusChoice.DRAFT)
        self._asset(CategoryChoice.TEXT, tags=[self.translation, self.tafsir])
        self._asset(CategoryChoice.TEXT)
        self._asset(CategoryChoice.TEXT, publisher=self.other, tags=[self.tafsir])
        baker.make(AssetTag, slug="unused", name="Unused")
        self.authenticate_user(self.member, HTTP_X_TENANT=str(self.publisher.id))

        # Act
        counts = self._get()

        # Assert
        text = counts["text"]
        self.assertEqual((4, 1), (text["total"], text["drafts"]))
        self.assertEqual(
            [
                {"slug": "tafsir", "name": "Tafsir", "total": 2, "drafts": 0},
                {"slug": "translation", "name": "Translation", "total": 2, "drafts": 1},
            ],
            text["tags"],
        )

    def test_asset_counts_where_language_is_arabic_should_name_tags_in_arabic(self):
        # Arrange
        self._member_of(self.publisher, *READ_ALL)
        self._asset(CategoryChoice.TEXT, tags=[self.tafsir])
        self.authenticate_user(self.member, language="ar", HTTP_X_TENANT=str(self.publisher.id))

        # Act
        counts = self._get()

        # Assert
        self.assertEqual("تفسير", counts["text"]["tags"][0]["name"])

    def test_asset_counts_where_user_reads_only_recitations_should_return_only_recitations(self):
        # Arrange
        self._member_of(self.publisher, PermissionChoice.PORTAL_ACCESS, PermissionChoice.PORTAL_READ_RECITATION)
        self._seed()
        self.authenticate_user(self.member, HTTP_X_TENANT=str(self.publisher.id))

        # Act
        counts = self._get()

        # Assert
        self.assertEqual(["recitation"], list(counts))
        self.assertEqual(1, counts["recitation"]["total"])

    def test_asset_counts_where_read_permissions_are_held_at_other_publisher_should_omit_those_types(self):
        # Arrange
        self._member_of(self.publisher, PermissionChoice.PORTAL_ACCESS)
        self._member_of(self.other, *READ_ALL)
        self._seed()
        self.authenticate_user(self.member, HTTP_X_TENANT=str(self.publisher.id))

        # Act
        counts = self._get()

        # Assert
        self.assertEqual({}, counts)

    def test_asset_counts_where_user_is_member_of_two_publishers_should_count_only_the_tenant(self):
        # Arrange
        self._member_of(self.publisher, *READ_ALL)
        self._member_of(self.other, *READ_ALL)
        self._asset(CategoryChoice.FONT)
        self._asset(CategoryChoice.FONT, publisher=self.other)
        self._asset(CategoryChoice.FONT, publisher=self.other)
        self.authenticate_user(self.member, HTTP_X_TENANT=str(self.other.id))

        # Act
        counts = self._get()

        # Assert
        self.assertEqual(2, counts["font"]["total"])

    def test_asset_counts_where_staff_has_no_tenant_should_count_every_publisher(self):
        # Arrange
        staff = User.objects.create_user(email="staff@example.com", name="Staff", is_staff=True)
        for permission in READ_ALL:
            self.give_permission(staff, permission)
        self._asset(CategoryChoice.MUSHAF)
        self._asset(CategoryChoice.MUSHAF, publisher=self.other)
        self.authenticate_user(staff)

        # Act
        counts = self._get()

        # Assert
        self.assertEqual(2, counts["mushaf"]["total"])

    def test_asset_counts_where_tenant_is_not_users_publisher_should_return_403(self):
        # Arrange
        self._member_of(self.publisher, *READ_ALL)
        self._seed()
        self.authenticate_user(self.member, HTTP_X_TENANT=str(self.other.id))

        # Act
        response = self.client.get(URL)

        # Assert
        self.assertEqual(403, response.status_code, response.content)
        self.assertEqual("permission_denied", response.json()["error_name"])

    def test_asset_counts_where_user_lacks_portal_access_should_return_403(self):
        # Arrange
        self._member_of(self.publisher, PermissionChoice.PORTAL_READ_MUSHAF)
        self.authenticate_user(self.member, HTTP_X_TENANT=str(self.publisher.id))

        # Act
        response = self.client.get(URL)

        # Assert
        self.assertEqual(403, response.status_code, response.content)
        self.assertEqual("permission_denied", response.json()["error_name"])

    def test_asset_counts_where_unauthenticated_should_return_401(self):
        # Act
        response = self.client.get(URL)

        # Assert
        self.assertEqual(401, response.status_code, response.content)
        self.assertEqual("authentication_error", response.json()["error_name"])

    def test_asset_counts_where_assets_grow_should_run_the_same_number_of_queries(self):
        # Arrange
        self._member_of(self.publisher, *READ_ALL)
        self.authenticate_user(self.member, HTTP_X_TENANT=str(self.publisher.id))
        self._seed(per_type=1)
        with CaptureQueriesContext(connection) as few:
            self._get()
        cache.clear()
        self._seed(per_type=10)

        # Act
        with CaptureQueriesContext(connection) as many:
            counts = self._get()

        # Assert
        self.assertEqual(11, counts["mushaf"]["total"])
        self.assertEqual(len(few), len(many))
        self.assertEqual(2, len(_count_queries(many)))

    def test_asset_counts_where_cached_should_skip_the_count_queries(self):
        # Arrange
        self._member_of(self.publisher, *READ_ALL)
        self._seed()
        self.authenticate_user(self.member, HTTP_X_TENANT=str(self.publisher.id))
        with CaptureQueriesContext(connection) as cold:
            self._get()

        # Act
        with CaptureQueriesContext(connection) as warm:
            self._get()

        # Assert
        self.assertEqual(2, len(_count_queries(cold)))
        self.assertEqual([], _count_queries(warm))

    def test_asset_counts_where_asset_is_created_should_show_it_on_the_next_request(self):
        # Arrange
        self._member_of(self.publisher, *READ_ALL)
        self._asset(CategoryChoice.FONT)
        self.authenticate_user(self.member, HTTP_X_TENANT=str(self.publisher.id))
        self.assertEqual(1, self._get()["font"]["total"])

        # Act
        with self.captureOnCommitCallbacks(execute=True):
            self._asset(CategoryChoice.FONT, status=StatusChoice.DRAFT)
        counts = self._get()

        # Assert
        self.assertEqual((2, 1), (counts["font"]["total"], counts["font"]["drafts"]))

    def test_asset_counts_where_asset_is_retagged_should_update_the_tag_breakdown(self):
        # Arrange
        self._member_of(self.publisher, *READ_ALL)
        asset = self._asset(CategoryChoice.TEXT, tags=[self.tafsir])
        self.authenticate_user(self.member, HTTP_X_TENANT=str(self.publisher.id))
        self.assertEqual(["tafsir"], [tag["slug"] for tag in self._get()["text"]["tags"]])

        # Act
        with self.captureOnCommitCallbacks(execute=True):
            asset.tags.set([self.translation])
        counts = self._get()

        # Assert
        self.assertEqual(["translation"], [tag["slug"] for tag in counts["text"]["tags"]])

    def test_asset_counts_where_asset_is_deleted_should_drop_it_on_the_next_request(self):
        # Arrange
        self._member_of(self.publisher, *READ_ALL)
        asset = self._asset(CategoryChoice.MUSHAF)
        self.authenticate_user(self.member, HTTP_X_TENANT=str(self.publisher.id))
        self.assertEqual(1, self._get()["mushaf"]["total"])

        # Act
        with self.captureOnCommitCallbacks(execute=True):
            asset.delete()
        counts = self._get()

        # Assert
        self.assertEqual(0, counts["mushaf"]["total"])

    def test_asset_counts_where_unrelated_field_is_saved_should_keep_the_cache(self):
        # Arrange
        self._member_of(self.publisher, *READ_ALL)
        asset = self._asset(CategoryChoice.MUSHAF)
        self.authenticate_user(self.member, HTTP_X_TENANT=str(self.publisher.id))
        self._get()
        Asset.objects.filter(pk=asset.pk).update(status=StatusChoice.DRAFT)  # no signal: stays cached

        # Act
        with self.captureOnCommitCallbacks(execute=True):
            asset.name = "Renamed"
            asset.save(update_fields=["name"])
        counts = self._get()

        # Assert
        self.assertEqual(0, counts["mushaf"]["drafts"])
