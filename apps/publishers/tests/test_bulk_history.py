"""Tests asserting history preservation for bulk operations in apps.publishers (ITQ-34 / #432)."""

from django.utils import timezone

from apps.core.tests.base import BaseTestCase
from apps.publishers.models import Domain, MemberLanguage, Publisher, PublisherMember, PublisherMemberInvitation
from apps.publishers.repositories.publisher_member_invitation import PublisherMemberInvitationRepository
from apps.publishers.tests.group_helpers import admin_group
from apps.users.models import User


class PublishersBulkHistoryTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user(email="user@example.com", name="Test User")
        self.publisher = Publisher.objects.create(name="Publisher Corp", slug="pub-corp")
        self.member = PublisherMember.objects.create(publisher=self.publisher, user=self.user, group=admin_group())
        self.invitation_repo = PublisherMemberInvitationRepository()

    def test_domain_save_where_new_primary_saved_should_write_history_for_demoted_domains(self):
        # Arrange: create first primary domain
        domain1 = Domain.objects.create(publisher=self.publisher, domain="alpha.example.com", is_primary=True)
        initial_history_count = domain1.history.count()

        # Act: create second primary domain (triggers Domain.save demotion of domain1)
        domain2 = Domain.objects.create(publisher=self.publisher, domain="beta.example.com", is_primary=True)

        # Assert: domain1 is demoted in default DB
        domain1.refresh_from_db()
        assert domain1.is_primary is False
        assert domain2.is_primary is True

        # Assert: domain1 received a historical record with history_type='~' and is_primary=False
        latest_history = domain1.history.order_by("-history_date").first()
        assert latest_history is not None
        assert latest_history.history_type == "~"
        assert latest_history.is_primary is False
        assert domain1.history.count() == initial_history_count + 1

    def test_cancel_pending_invitations_where_invitations_exist_should_write_history_records(self):
        # Arrange: create pending invitation for member
        inv = self.invitation_repo.create_invitation(
            publisher=self.publisher,
            invited_by=self.user,
            member=self.member,
            token_hash="hash1",
            expires_at=timezone.now() + timezone.timedelta(days=7),
        )

        # Act: cancel all pending invitations for member
        now = timezone.now()
        self.invitation_repo.cancel_pending_invitations(member=self.member, cancelled_by=self.user, now=now)

        # Assert: default DB status updated to CANCELLED
        inv.refresh_from_db()
        assert inv.status == PublisherMemberInvitation.StatusChoice.CANCELLED

        # Assert: audit DB has update (~) record for invitation
        h = inv.history.order_by("-history_date").first()
        assert h is not None
        assert h.history_type == "~"
        assert h.status == PublisherMemberInvitation.StatusChoice.CANCELLED

    def test_mark_expired_where_invitations_given_should_write_history_records(self):
        # Arrange: create pending invitation
        inv = self.invitation_repo.create_invitation(
            publisher=self.publisher,
            invited_by=self.user,
            member=self.member,
            token_hash="hash_exp",
            expires_at=timezone.now() - timezone.timedelta(days=1),
        )

        # Act: mark expired in bulk
        count = self.invitation_repo.mark_expired([inv])

        # Assert: returned count is 1 and status is EXPIRED
        assert count == 1
        inv.refresh_from_db()
        assert inv.status == PublisherMemberInvitation.StatusChoice.EXPIRED

        # Assert: audit DB historical record with ~
        latest_h = inv.history.order_by("-history_date").first()
        assert latest_h.history_type == "~"
        assert latest_h.status == PublisherMemberInvitation.StatusChoice.EXPIRED

    def test_member_languages_bulk_create_where_languages_set_should_write_history_records(self):
        # Arrange: language codes to assign
        languages = ["ar", "en", "fr"]

        # Act: bulk create using simple_history helper
        from simple_history.utils import bulk_create_with_history

        created_objs = bulk_create_with_history(
            [MemberLanguage(member=self.member, language=code) for code in languages],
            MemberLanguage,
        )

        # Assert: 3 objects in default DB
        assert len(created_objs) == 3
        assert MemberLanguage.objects.filter(member=self.member).count() == 3

        # Assert: 3 history records in audit DB with history_type='+'
        hist_records = list(MemberLanguage.history.filter(member_id=self.member.id))
        assert len(hist_records) == 3
        assert all(h.history_type == "+" for h in hist_records)
        assert {h.language for h in hist_records} == {"ar", "en", "fr"}
