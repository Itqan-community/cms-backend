from django.db import IntegrityError
from django.utils import timezone
from model_bakery import baker

from apps.core.tests.base import BaseTestCase
from apps.publishers.models import Publisher, PublisherMember, PublisherMemberInvitation
from apps.users.models import User


class InvitationModelTest(BaseTestCase):
    def _member(self, publisher, email="member@example.com", role=PublisherMember.RoleChoice.STAFF):
        user = baker.make(User, email=email)
        return PublisherMember.objects.create(user=user, publisher=publisher, role=role)

    def test_email_and_role_are_derived_from_member(self):
        publisher = baker.make(Publisher)
        member = self._member(publisher, email="Derived@Example.COM", role=PublisherMember.RoleChoice.ADMIN)
        inv = PublisherMemberInvitation.objects.create(
            publisher=publisher,
            invited_by=baker.make(User),
            member=member,
            token_hash="hash1",
            expires_at=timezone.now(),
        )
        field_names = {f.name for f in PublisherMemberInvitation._meta.get_fields()}
        self.assertNotIn("email", field_names)
        self.assertNotIn("role", field_names)
        self.assertEqual("derived@example.com", inv.email)
        self.assertEqual(PublisherMember.RoleChoice.ADMIN, inv.role)

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
