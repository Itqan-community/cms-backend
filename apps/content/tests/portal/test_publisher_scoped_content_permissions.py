from model_bakery import baker

from apps.content.services.asset_language_access import allowed_languages
from apps.content.tests.portal.test_asset_review import AssetReviewApiBaseTest
from apps.core.permissions import PermissionChoice
from apps.publishers.models import MemberLanguage, Publisher, PublisherMember
from apps.publishers.tests.services.test_effective_permissions import role
from apps.users.models import User

REVIEW = PermissionChoice.PORTAL_REVIEW_CONTENT
ALL_LANGUAGES = PermissionChoice.PORTAL_ACCESS_ALL_LANGUAGES


class PublisherScopedContentPermissionTest(AssetReviewApiBaseTest):
    """``self.publisher`` owns the asset; ``self.other`` is a second publisher the user also belongs to."""

    def setUp(self):
        super().setUp()
        self.other = baker.make(Publisher, name="Other")
        self.member = User.objects.create_user(email="scoped@example.com", name="Scoped")

    def _join(self, publisher: Publisher, *permissions: PermissionChoice) -> PublisherMember:
        group = role(publisher, PermissionChoice.PORTAL_ACCESS, *permissions)
        self.member.groups.add(group)  # legacy sync, must not leak across publishers
        return PublisherMember.objects.create(
            user=self.member, publisher=publisher, group=group, status=PublisherMember.StatusChoice.ACTIVE
        )

    def test_review_allowed_when_role_at_this_publisher_grants_it(self):
        membership = self._join(self.publisher, REVIEW)
        MemberLanguage.objects.create(member=membership, language="fr")
        self.authenticate_user(self.member, HTTP_X_TENANT=str(self.publisher.id))

        response = self.client.get(self._changes_url("?language=fr"))

        self.assertEqual(200, response.status_code, response.content)

    def test_review_denied_when_permission_held_only_at_other_publisher(self):
        membership = self._join(self.publisher)
        MemberLanguage.objects.create(member=membership, language="fr")
        self._join(self.other, REVIEW)
        self.authenticate_user(self.member, HTTP_X_TENANT=str(self.publisher.id))

        response = self.client.get(self._changes_url("?language=fr"))

        self.assertEqual(403, response.status_code, response.content)

    def test_all_languages_access_applies_at_the_assets_publisher(self):
        self._join(self.publisher, ALL_LANGUAGES)

        self.assertEqual({"ar", "fr"}, allowed_languages(self.member, self.asset))

    def test_all_languages_access_is_per_publisher(self):
        membership = self._join(self.publisher)
        MemberLanguage.objects.create(member=membership, language="fr")
        self._join(self.other, ALL_LANGUAGES)

        self.assertEqual({"fr"}, allowed_languages(self.member, self.asset))
