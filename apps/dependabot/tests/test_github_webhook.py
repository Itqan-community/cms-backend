"""Tests for the GitHub App installation webhook (consent entrypoint).

Signature unit tests are pure functions; event tests drive the real
endpoint (``POST /cms-api/dependabot/github/webhook/``) with signed
deliveries against the database. The webhook makes no outbound GitHub
calls, so no HTTP transport is involved at all.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from typing import Any

from django.test import SimpleTestCase, TestCase, override_settings
import pytest

from apps.core.ninja_utils.errors import ItqanError
from apps.dependabot.models import WatchedRepository
from apps.dependabot.services.github_webhook import (
    GitHubWebhookService,
    parse_webhook_payload,
    verify_webhook_signature,
)
from apps.dependabot.services.watched_repositories import WatchedRepositoryService

HOST = "github"
OWNER = "octo"
INSTALLATION_ID = 111
WEBHOOK_SECRET = "whsec_test_secret"
WEBHOOK_URL = "/cms-api/dependabot/github/webhook/"


def _sign(secret: str, body: bytes) -> str:
    return "sha256=" + hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


# --- Signature verification (pure) ---


def test_signature_where_valid_accepted():
    body = b'{"action":"created"}'
    assert verify_webhook_signature(secret=WEBHOOK_SECRET, payload=body, signature_header=_sign(WEBHOOK_SECRET, body))


@pytest.mark.parametrize(
    "header",
    [None, "", "sha256=", "md5=deadbeef", "sha256=deadbeef", "sha256=zzzz"],
)
def test_signature_where_missing_or_malformed_rejected(header):
    body = b'{"action":"created"}'
    assert not verify_webhook_signature(secret=WEBHOOK_SECRET, payload=body, signature_header=header)


def test_signature_where_wrong_secret_rejected():
    body = b'{"action":"created"}'
    assert not verify_webhook_signature(
        secret=WEBHOOK_SECRET, payload=body, signature_header=_sign("other-secret", body)
    )


def test_signature_where_empty_secret_never_verifies():
    body = b'{"action":"created"}'
    assert not verify_webhook_signature(secret="", payload=body, signature_header=_sign("", body))


def test_signature_where_tampered_body_rejected():
    body = b'{"action":"created"}'
    header = _sign(WEBHOOK_SECRET, body)
    assert not verify_webhook_signature(secret=WEBHOOK_SECRET, payload=b'{"action":"deleted"}', signature_header=header)


# --- Payload parsing (pure) ---


def test_parse_where_installation_created_shaped():
    parsed = parse_webhook_payload(
        event="installation",
        payload=json.dumps(
            {
                "action": "created",
                "installation": {"id": INSTALLATION_ID, "account": {"login": OWNER}},
                "repositories": [{"full_name": f"{OWNER}/a"}, {"full_name": f"{OWNER}/b"}],
            }
        ).encode(),
    )
    assert parsed.installation_id == INSTALLATION_ID
    assert [(r.owner, r.repository_name) for r in parsed.repositories] == [(OWNER, "a"), (OWNER, "b")]


@pytest.mark.parametrize(
    "payload",
    [
        b"{not json",
        b"[1, 2]",
        b"{}",
        json.dumps({"action": "created"}).encode(),
        json.dumps({"action": "created", "installation": {"id": 0}}).encode(),
        json.dumps({"action": "created", "installation": {"id": True}}).encode(),
        json.dumps(
            {"action": "created", "installation": {"id": 1}, "repositories": [{"full_name": "no-slash"}]}
        ).encode(),
        json.dumps({"action": "created", "installation": {"id": 1}, "repositories": "nope"}).encode(),
    ],
)
def test_parse_where_malformed_rejected(payload):
    with pytest.raises(ItqanError) as exc_info:
        parse_webhook_payload(event="installation", payload=payload)
    assert exc_info.value.error_name == "github_invalid_webhook_payload"
    assert exc_info.value.status_code == 400


def test_parse_where_missing_event_rejected():
    with pytest.raises(ItqanError) as exc_info:
        parse_webhook_payload(event=None, payload=b"{}")
    assert exc_info.value.error_name == "github_invalid_webhook_payload"


# --- Endpoint ---


class GitHubWebhookEndpointTest(TestCase):
    def setUp(self):
        super().setUp()
        self.watched = WatchedRepositoryService()

    def _settings(self, **overrides):
        values = {"ENABLE_ITQAN_DEPENDABOT": True, "GITHUB_WEBHOOK_SECRET": WEBHOOK_SECRET}
        values.update(overrides)
        return override_settings(**values)

    def _post(self, *, event: str | None, body: bytes, secret: str = WEBHOOK_SECRET, sign: bool = True):
        headers: dict[str, Any] = {"content_type": "application/json", "HTTP_X_GITHUB_DELIVERY": "test-delivery-1"}
        if event is not None:
            headers["HTTP_X_GITHUB_EVENT"] = event
        if sign:
            headers["HTTP_X_HUB_SIGNATURE_256"] = _sign(secret, body)
        return self.client.post(WEBHOOK_URL, data=body, **headers)

    def _deliver(self, *, event: str, payload: dict, **kwargs):
        return self._post(event=event, body=json.dumps(payload).encode(), **kwargs)

    def _rows(self):
        return {
            (w.owner, w.repository_name): w.status
            for w in WatchedRepository.objects.filter(host=HOST).order_by("owner", "repository_name")
        }

    def test_created_where_two_repos_opts_in_both(self):
        with self._settings():
            response = self._deliver(
                event="installation",
                payload={
                    "action": "created",
                    "installation": {"id": INSTALLATION_ID, "account": {"login": OWNER}},
                    "repositories": [{"full_name": f"{OWNER}/a"}, {"full_name": f"{OWNER}/b"}],
                },
            )
        assert response.status_code == 200
        assert response.json() == {"status": "processed", "event": "installation", "action": "created", "affected": 2}
        assert self._rows() == {(OWNER, "a"): "opted_in", (OWNER, "b"): "opted_in"}
        row = WatchedRepository.objects.get(owner=OWNER, repository_name="a")
        assert row.installation_id == INSTALLATION_ID

    def test_created_where_duplicate_delivery_is_idempotent(self):
        payload = {
            "action": "created",
            "installation": {"id": INSTALLATION_ID, "account": {"login": OWNER}},
            "repositories": [{"full_name": f"{OWNER}/a"}],
        }
        with self._settings():
            first = self._deliver(event="installation", payload=payload)
            second = self._deliver(event="installation", payload=payload)
        assert first.status_code == second.status_code == 200
        assert WatchedRepository.objects.count() == 1
        assert self._rows() == {(OWNER, "a"): "opted_in"}

    def test_repositories_added_where_new_repo_opted_in(self):
        self.watched.opt_in(host=HOST, owner=OWNER, repository_name="a", installation_id=INSTALLATION_ID)
        with self._settings():
            response = self._deliver(
                event="installation_repositories",
                payload={
                    "action": "added",
                    "installation": {"id": INSTALLATION_ID},
                    "repositories_added": [{"full_name": f"{OWNER}/b"}],
                },
            )
        assert response.status_code == 200
        assert self._rows() == {(OWNER, "a"): "opted_in", (OWNER, "b"): "opted_in"}

    def test_repositories_removed_where_row_preserved_as_opted_out(self):
        self.watched.opt_in(host=HOST, owner=OWNER, repository_name="a", installation_id=INSTALLATION_ID)
        self.watched.opt_in(host=HOST, owner=OWNER, repository_name="b", installation_id=INSTALLATION_ID)
        with self._settings():
            response = self._deliver(
                event="installation_repositories",
                payload={
                    "action": "removed",
                    "installation": {"id": INSTALLATION_ID},
                    "repositories_removed": [{"full_name": f"{OWNER}/b"}],
                },
            )
        assert response.status_code == 200
        assert response.json()["affected"] == 1
        assert self._rows() == {(OWNER, "a"): "opted_in", (OWNER, "b"): "opted_out"}
        assert WatchedRepository.objects.count() == 2

    def test_repositories_removed_where_unknown_repo_processed_idempotently(self):
        with self._settings():
            response = self._deliver(
                event="installation_repositories",
                payload={
                    "action": "removed",
                    "installation": {"id": INSTALLATION_ID},
                    "repositories_removed": [{"full_name": f"{OWNER}/ghost"}],
                },
            )
        assert response.status_code == 200
        assert response.json() == {
            "status": "processed",
            "event": "installation_repositories",
            "action": "removed",
            "affected": 0,
        }

    def test_removed_where_stale_replay_after_reinstall_leaves_newer_consent(self):
        old_installation = INSTALLATION_ID
        new_installation = INSTALLATION_ID + 1
        created_old = {
            "action": "created",
            "installation": {"id": old_installation, "account": {"login": OWNER}},
            "repositories": [{"full_name": f"{OWNER}/a"}],
        }
        created_new = {
            "action": "created",
            "installation": {"id": new_installation, "account": {"login": OWNER}},
            "repositories": [{"full_name": f"{OWNER}/a"}],
        }
        stale_removal = {
            "action": "removed",
            "installation": {"id": old_installation},
            "repositories_removed": [{"full_name": f"{OWNER}/a"}],
        }
        with self._settings():
            assert self._deliver(event="installation", payload=created_old).status_code == 200
            assert self._deliver(event="installation", payload=created_new).status_code == 200
            stale = self._deliver(event="installation_repositories", payload=stale_removal)
        assert stale.status_code == 200
        assert stale.json()["affected"] == 0
        row = WatchedRepository.objects.get(host=HOST, owner=OWNER, repository_name="a")
        assert row.status == WatchedRepository.StatusChoice.OPTED_IN
        assert row.installation_id == new_installation

    def test_suspend_where_only_opted_in_rows_suspended(self):
        self.watched.opt_in(host=HOST, owner=OWNER, repository_name="a", installation_id=INSTALLATION_ID)
        self.watched.opt_in(host=HOST, owner=OWNER, repository_name="b", installation_id=INSTALLATION_ID)
        self.watched.opt_out(host=HOST, owner=OWNER, repository_name="b")
        with self._settings():
            response = self._deliver(
                event="installation", payload={"action": "suspend", "installation": {"id": INSTALLATION_ID}}
            )
        assert response.status_code == 200
        assert self._rows() == {(OWNER, "a"): "suspended", (OWNER, "b"): "opted_out"}

    def test_unsuspend_where_opted_out_never_revived(self):
        self.watched.opt_in(host=HOST, owner=OWNER, repository_name="a", installation_id=INSTALLATION_ID)
        self.watched.opt_in(host=HOST, owner=OWNER, repository_name="b", installation_id=INSTALLATION_ID)
        self.watched.opt_out(host=HOST, owner=OWNER, repository_name="b")
        self.watched.suspend_installation(host=HOST, installation_id=INSTALLATION_ID)
        assert self._rows() == {(OWNER, "a"): "suspended", (OWNER, "b"): "opted_out"}
        with self._settings():
            response = self._deliver(
                event="installation", payload={"action": "unsuspend", "installation": {"id": INSTALLATION_ID}}
            )
        assert response.status_code == 200
        assert response.json()["affected"] == 1
        assert self._rows() == {(OWNER, "a"): "opted_in", (OWNER, "b"): "opted_out"}

    def test_deleted_where_rows_preserved_as_opted_out(self):
        self.watched.opt_in(host=HOST, owner=OWNER, repository_name="a", installation_id=INSTALLATION_ID)
        with self._settings():
            response = self._deliver(
                event="installation",
                payload={
                    "action": "deleted",
                    "installation": {"id": INSTALLATION_ID, "account": {"login": OWNER}},
                    "repositories": [{"full_name": f"{OWNER}/a"}],
                },
            )
        assert response.status_code == 200
        assert self._rows() == {(OWNER, "a"): "opted_out"}
        assert WatchedRepository.objects.count() == 1

    def test_unsupported_event_where_ignored_without_rows(self):
        with self._settings():
            response = self._deliver(event="push", payload={"ref": "refs/heads/main"})
        assert response.status_code == 200
        assert response.json()["status"] == "ignored"
        assert WatchedRepository.objects.count() == 0

    def test_unknown_action_where_ignored(self):
        with self._settings():
            response = self._deliver(
                event="installation",
                payload={"action": "new_permissions_accepted", "installation": {"id": INSTALLATION_ID}},
            )
        assert response.status_code == 200
        assert response.json()["status"] == "ignored"

    def test_malformed_json_where_rejected(self):
        body = b"{not json"
        with self._settings():
            response = self._post(event="installation", body=body)
        assert response.status_code == 400
        assert response.json()["error_name"] == "github_invalid_webhook_payload"

    def test_missing_signature_where_rejected(self):
        with self._settings():
            response = self._post(
                event="installation",
                body=json.dumps({"action": "created", "installation": {"id": 1}}).encode(),
                sign=False,
            )
        assert response.status_code == 401
        assert response.json()["error_name"] == "github_webhook_signature_invalid"

    def test_invalid_signature_where_rejected(self):
        with self._settings():
            response = self._post(
                event="installation",
                body=json.dumps({"action": "created", "installation": {"id": 1}}).encode(),
                secret="wrong-secret",
            )
        assert response.status_code == 401
        assert WatchedRepository.objects.count() == 0

    def test_flag_disabled_where_ignored_without_rows(self):
        with self._settings(ENABLE_ITQAN_DEPENDABOT=False):
            response = self._deliver(
                event="installation",
                payload={
                    "action": "created",
                    "installation": {"id": INSTALLATION_ID, "account": {"login": OWNER}},
                    "repositories": [{"full_name": f"{OWNER}/a"}],
                },
            )
        assert response.status_code == 200
        assert response.json()["status"] == "ignored"
        assert WatchedRepository.objects.count() == 0


class GitHubWebhookSecrecyTest(SimpleTestCase):
    def test_rejected_delivery_does_not_leak_secret(self):
        canary = "whsec_CANARY_DO_NOT_LEAK"
        body = json.dumps({"action": "created", "installation": {"id": 1}}).encode()
        with override_settings(ENABLE_ITQAN_DEPENDABOT=True, GITHUB_WEBHOOK_SECRET=canary):
            with self.assertLogs("apps.dependabot.services.github_webhook", level=logging.DEBUG) as cm:
                service = GitHubWebhookService()
                with pytest.raises(ItqanError) as exc_info:
                    service.handle(event="installation", payload=body, signature_header="sha256=wrong", secret=canary)
        assert exc_info.value.error_name == "github_webhook_signature_invalid"
        assert canary not in exc_info.value.message
        assert canary not in str(exc_info.value.extra)
        for record in cm.records:
            assert canary not in record.getMessage()
