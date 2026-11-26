from django.db import connection
from django.test.utils import CaptureQueriesContext
from model_bakery import baker

from apps.content.models import (
    Asset,
    AssetTemplateChoice,
    CategoryChoice,
    ContentIssueReport,
    MushafLayout,
    StatusChoice,
)
from apps.content.tests.quran_data import QuranDataMixin
from apps.core.permissions import PermissionChoice
from apps.core.tests.base import BaseTestCase
from apps.publishers.models import Publisher, PublisherMember
from apps.publishers.tests.services.test_effective_permissions import role
from apps.users.models import User

Status = ContentIssueReport.StatusChoice


class GridIssuesTests(QuranDataMixin, BaseTestCase):
    """``GET /portal/content/{category}/{slug}/issues/``: an asset's open issues, by surah:ayah."""

    def setUp(self):
        super().setUp()
        self.bake_quran()
        self.publisher = baker.make(Publisher, name="Issues Publisher")
        self.reporter = User.objects.create_user(email="grid-reporter@example.com", name="Reporter")
        self.user = User.objects.create_user(email="grid-editor@example.com", name="Editor", is_staff=True)
        self.give_permission(self.user, PermissionChoice.PORTAL_READ_TEXT_ASSET)

    def _asset(self, template: AssetTemplateChoice, layout: MushafLayout | None = None) -> Asset:
        return baker.make(
            Asset,
            publisher=self.publisher,
            category=CategoryChoice.TEXT,
            status=StatusChoice.READY,
            template=template,
            mushaf_layout=layout,
        )

    def _report(self, asset: Asset, context: dict | None, status: str = Status.PENDING) -> ContentIssueReport:
        return ContentIssueReport.objects.create(
            asset=asset, reporter=self.reporter, description="Wrong text here.", context=context, status=status
        )

    def _get(self, asset: Asset, **headers):
        return self.client.get(f"/portal/content/text-assets/{asset.slug}/issues/", **headers)

    def test_list_grid_issues_where_ayah_asset_has_open_issues_should_group_them_by_ayah(self):
        # Arrange
        asset = self._asset(AssetTemplateChoice.AYAH)
        later = self._report(asset, {"surah": 2, "ayah": 1}, Status.UNDER_REVIEW)
        first = self._report(asset, {"surah": 1, "ayah": 2})
        second = self._report(asset, {"surah": 1, "ayah": 2})
        self._report(asset, {"surah": 1, "ayah": 1}, Status.RESOLVED)
        self._report(asset, {"surah": 1, "ayah": 1}, Status.DISMISSED)
        self._report(asset, None)
        self._report(self._asset(AssetTemplateChoice.AYAH), {"surah": 1, "ayah": 1})
        self.authenticate_user(self.user)

        # Act
        response = self._get(asset)

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual(
            [(1, 2, self.ayah2.id, [first.id, second.id]), (2, 1, self.ayah3.id, [later.id])],
            [(g["surah"], g["ayah"], g["unit_id"], [i["id"] for i in g["issues"]]) for g in body],
        )
        self.assertEqual(
            {"id", "description", "status", "created_at"},
            set(body[1]["issues"][0]),
        )
        self.assertEqual("under_review", body[1]["issues"][0]["status"])

    def test_list_grid_issues_where_word_asset_should_land_on_the_ayahs_first_word(self):
        # Arrange
        asset = self._asset(AssetTemplateChoice.WORD)
        self._report(asset, {"surah": 1, "ayah": 1})
        self.authenticate_user(self.user)

        # Act
        response = self._get(asset)

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual(self.word1.id, response.json()[0]["unit_id"])

    def test_list_grid_issues_where_surah_asset_should_land_on_the_surah(self):
        # Arrange
        asset = self._asset(AssetTemplateChoice.SURAH)
        self._report(asset, {"surah": 2, "ayah": 1})
        self.authenticate_user(self.user)

        # Act
        response = self._get(asset)

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual(2, response.json()[0]["unit_id"])

    def test_list_grid_issues_where_page_asset_should_land_on_the_ayahs_page_within_the_layout(self):
        # Arrange
        layout = baker.make(MushafLayout, name="One page", page_count=1)
        asset = self._asset(AssetTemplateChoice.PAGE, layout)
        self._report(asset, {"surah": 1, "ayah": 2})  # page 1
        self._report(asset, {"surah": 2, "ayah": 1})  # page 2: past the layout's last page
        self.authenticate_user(self.user)

        # Act
        response = self._get(asset)

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual([1, None], [g["unit_id"] for g in response.json()])

    def test_list_grid_issues_where_group_asset_should_leave_the_row_to_the_client(self):
        # Arrange
        asset = self._asset(AssetTemplateChoice.AYAH_GROUP)
        self._report(asset, {"surah": 1, "ayah": 1})
        self.authenticate_user(self.user)

        # Act
        response = self._get(asset)

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual([(1, 1, None)], [(g["surah"], g["ayah"], g["unit_id"]) for g in response.json()])

    def test_list_grid_issues_where_many_issues_should_use_a_constant_number_of_queries(self):
        # Arrange
        asset = self._asset(AssetTemplateChoice.WORD)
        self._report(asset, {"surah": 1, "ayah": 1})
        self.authenticate_user(self.user)
        with CaptureQueriesContext(connection) as one:
            self._get(asset)
        for surah, ayah in ((1, 1), (1, 2), (2, 1), (1, 2)):
            self._report(asset, {"surah": surah, "ayah": ayah}, Status.UNDER_REVIEW)

        # Act
        with CaptureQueriesContext(connection) as many:
            response = self._get(asset)

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual(3, len(response.json()))
        self.assertEqual(len(one), len(many))

    def test_list_grid_issues_where_user_cannot_read_text_assets_should_return_403(self):
        # Arrange
        asset = self._asset(AssetTemplateChoice.AYAH)
        self.remove_permission(self.user, PermissionChoice.PORTAL_READ_TEXT_ASSET)
        self.authenticate_user(self.user)

        # Act
        response = self._get(asset)

        # Assert
        self.assertEqual(403, response.status_code, response.content)
        self.assertEqual("permission_denied", response.json()["error_name"])

    def test_list_grid_issues_where_asset_belongs_to_another_publisher_should_return_404(self):
        # Arrange
        asset = self._asset(AssetTemplateChoice.AYAH)
        self._report(asset, {"surah": 1, "ayah": 1})
        other = baker.make(Publisher, name="Other Publisher")
        member = User.objects.create_user(email="grid-member@example.com", name="Member")
        group = role(other, PermissionChoice.PORTAL_ACCESS, PermissionChoice.PORTAL_READ_TEXT_ASSET)
        PublisherMember.objects.create(
            user=member, publisher=other, group=group, status=PublisherMember.StatusChoice.ACTIVE
        )
        self.authenticate_user(member, HTTP_X_TENANT=str(other.id))

        # Act
        response = self._get(asset)

        # Assert
        self.assertEqual(404, response.status_code, response.content)
        self.assertEqual("text_asset_not_found", response.json()["error_name"])

    def test_list_grid_issues_where_member_of_the_assets_publisher_should_return_its_issues(self):
        # Arrange
        asset = self._asset(AssetTemplateChoice.AYAH)
        report = self._report(asset, {"surah": 1, "ayah": 1})
        member = User.objects.create_user(email="grid-own-member@example.com", name="Own Member")
        group = role(self.publisher, PermissionChoice.PORTAL_ACCESS, PermissionChoice.PORTAL_READ_TEXT_ASSET)
        PublisherMember.objects.create(
            user=member, publisher=self.publisher, group=group, status=PublisherMember.StatusChoice.ACTIVE
        )
        self.authenticate_user(member, HTTP_X_TENANT=str(self.publisher.id))

        # Act
        response = self._get(asset)

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual([report.id], [i["id"] for i in response.json()[0]["issues"]])
