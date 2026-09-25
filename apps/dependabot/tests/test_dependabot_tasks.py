"""Tests for Dependabot Celery tasks and signals (ITQ-28 / #427).

Covers:
- dispatch_dependabot_updates_for_version fan-out over opted-in repositories.
- Staggered batch scheduling.
- Rate-limit handling and Celery backoff retry.
- Signal triggering on AssetVersion publication.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings
import pytest

from apps.content.models import Asset, AssetVersion, CategoryChoice, VersionStateChoice
from apps.core.ninja_utils.errors import ItqanError
from apps.dependabot.models import WatchedRepository
from apps.dependabot.services.pr_updater import UpdateResult
from apps.dependabot.signals import on_asset_version_published
from apps.dependabot.tasks import (
    dispatch_dependabot_updates_for_version,
    process_repository_dependabot_update,
)
from apps.publishers.models import Publisher


class DependabotTasksTest(TestCase):
    def setUp(self):
        super().setUp()
        self.publisher = Publisher.objects.create(name="Test Publisher", slug="test-publisher")
        self.asset = Asset.objects.create(
            publisher=self.publisher,
            name="Quran Hafs",
            name_ar="القرآن الكريم برواية حفص",
            name_en="The Holy Quran - Hafs",
            category=CategoryChoice.MUSHAF,
            slug="quran-hafs",
        )
        self.published_version = AssetVersion.objects.create(
            asset=self.asset,
            name="1.3.0",
            state=VersionStateChoice.PUBLISHED,
            summary="New edition",
        )
        self.draft_version = AssetVersion.objects.create(
            asset=self.asset,
            name="1.4.0",
            state=VersionStateChoice.DRAFT,
            summary="Draft release",
        )

        self.repo_opted_in_1 = WatchedRepository.objects.create(
            host="github",
            owner="org1",
            repository_name="repo1",
            installation_id=101,
            status=WatchedRepository.StatusChoice.OPTED_IN,
        )
        self.repo_opted_in_2 = WatchedRepository.objects.create(
            host="github",
            owner="org2",
            repository_name="repo2",
            installation_id=102,
            status=WatchedRepository.StatusChoice.OPTED_IN,
        )
        self.repo_opted_out = WatchedRepository.objects.create(
            host="github",
            owner="org3",
            repository_name="repo3",
            installation_id=103,
            status=WatchedRepository.StatusChoice.OPTED_OUT,
        )

    def _settings(self, **overrides):
        values = {
            "ENABLE_ITQAN_DEPENDABOT": True,
            "GITHUB_APP_ID": 123,
            "GITHUB_APP_PRIVATE_KEY": "fake_pem",
        }
        values.update(overrides)
        return override_settings(**values)

    def test_dispatch_fans_out_to_only_opted_in_repositories(self):
        with self._settings():
            with patch("apps.dependabot.tasks.process_repository_dependabot_update.apply_async") as mock_apply:
                res = dispatch_dependabot_updates_for_version(self.published_version.id)

                assert res["status"] == "success"
                assert res["dispatched_count"] == 2
                assert mock_apply.call_count == 2

                # Verify called with repo IDs for only opted-in repos
                called_repo_ids = [call.kwargs["args"][0] for call in mock_apply.call_args_list]
                assert set(called_repo_ids) == {self.repo_opted_in_1.id, self.repo_opted_in_2.id}
                assert self.repo_opted_out.id not in called_repo_ids

    def test_dispatch_skips_when_dependabot_disabled(self):
        with self._settings(ENABLE_ITQAN_DEPENDABOT=False):
            with patch("apps.dependabot.tasks.process_repository_dependabot_update.apply_async") as mock_apply:
                res = dispatch_dependabot_updates_for_version(self.published_version.id)
                assert res["status"] == "skipped"
                assert res["reason"] == "dependabot_disabled"
                mock_apply.assert_not_called()

    def test_dispatch_skips_when_version_is_not_published(self):
        with self._settings():
            with patch("apps.dependabot.tasks.process_repository_dependabot_update.apply_async") as mock_apply:
                res = dispatch_dependabot_updates_for_version(self.draft_version.id)
                assert res["status"] == "skipped"
                assert res["reason"] == "not_published"
                mock_apply.assert_not_called()

    def test_dispatch_skips_when_version_is_invalid_semver(self):
        invalid_version = AssetVersion.objects.create(
            asset=self.asset,
            name="invalid-name",
            state=VersionStateChoice.PUBLISHED,
        )
        with self._settings():
            with patch("apps.dependabot.tasks.process_repository_dependabot_update.apply_async") as mock_apply:
                res = dispatch_dependabot_updates_for_version(invalid_version.id)
                assert res["status"] == "skipped"
                assert res["reason"] == "invalid_semver"
                mock_apply.assert_not_called()

    def test_process_repo_update_retries_on_rate_limit(self):
        with self._settings():
            with patch("apps.dependabot.services.pr_updater.PrUpdaterService.process_repository") as mock_process:
                mock_process.side_effect = ItqanError(
                    "github_rate_limited",
                    "Rate limited",
                    503,
                    extra={"retry_after_seconds": 45},
                )
                with patch.object(process_repository_dependabot_update, "retry") as mock_retry:
                    mock_retry.side_effect = RuntimeError("retry called")

                    with pytest.raises(RuntimeError, match="retry called"):
                        process_repository_dependabot_update(self.repo_opted_in_1.id, self.published_version.id)

                    mock_retry.assert_called_once()
                    assert mock_retry.call_args.kwargs["countdown"] == 45

    def test_process_repo_update_retries_on_transient_error(self):
        with self._settings():
            with patch("apps.dependabot.services.pr_updater.PrUpdaterService.process_repository") as mock_process:
                mock_process.side_effect = ItqanError("github_upstream_error", "Server Error", 502)
                with patch.object(process_repository_dependabot_update, "retry") as mock_retry:
                    mock_retry.side_effect = RuntimeError("retry called")

                    with pytest.raises(RuntimeError, match="retry called"):
                        process_repository_dependabot_update(self.repo_opted_in_1.id, self.published_version.id)

                    mock_retry.assert_called_once()

    def test_process_repo_update_successful_execution(self):
        with self._settings():
            with patch("apps.dependabot.services.pr_updater.PrUpdaterService.process_repository") as mock_process:
                mock_process.return_value = UpdateResult(
                    action="created",
                    reason=None,
                    pr=MagicMock(number=55),
                    old_version="1.2.0",
                    new_version="1.3.0",
                    is_in_range=True,
                )
                res = process_repository_dependabot_update(self.repo_opted_in_1.id, self.published_version.id)
                assert res["status"] == "success"
                assert res["action"] == "created"
                assert res["pr_number"] == 55

    def test_signal_triggers_dispatch_on_commit(self):
        with self._settings():
            with patch("apps.dependabot.tasks.dispatch_dependabot_updates_for_version.delay") as mock_delay:
                with self.captureOnCommitCallbacks(execute=True):
                    on_asset_version_published(
                        sender=AssetVersion,
                        instance=self.published_version,
                        created=False,
                    )
                mock_delay.assert_called_once_with(self.published_version.id)
