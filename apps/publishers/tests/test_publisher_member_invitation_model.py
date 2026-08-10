from django.db import IntegrityError
from django.utils import timezone
from model_bakery import baker

from apps.core.tests.base import BaseTestCase
from apps.publishers.models import Publisher, PublisherMember, PublisherMemberInvitation
from apps.publishers.tests.group_helpers import admin_group, member_group
from apps.users.models import User


class InvitationModelTest(BaseTestCase):
    def _member(self, publisher, email="member@example.com", group=None):
        user = baker.make(User, email=email)
        return PublisherMember.objects.create(user=user, publisher=publisher, group=group or member_group())

    def test_email_and_group_name_are_derived_from_member(self):
        publisher = baker.make(Publisher)
        member = self._member(publisher, email="Derived@Example.COM", group=admin_group())
        inv = PublisherMemberInvitation.objects.create(
            publisher=publisher,
            invited_by=baker.make(User),
            member=member,
            token_hash="hash1",
            expires_at=timezone.now(),
        )
        field_names = {f.name for f in PublisherMemberInvitation._meta.get_fields()}
        self.assertNotIn("email", field_names)
        self.assertNotIn("group_name", field_names)
        self.assertEqual("derived@example.com", inv.email)
        self.assertEqual(admin_group().name, inv.group_name)

    def test_only_one_pending_invite_per_member(self):
        publisher = baker.make(Publisher)
        member = self._member(publisher)
        common = {
            "publisher": publisher,
            "invited_by": baker.make(User),
            "expires_at": timezone.now(),
        }
        PublisherMemberInvitation.objects.create(member=member, token_hash="h1", **common)
        with self.assertRaises(IntegrityError):
            PublisherMemberInvitation.objects.create(member=member, token_hash="h2", **common)
