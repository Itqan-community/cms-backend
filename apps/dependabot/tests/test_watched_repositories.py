"""Tests for the watched-repository opt-in persistence layer.

Pure database tests using plain ``django.test.TestCase`` (no storage, API,
or network dependencies). Model, repository, and service behavior are
covered through the service's public API plus direct repository checks.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from apps.core.ninja_utils.errors import ItqanError
from apps.dependabot.models import WatchedRepository
from apps.dependabot.repositories.watched_repository import WatchedRepositoryRepository
from apps.dependabot.services.watched_repositories import WatchedRepositoryService
from apps.users.models import User

HOST = "github"
OWNER = "itqan-community"
REPO = "sample-app"


class WatchedRepositoryOptInTest(TestCase):
    def setUp(self):
        super().setUp()
        self.repo = WatchedRepositoryRepository()
        self.service = WatchedRepositoryService(repo=self.repo)
        self.user = User.objects.create_user(email="staff@example.com", name="Staff")

    def _opt_in(self, **kwargs):
        values = {
            "host": HOST,
            "owner": OWNER,
            "repository_name": REPO,
            "installation_id": 111,
        }
        values.update(kwargs)
        return self.service.opt_in(**values)

    # --- Create / idempotency ---

    def test_opt_in_where_new_creates_opted_in_row(self):
        watched = self._opt_in(installation_id=111, opted_in_by=self.user)

        assert watched.pk is not None
        assert watched.host == HOST
        assert watched.owner == OWNER
        assert watched.repository_name == REPO
        assert watched.installation_id == 111
        assert watched.status == WatchedRepository.StatusChoice.OPTED_IN
        assert watched.is_opted_in is True
        assert watched.default_branch == "main"
        assert watched.opted_in_by_id == self.user.pk
        assert watched.opted_in_at is not None
        assert watched.last_manifest_sha is None
        assert watched.last_lockfile_sha is None
        assert watched.last_checked_at is None

    def test_opt_in_where_repeated_is_idempotent_and_refreshes(self):
        first = self._opt_in(installation_id=111)

        second = self.service.opt_in(
            host=HOST,
            owner=OWNER,
            repository_name=REPO,
            installation_id=222,
            default_branch="develop",
        )

        assert WatchedRepository.objects.count() == 1
        assert second.pk == first.pk
        assert second.status == WatchedRepository.StatusChoice.OPTED_IN
        assert second.installation_id == 222
        assert second.default_branch == "develop"
        assert second.opted_in_at >= first.opted_in_at

    def test_opt_in_where_repeated_without_actor_preserves_actor(self):
        self.service.opt_in(
            host=HOST,
            owner=OWNER,
            repository_name=REPO,
            installation_id=111,
            opted_in_by=self.user,
        )
        second = self.service.opt_in(
            host=HOST,
            owner=OWNER,
            repository_name=REPO,
            installation_id=111,
        )
        assert second.opted_in_by_id == self.user.pk

    def test_model_where_duplicate_identity_violates_unique_constraint(self):
        self._opt_in()
        with self.assertRaises(IntegrityError):
            WatchedRepository.objects.create(
                host=HOST,
                owner=OWNER,
                repository_name=REPO,
                installation_id=999,
            )

    def test_model_where_non_github_host_violates_github_only_constraint(self):
        self._opt_in()
        # Inner savepoint: without it the caught IntegrityError would poison
        # the TestCase transaction for the follow-up assertion query.
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                WatchedRepository.objects.create(
                    host="gitea",
                    owner=OWNER,
                    repository_name=REPO,
                    installation_id=999,
                )
        assert WatchedRepository.objects.count() == 1

    # --- Listing ---

    def test_list_opted_in_where_mixed_statuses_returns_only_opted_in(self):
        self._opt_in()
        self.service.opt_in(host=HOST, owner=OWNER, repository_name="leaving", installation_id=1)
        self.service.opt_out(host=HOST, owner=OWNER, repository_name="leaving")
        self.service.opt_in(host=HOST, owner=OWNER, repository_name="paused", installation_id=1)
        self.service.suspend(host=HOST, owner=OWNER, repository_name="paused")

        slugs = sorted(w.repository_name for w in self.repo.list_opted_in(HOST))
        assert slugs == [REPO]

    # --- Opt-out / suspend preserve history ---

    def test_opt_out_where_opted_in_preserves_row(self):
        watched = self._opt_in(installation_id=111)

        result = self.service.opt_out(host=HOST, owner=OWNER, repository_name=REPO)

        assert result.pk == watched.pk
        assert result.status == WatchedRepository.StatusChoice.OPTED_OUT
        assert result.is_opted_in is False
        assert WatchedRepository.objects.count() == 1
        # History survives the flip.
        assert result.installation_id == 111
        assert self.repo.get_by_owner_repo(HOST, OWNER, REPO) is not None

    def test_re_opt_in_where_opted_out_restores_without_new_row(self):
        self._opt_in(installation_id=111)
        self.service.opt_out(host=HOST, owner=OWNER, repository_name=REPO)

        restored = self.service.opt_in(host=HOST, owner=OWNER, repository_name=REPO, installation_id=333)

        assert WatchedRepository.objects.count() == 1
        assert restored.status == WatchedRepository.StatusChoice.OPTED_IN
        assert restored.is_opted_in is True
        assert restored.installation_id == 333
        assert list(self.repo.list_opted_in(HOST).values_list("repository_name", flat=True)) == [REPO]

    def test_suspend_where_opted_in_is_not_treated_as_opted_in(self):
        self._opt_in()
        suspended = self.service.suspend(host=HOST, owner=OWNER, repository_name=REPO)

        assert suspended.status == WatchedRepository.StatusChoice.SUSPENDED
        assert suspended.is_opted_in is False
        assert WatchedRepository.objects.count() == 1
        assert list(self.repo.list_opted_in(HOST)) == []
        with self.assertRaises(ItqanError) as ctx:
            self.service.require_opted_in(host=HOST, owner=OWNER, repository_name=REPO)
        assert ctx.exception.error_name == "dependabot_repository_not_found"

    def test_opt_out_where_unknown_raises_not_found(self):
        with self.assertRaises(ItqanError) as ctx:
            self.service.opt_out(host=HOST, owner="ghost", repository_name="nothing")
        assert ctx.exception.error_name == "dependabot_repository_not_found"
        assert ctx.exception.status_code == 404

    def test_suspend_where_unknown_raises_not_found(self):
        with self.assertRaises(ItqanError) as ctx:
            self.service.suspend(host=HOST, owner="ghost", repository_name="nothing")
        assert ctx.exception.error_name == "dependabot_repository_not_found"

    # --- Atomic installation transitions (single conditional UPDATE) ---

    def test_suspend_installation_where_single_statement_transitions_matching_rows(self):
        self._opt_in(installation_id=111)
        self.service.opt_in(host=HOST, owner=OWNER, repository_name="other", installation_id=111)
        self.service.opt_out(host=HOST, owner=OWNER, repository_name="other")

        with self.assertNumQueries(1):
            transitioned = self.service.suspend_installation(host=HOST, installation_id=111)

        assert transitioned == 1
        statuses = dict(WatchedRepository.objects.filter(host=HOST).values_list("repository_name", "status"))
        assert statuses == {REPO: "suspended", "other": "opted_out"}

    def test_suspend_installation_where_redelivery_transitions_zero(self):
        self._opt_in(installation_id=111)
        assert self.service.suspend_installation(host=HOST, installation_id=111) == 1
        assert self.service.suspend_installation(host=HOST, installation_id=111) == 0

    def test_unsuspend_installation_where_only_suspended_flip_and_history_kept(self):
        before = self._opt_in(installation_id=111, default_branch="develop", opted_in_by=self.user)
        self.service.suspend_installation(host=HOST, installation_id=111)

        with self.assertNumQueries(1):
            transitioned = self.service.unsuspend_installation(host=HOST, installation_id=111)

        assert transitioned == 1
        restored = self.repo.get_by_owner_repo(HOST, OWNER, REPO)
        assert restored.status == WatchedRepository.StatusChoice.OPTED_IN
        assert restored.opted_in_at >= before.opted_in_at
        assert restored.opted_in_by_id == self.user.pk
        assert restored.default_branch == "develop"

    def test_opt_out_installation_where_redelivery_transitions_zero(self):
        self._opt_in(installation_id=111)
        assert self.service.opt_out_installation(host=HOST, installation_id=111) == 1
        assert self.service.opt_out_installation(host=HOST, installation_id=111) == 0
        assert WatchedRepository.objects.count() == 1

    def test_opt_out_from_installation_where_stale_installation_leaves_newer_consent(self):
        self.service.opt_in(host=HOST, owner=OWNER, repository_name=REPO, installation_id=111)
        self.service.opt_in(host=HOST, owner=OWNER, repository_name=REPO, installation_id=222)

        assert (
            self.service.opt_out_from_installation(host=HOST, owner=OWNER, repository_name=REPO, installation_id=111)
            is False
        )
        current = self.repo.get_by_owner_repo(HOST, OWNER, REPO)
        assert current.status == WatchedRepository.StatusChoice.OPTED_IN
        assert current.installation_id == 222

    def test_opt_out_from_installation_where_matching_transitions(self):
        self.service.opt_in(host=HOST, owner=OWNER, repository_name=REPO, installation_id=111)

        assert (
            self.service.opt_out_from_installation(host=HOST, owner=OWNER, repository_name=REPO, installation_id=111)
            is True
        )
        assert self.repo.get_by_owner_repo(HOST, OWNER, REPO).status == WatchedRepository.StatusChoice.OPTED_OUT

    def test_opt_out_from_installation_where_unknown_returns_false(self):
        assert (
            self.service.opt_out_from_installation(
                host=HOST, owner="ghost", repository_name="nothing", installation_id=111
            )
            is False
        )

    # --- Discovery state ---

    def test_record_discovery_where_opted_in_persists_state(self):
        self._opt_in()
        checked_at = datetime(2026, 9, 6, 12, 0, 0, tzinfo=UTC)

        result = self.service.record_discovery(
            host=HOST,
            owner=OWNER,
            repository_name=REPO,
            last_manifest_sha="a" * 40,
            last_lockfile_sha="b" * 40,
            last_checked_at=checked_at,
        )

        assert result.last_manifest_sha == "a" * 40
        assert result.last_lockfile_sha == "b" * 40
        assert result.last_checked_at == checked_at
        assert result.status == WatchedRepository.StatusChoice.OPTED_IN

    def test_record_discovery_where_absent_files_stores_nulls(self):
        self._opt_in()

        result = self.service.record_discovery(
            host=HOST,
            owner=OWNER,
            repository_name=REPO,
            last_manifest_sha=None,
            last_lockfile_sha=None,
            last_checked_at=None,
        )

        before = timezone.now() - timedelta(seconds=5)
        assert result.last_manifest_sha is None
        assert result.last_lockfile_sha is None
        assert result.last_checked_at is not None
        assert result.last_checked_at >= before

    def test_record_discovery_where_branch_resolved_overwrites_initial_guess(self):
        watched = self._opt_in()
        assert watched.default_branch == "main"

        result = self.service.record_discovery(
            host=HOST,
            owner=OWNER,
            repository_name=REPO,
            last_manifest_sha=None,
            last_lockfile_sha=None,
            last_checked_at=None,
            default_branch="develop",
        )

        assert result.default_branch == "develop"

    def test_record_discovery_where_branch_omitted_preserves_stored_value(self):
        self.service.opt_in(
            host=HOST,
            owner=OWNER,
            repository_name=REPO,
            installation_id=111,
            default_branch="develop",
        )

        result = self.service.record_discovery(
            host=HOST,
            owner=OWNER,
            repository_name=REPO,
            last_manifest_sha=None,
            last_lockfile_sha=None,
            last_checked_at=None,
        )

        assert result.default_branch == "develop"

    def test_record_discovery_where_branch_invalid_raises(self):
        self._opt_in()
        with self.assertRaises(ItqanError) as ctx:
            self.service.record_discovery(
                host=HOST,
                owner=OWNER,
                repository_name=REPO,
                last_manifest_sha=None,
                last_lockfile_sha=None,
                last_checked_at=None,
                default_branch="  ",
            )
        assert ctx.exception.error_name == "dependabot_invalid_repository"

    def test_record_discovery_where_not_opted_in_raises(self):
        self._opt_in()
        self.service.opt_out(host=HOST, owner=OWNER, repository_name=REPO)

        with self.assertRaises(ItqanError) as ctx:
            self.service.record_discovery(
                host=HOST,
                owner=OWNER,
                repository_name=REPO,
                last_manifest_sha="a" * 40,
                last_lockfile_sha=None,
                last_checked_at=None,
            )
        assert ctx.exception.error_name == "dependabot_repository_not_found"

    # --- Input validation ---

    def test_opt_in_where_identity_invalid_raises(self):
        bad_inputs = [
            {"owner": "", "repository_name": REPO},
            {"owner": "  ", "repository_name": REPO},
            {"owner": "org/sub", "repository_name": REPO},
            {"owner": OWNER, "repository_name": ""},
            {"owner": OWNER, "repository_name": "a/b"},
            {"owner": OWNER, "repository_name": REPO, "installation_id": 0},
            {"owner": OWNER, "repository_name": REPO, "installation_id": -1},
            {"owner": OWNER, "repository_name": REPO, "installation_id": True},
            {"owner": OWNER, "repository_name": REPO, "installation_id": "111"},
            {"owner": OWNER, "repository_name": REPO, "default_branch": ""},
            {"host": "gitlab", "owner": OWNER, "repository_name": REPO},
        ]
        for kwargs in bad_inputs:
            with self.subTest(kwargs=kwargs):
                values = {"host": HOST, "installation_id": 111, **kwargs}
                with self.assertRaises(ItqanError) as ctx:
                    self.service.opt_in(**values)
                assert ctx.exception.error_name == "dependabot_invalid_repository"
        assert WatchedRepository.objects.count() == 0

    def test_record_discovery_where_sha_malformed_raises(self):
        self._opt_in()
        with self.assertRaises(ItqanError) as ctx:
            self.service.record_discovery(
                host=HOST,
                owner=OWNER,
                repository_name=REPO,
                last_manifest_sha="not a sha!!",
                last_lockfile_sha=None,
                last_checked_at=None,
            )
        assert ctx.exception.error_name == "dependabot_invalid_repository"

    # --- Model hygiene ---

    def test_model_where_installation_id_is_stored_and_indexed(self):
        watched = self._opt_in(installation_id=424242)

        fetched = WatchedRepository.objects.get(installation_id=424242)
        assert fetched.pk == watched.pk
        installation_field = WatchedRepository._meta.get_field("installation_id")
        assert installation_field.db_index is True

    def test_model_where_no_secret_or_token_fields_exist(self):
        field_names = {field.name for field in WatchedRepository._meta.get_fields()}
        for forbidden in ("token", "jwt", "secret", "password", "private_key", "api_key", "apikey"):
            assert forbidden not in field_names, f"unexpected secret-like field: {forbidden}"
        assert "installation_id" in field_names
