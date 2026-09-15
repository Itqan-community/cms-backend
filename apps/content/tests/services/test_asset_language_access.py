from model_bakery import baker

from apps.content.models import Asset, AssetLanguage, AssetVersion, CategoryChoice, StatusChoice
from apps.content.services.asset_language_access import (
    allowed_languages,
    assign_language_to_member,
    require_language,
    require_version_language,
)
from apps.core.ninja_utils.errors import ItqanError
from apps.core.permissions import PermissionChoice
from apps.core.tests.base import BaseTestCase
from apps.publishers.models import MemberLanguage, Publisher, PublisherMember
from apps.users.models import User


class AssetLanguageAccessTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.publisher = baker.make(Publisher)
        self.asset = baker.make(
            Asset,
            category=CategoryChoice.TRANSLATION,
            publisher=self.publisher,
            status=StatusChoice.READY,
            language="ar",
            slug="t1",
        )
        self.fr = AssetLanguage.objects.create(asset=self.asset, language="fr")
        self.es = AssetLanguage.objects.create(asset=self.asset, language="es")
        self.user = User.objects.create_user(email="editor@example.com", name="Editor")
        self.membership = baker.make(
            PublisherMember,
            user=self.user,
            publisher=self.publisher,
            status=PublisherMember.StatusChoice.ACTIVE,
        )

    def test_allowed_languages_where_assigned_should_return_only_those(self):
        # Arrange
        MemberLanguage.objects.create(member=self.membership, language="fr")

        # Act
        allowed = allowed_languages(self.user, self.asset)

        # Assert
        self.assertEqual({"fr"}, allowed)

    def test_allowed_languages_where_no_assignment_should_be_empty(self):
        # Act
        allowed = allowed_languages(self.user, self.asset)

        # Assert — an empty assignment means no languages, not all of them
        self.assertEqual(set(), allowed)

    def test_allowed_languages_where_bypass_permission_should_include_source(self):
        # Arrange — no assignments at all, only the bypass
        self.give_permission(self.user, PermissionChoice.PORTAL_ACCESS_ALL_LANGUAGES)
        self.user = User.objects.get(pk=self.user.pk)

        # Act
        allowed = allowed_languages(self.user, self.asset)

        # Assert — every language on the asset, the 'ar' source included
        self.assertEqual({"ar", "fr", "es"}, allowed)

    def test_allowed_languages_where_assignment_is_for_another_publisher_should_not_leak(self):
        # Arrange — same user, same language, but assigned on a different publisher
        other_publisher = baker.make(Publisher)
        other_member = baker.make(
            PublisherMember,
            user=self.user,
            publisher=other_publisher,
            status=PublisherMember.StatusChoice.ACTIVE,
        )
        MemberLanguage.objects.create(member=other_member, language="fr")

        # Act
        allowed = allowed_languages(self.user, self.asset)

        # Assert
        self.assertEqual(set(), allowed)

    def test_allowed_languages_where_membership_is_not_active_should_not_count(self):
        # Arrange
        self.membership.status = PublisherMember.StatusChoice.PENDING
        self.membership.save()
        MemberLanguage.objects.create(member=self.membership, language="fr")

        # Act
        allowed = allowed_languages(self.user, self.asset)

        # Assert
        self.assertEqual(set(), allowed)

    def test_require_language_where_not_assigned_should_raise_403(self):
        # Arrange
        MemberLanguage.objects.create(member=self.membership, language="fr")

        # Act / Assert
        with self.assertRaises(ItqanError) as ctx:
            require_language(self.user, self.asset, "es")
        self.assertEqual("language_not_assigned", ctx.exception.error_name)
        self.assertEqual(403, ctx.exception.status_code)

    def test_require_language_where_source_and_not_assigned_should_raise_403(self):
        # Arrange — assigned 'fr' only; the source is gated like any other language
        MemberLanguage.objects.create(member=self.membership, language="fr")

        # Act / Assert
        with self.assertRaises(ItqanError) as ctx:
            require_language(self.user, self.asset, "ar")
        self.assertEqual("language_not_assigned", ctx.exception.error_name)

    def test_require_version_language_where_legacy_version_should_resolve_to_source(self):
        # Arrange — a version with no asset_language belongs to the source ('ar').
        # bulk_create bypasses save(), which would otherwise backfill the language.
        legacy = AssetVersion(asset=self.asset, name="legacy", asset_language=None)
        AssetVersion.objects.bulk_create([legacy])
        legacy = AssetVersion.objects.get(name="legacy")
        MemberLanguage.objects.create(member=self.membership, language="fr")

        # Act / Assert — gated as the source language, not silently allowed
        self.assertIsNone(legacy.asset_language_id)
        self.assertEqual("ar", legacy.resolved_language)
        with self.assertRaises(ItqanError) as ctx:
            require_version_language(self.user, self.asset, legacy)
        self.assertEqual("language_not_assigned", ctx.exception.error_name)

    def test_assign_language_to_member_where_active_membership_should_create_row(self):
        # Act
        assign_language_to_member(self.user, self.asset, "es")

        # Assert
        self.assertTrue(MemberLanguage.objects.filter(member=self.membership, language="es").exists())

    def test_assign_language_to_member_where_called_twice_should_be_idempotent(self):
        # Act
        assign_language_to_member(self.user, self.asset, "es")
        assign_language_to_member(self.user, self.asset, "es")

        # Assert
        self.assertEqual(1, MemberLanguage.objects.filter(member=self.membership, language="es").count())

    def test_assign_language_to_member_where_no_membership_should_be_noop(self):
        # Arrange — Itqan staff acting on a publisher they are not a member of
        outsider = User.objects.create_user(email="staff@example.com", name="Staff", is_staff=True)

        # Act
        assign_language_to_member(outsider, self.asset, "es")

        # Assert
        self.assertFalse(MemberLanguage.objects.filter(language="es").exists())
