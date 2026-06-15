from model_bakery import baker

from apps.core.permissions import PermissionChoice
from apps.core.tests.base import BaseTestCase
from apps.publishers.models import Publisher, PublisherMember
from apps.users.models import User


class ListMembersTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.p1 = baker.make(Publisher)
        self.p2 = baker.make(Publisher)
        self.admin = baker.make(User, is_staff=False)
        PublisherMember.objects.create(
            user=self.admin,
            publisher=self.p1,
            role=PublisherMember.RoleChoice.ADMIN,
            status=PublisherMember.StatusChoice.ACTIVE,
        )
        PublisherMember.objects.create(
            user=baker.make(User),
            publisher=self.p2,
            role=PublisherMember.RoleChoice.STAFF,
            status=PublisherMember.StatusChoice.ACTIVE,
        )

    def test_admin_lists_only_own_publisher_via_filter(self):
        self.authenticate_user(self.admin)
        self.give_permission(self.admin, PermissionChoice.PORTAL_VIEW_PUBLISHER_MEMBERS)
        resp = self.client.get(f"/portal/members/?publisher_id={self.p1.id}")
        self.assertEqual(200, resp.status_code, resp.content)
        publisher_ids = {m["publisher_id"] for m in resp.json()["results"]}
        self.assertEqual({self.p1.id}, publisher_ids)

    def test_admin_foreign_publisher_filter_returns_empty_list_not_403(self):
        self.authenticate_user(self.admin)
        self.give_permission(self.admin, PermissionChoice.PORTAL_VIEW_PUBLISHER_MEMBERS)
        resp = self.client.get(f"/portal/members/?publisher_id={self.p2.id}")
        self.assertEqual(200, resp.status_code, resp.content)
        self.assertEqual([], resp.json()["results"])

    def test_status_filter_narrows_results(self):
        baker.make(
            PublisherMember,
            publisher=self.p1,
            user=baker.make(User),
            role=PublisherMember.RoleChoice.STAFF,
            status=PublisherMember.StatusChoice.PENDING,
        )
        self.authenticate_user(self.admin)
        self.give_permission(self.admin, PermissionChoice.PORTAL_VIEW_PUBLISHER_MEMBERS)
        resp = self.client.get(f"/portal/members/?publisher_id={self.p1.id}&status=pending")
        self.assertEqual(200, resp.status_code, resp.content)
        statuses = {m["status"] for m in resp.json()["results"]}
        self.assertEqual({"pending"}, statuses)

    def test_itqan_lists_all_members_flat(self):
        itqan = baker.make(User, is_staff=True)
        self.authenticate_user(itqan)
        self.give_permission(itqan, PermissionChoice.PORTAL_VIEW_PUBLISHER_MEMBERS)
        resp = self.client.get("/portal/members/")
        self.assertEqual(200, resp.status_code, resp.content)
        publisher_ids = {m["publisher_id"] for m in resp.json()["results"]}
        self.assertTrue({self.p1.id, self.p2.id}.issubset(publisher_ids))

    def test_admin_flat_endpoint_is_scoped_to_own_publishers(self):
        self.authenticate_user(self.admin)
        self.give_permission(self.admin, PermissionChoice.PORTAL_VIEW_PUBLISHER_MEMBERS)
        resp = self.client.get("/portal/members/")
        self.assertEqual(200, resp.status_code, resp.content)
        publisher_ids = {m["publisher_id"] for m in resp.json()["results"]}
        self.assertEqual({self.p1.id}, publisher_ids)
