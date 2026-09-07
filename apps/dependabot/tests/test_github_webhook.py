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
import unittest
import uuid

from django.test import SimpleTestCase, TestCase, override_settings
import pytest

from apps.core.ninja_utils.errors import ItqanError
from apps.dependabot.models import WatchedRepository
from apps.dependabot.services.github_client import GitHubContentsClient
from apps.dependabot.services.github_token import GitHubInstallationTokenService
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
GITHUB_APP_ID = 12345
GITHUB_APP_PRIVATE_KEY = """\
-----BEGIN PRIVATE KEY-----
MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQDK0qSLkPZnq7Y7
5hQ9WpmW2kkn7r3gzs/uKM2Qi3hPU92wdgsp7HbMHUyKADQO41H5MuvpyDj2fj+E
rS/t9zJwdRritvsgu7JOj/REMUw986NTdE9rr5Qnx7BUlUyIPrkjjRDvBCtNadrH
HCClIbCl6DXXKjWwTy7CnmmgTCCfFjEA19rnh9vx6xqBq7vqTTtHxeVZhEnA5Mwy
lDSdCh3ZOc9oqdevOirCXSNO512o49Q+c+jw7S/AhKTWrXdTPkSsd0SJJuq0LLOn
mWLLf+ovicF6eHkwxkoU9ago7GL8Jo3aKy3IK8dOokEFlIhJeDfAYXz1anwaL3x1
wPY8HUk5AgMBAAECggEANC0vNlZDBVV3qn4ca9IwW83o7vRsdXZOqHJnu40dlK67
A6fCZHUX9Jd+9qtpuQDCuExgw0IGYWcF+SBCicHDgImnsnYnMXsHuk0vJhHWjsNs
G057FfVTtE4bLw8/YndcUmh6WDqm1yHprbovLbv2gR+1JhaOPD6KhXeSLbIX3ES3
z5DQafEfG16Y5tQtStKTQ8N0NqdRPD+sBltAbIIrjUx1SRZ1Q2c0ePTpGwOE8TYv
URhvxoTjDPfnxfOKUAwMnm1kiUOQyHdAxDd0Ilg/bvqfxjPg3CddXZXipi182LzT
mVkf3TFIOE6LGOMRAuVMQCfp7sp5ZR2BF+3FAuq/dwKBgQD9LgiCjQ/oGipyo2BA
gof+Y2A7tYnC5Ku2UvwO9YY6IgwFdRO2QXguDHgmn+cxPJ2BCucQneGajWK+klPu
TOKReLxasDpFLemRBW14Ba4ehpwk122iklwgdOjez5EN/5UUmteL2i+bdjxbLGKW
MoSdMS/vXv7zN9JEepkuZ86ghwKBgQDNFQL8wAdA9s0n6UWciZxYXPEtMDCs/qHO
uhPH+IO2xyzmOVjbRY7JmvGwEoBp0TXlKAduEqN0jj8gKMz2YYblmWOS5krq7nbN
0mqXtcGcyE5BljWS27m+SbsbRHnroHUic38h5AG486pCVF4oBmF7m1ibFVT9opV9
FA1aanf4PwKBgDFEUPGeo5bF6LawJh3HiNEu414bIHilaOis01HR41HSqEYzlydj
LBDB6muRuDpzki63QWmRX4Jkuu9cqCp6Gai3Nufq3RvzKD1JMhkl+dEE3sOojDQT
iQvj1CDvgUmZD5iX3RPg3FzDMFGJnJGfuQChvrM06CXKGgerV72ZA7NnAoGALkTp
UaD5gfysuK52mCSr83u0ph9TPBSO6RcuU1WMUfaJ+L9DfuUom++rS7BA7J7Y7ASl
+H2YBzn4oAbUh1nll3ON9ZyjlnGKuFEa33OQZREEJuP+3k1YkMgNwM8oOrMO+mDY
dAr/IH1JEoH6ZElcQQkBaqvbawX9eCTIBngy7P0CgYEAgWdz+l8LODDtnG5B6obW
zFJY/1/HnL2lAVYpH1PbXtY6pYdCQGo67pmSdPe0iX67dFNt+kVBQsapqVG3az28
iKA/al4RaxdPXoN3Envp9XFgmi1aFc2VCvPUppfDZxnBwgqyTPIHm/OA0vjuN2qP
klyH69JEzGm27oxNxkvOCpA=
-----END PRIVATE KEY-----
"""
STUB_TOKEN = "ghs_test_stub_token"
FAR_FUTURE = __import__("datetime").datetime(2099, 1, 1, tzinfo=__import__("datetime").timezone.utc)


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
        # Patch GitHubContentsClient so the real endpoint never makes outbound calls.
        import httpx

        from apps.dependabot.services.github_client import GitHubContentsClient
        from apps.dependabot.services.github_token import GitHubInstallationTokenService, clear_installation_token_cache

        clear_installation_token_cache()

        def _mock_handler(request: httpx.Request) -> httpx.Response:
            path = str(request.url.path)
            if path.endswith("/access_tokens"):
                return httpx.Response(201, json={"token": STUB_TOKEN, "expires_at": FAR_FUTURE.isoformat()})
            if "/app/installations/" in path and "/access_tokens" not in path:
                # Mirror the DB state: if any row for this installation is
                # suspended, report the installation as suspended so that
                # legitimate unsuspend events reconcile correctly.
                is_suspended = WatchedRepository.objects.filter(
                    installation_id=INSTALLATION_ID, status="suspended"
                ).exists()
                if is_suspended:
                    return httpx.Response(
                        200,
                        json={
                            "id": INSTALLATION_ID,
                            "suspended_by": {"login": "admin"},
                            "suspended_at": "2026-09-06T12:00:00Z",
                        },
                    )
                return httpx.Response(200, json={"id": INSTALLATION_ID, "suspended_by": None})
            if "/repos/" in path and "/contents/" not in path:
                return httpx.Response(200, json={"default_branch": "main"})
            return httpx.Response(404)

        mock_transport = httpx.MockTransport(_mock_handler)
        self._mock_client = httpx.Client(transport=mock_transport)
        self._mock_contents = GitHubContentsClient(
            token_service=GitHubInstallationTokenService(http_client=self._mock_client),
            http_client=self._mock_client,
        )
        self._patcher = unittest.mock.patch(
            "apps.dependabot.services.github_webhook.GitHubContentsClient",
            return_value=self._mock_contents,
        )
        self._patcher.start()
        self.addCleanup(self._patcher.stop)
        self.addCleanup(clear_installation_token_cache)

    def _settings(self, **overrides):
        values = {
            "ENABLE_ITQAN_DEPENDABOT": True,
            "GITHUB_WEBHOOK_SECRET": WEBHOOK_SECRET,
            "GITHUB_APP_ID": GITHUB_APP_ID,
            "GITHUB_APP_PRIVATE_KEY": GITHUB_APP_PRIVATE_KEY,
        }
        values.update(overrides)
        return override_settings(**values)

    def _post(
        self,
        *,
        event: str | None,
        body: bytes,
        secret: str = WEBHOOK_SECRET,
        sign: bool = True,
        delivery_id: str | None = None,
        send_delivery: bool = True,
    ):
        # Fresh GUID per delivery (like GitHub); pass an explicit one to
        # simulate redelivery of the same delivery.
        headers: dict[str, Any] = {"content_type": "application/json"}
        if send_delivery:
            headers["HTTP_X_GITHUB_DELIVERY"] = (
                delivery_id if delivery_id is not None else f"test-delivery-{uuid.uuid4()}"
            )
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

    def test_duplicate_delivery_where_redelivery_acknowledged_without_reapplying(self):
        from apps.dependabot.models import WebhookDelivery

        payload = {
            "action": "created",
            "installation": {"id": INSTALLATION_ID, "account": {"login": OWNER}},
            "repositories": [{"full_name": f"{OWNER}/a"}],
        }
        with self._settings():
            first = self._deliver(event="installation", payload=payload, delivery_id="dup-delivery-1")
            second = self._deliver(event="installation", payload=payload, delivery_id="dup-delivery-1")
        assert first.status_code == 200
        assert first.json()["status"] == "processed"
        assert second.status_code == 200
        assert second.json()["status"] == "ignored"
        assert WebhookDelivery.objects.filter(delivery_id="dup-delivery-1").count() == 1
        assert WatchedRepository.objects.count() == 1
        assert self._rows() == {(OWNER, "a"): "opted_in"}

    def test_missing_delivery_header_where_rejected(self):
        with self._settings():
            response = self._post(
                event="installation",
                body=json.dumps({"action": "created", "installation": {"id": 1}}).encode(),
                send_delivery=False,
            )
        assert response.status_code == 400
        assert response.json()["error_name"] == "github_invalid_webhook_payload"

    def test_added_after_removed_where_later_event_wins(self):
        # Same installation, arrival order decides: a re-add following a
        # removal is legitimate consent, not a stale replay.
        removed = {
            "action": "removed",
            "installation": {"id": INSTALLATION_ID},
            "repositories_removed": [{"full_name": f"{OWNER}/a"}],
        }
        added = {
            "action": "added",
            "installation": {"id": INSTALLATION_ID},
            "repositories_added": [{"full_name": f"{OWNER}/a"}],
        }
        with self._settings():
            assert (
                self._deliver(
                    event="installation",
                    payload={
                        "action": "created",
                        "installation": {"id": INSTALLATION_ID, "account": {"login": OWNER}},
                        "repositories": [{"full_name": f"{OWNER}/a"}],
                    },
                ).status_code
                == 200
            )
            assert self._deliver(event="installation_repositories", payload=removed).status_code == 200
            assert self._rows() == {(OWNER, "a"): "opted_out"}
            assert self._deliver(event="installation_repositories", payload=added).status_code == 200
        assert self._rows() == {(OWNER, "a"): "opted_in"}

    def test_created_after_deleted_where_reinstall_opts_in_again(self):
        deleted = {"action": "deleted", "installation": {"id": INSTALLATION_ID, "account": {"login": OWNER}}}
        created = {
            "action": "created",
            "installation": {"id": INSTALLATION_ID, "account": {"login": OWNER}},
            "repositories": [{"full_name": f"{OWNER}/a"}],
        }
        with self._settings():
            assert self._deliver(event="installation", payload=created).status_code == 200
            assert self._deliver(event="installation", payload=deleted).status_code == 200
            assert self._rows() == {(OWNER, "a"): "opted_out"}
            assert self._deliver(event="installation", payload=created).status_code == 200
        assert self._rows() == {(OWNER, "a"): "opted_in"}

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


class GitHubWebhookReconciliationTest(TestCase):
    """State-granting transitions reconcile with GitHub's current state."""

    def setUp(self):
        super().setUp()
        self.watched = WatchedRepositoryService()

    def _settings(self, **overrides):
        values = {
            "ENABLE_ITQAN_DEPENDABOT": True,
            "GITHUB_WEBHOOK_SECRET": WEBHOOK_SECRET,
            "GITHUB_APP_ID": GITHUB_APP_ID,
            "GITHUB_APP_PRIVATE_KEY": GITHUB_APP_PRIVATE_KEY,
        }
        values.update(overrides)
        return override_settings(**values)

    def _rows(self):
        return {
            (w.owner, w.repository_name): w.status
            for w in WatchedRepository.objects.filter(host=HOST).order_by("owner", "repository_name")
        }

    def _make_handler(self, *, installation_state: str = "active", repo_accessible: bool = True):
        """Create a mock transport that returns consistent GitHub state."""
        import httpx

        def handler(request: httpx.Request) -> httpx.Response:
            path = str(request.url.path)
            print(f"DEBUG MOCK: {request.method} {request.url} -> path={path}")
            if path.endswith("/access_tokens"):
                return httpx.Response(201, json={"token": STUB_TOKEN, "expires_at": FAR_FUTURE.isoformat()})
            if "/app/installations/" in path and "/access_tokens" not in path:
                print(f"DEBUG MOCK: installation state={installation_state}")
                if installation_state == "deleted":
                    return httpx.Response(404, json={"message": "Not Found"})
                if installation_state == "suspended":
                    return httpx.Response(
                        200,
                        json={
                            "id": INSTALLATION_ID,
                            "suspended_by": {"login": "admin"},
                            "suspended_at": "2026-09-06T12:00:00Z",
                        },
                    )
                return httpx.Response(200, json={"id": INSTALLATION_ID, "suspended_by": None})
            if "/repos/" in path and "/contents/" not in path:
                print(f"DEBUG MOCK: repo accessible={repo_accessible}")
                if not repo_accessible:
                    return httpx.Response(404, json={"message": "Not Found"})
                return httpx.Response(200, json={"default_branch": "main"})
            print(f"DEBUG MOCK: 404 fallback for {request.url}")
            return httpx.Response(404)

        return handler

    def _post_via_mock(
        self,
        body: bytes,
        headers: dict[str, str],
        *,
        installation_state: str = "active",
        repo_accessible: bool = True,
    ):
        import httpx

        from apps.dependabot.services.github_webhook import GitHubWebhookService

        with self._settings():
            double = self._make_handler(installation_state=installation_state, repo_accessible=repo_accessible)
            transport = httpx.MockTransport(double)
            client = httpx.Client(transport=transport)
            token_service = GitHubInstallationTokenService(http_client=client)
            contents_client = GitHubContentsClient(token_service=token_service, http_client=client)
            service = GitHubWebhookService(
                watched_service=self.watched,
                github_client=contents_client,
            )
            return service.handle(
                event=headers.get("X-GitHub-Event"),
                payload=body,
                signature_header=headers.get("X-Hub-Signature-256"),
                secret=WEBHOOK_SECRET,
                delivery_id=headers.get("X-GitHub-Delivery"),
            )

    def test_stale_added_after_current_removal_does_not_restore_opted_in(self):
        self.watched.opt_in(host=HOST, owner=OWNER, repository_name="a", installation_id=INSTALLATION_ID)
        self.watched.opt_out(host=HOST, owner=OWNER, repository_name="a")
        assert self._rows() == {(OWNER, "a"): "opted_out"}

        body = json.dumps(
            {
                "action": "added",
                "installation": {"id": INSTALLATION_ID},
                "repositories_added": [{"full_name": f"{OWNER}/a"}],
            }
        ).encode()
        headers = {
            "X-GitHub-Event": "installation_repositories",
            "X-GitHub-Delivery": "recon-added-stale",
            "X-Hub-Signature-256": _sign(WEBHOOK_SECRET, body),
        }
        outcome = self._post_via_mock(body, headers, repo_accessible=False)
        assert outcome.status == "processed"
        assert outcome.affected == 0
        assert self._rows() == {(OWNER, "a"): "opted_out"}

    def test_legitimate_current_added_does_opt_in(self):
        assert WatchedRepository.objects.count() == 0
        body = json.dumps(
            {
                "action": "added",
                "installation": {"id": INSTALLATION_ID},
                "repositories_added": [{"full_name": f"{OWNER}/a"}],
            }
        ).encode()
        headers = {
            "X-GitHub-Event": "installation_repositories",
            "X-GitHub-Delivery": "recon-added-fresh",
            "X-Hub-Signature-256": _sign(WEBHOOK_SECRET, body),
        }
        outcome = self._post_via_mock(body, headers)
        assert outcome.status == "processed"
        assert outcome.affected == 1
        assert self._rows() == {(OWNER, "a"): "opted_in"}

    def test_stale_created_after_current_deletion_does_not_restore_consent(self):
        self.watched.opt_in(host=HOST, owner=OWNER, repository_name="a", installation_id=INSTALLATION_ID)
        assert self._rows() == {(OWNER, "a"): "opted_in"}

        body = json.dumps(
            {
                "action": "created",
                "installation": {"id": INSTALLATION_ID, "account": {"login": OWNER}},
                "repositories": [{"full_name": f"{OWNER}/a"}],
            }
        ).encode()
        headers = {
            "X-GitHub-Event": "installation",
            "X-GitHub-Delivery": "recon-created-stale",
            "X-Hub-Signature-256": _sign(WEBHOOK_SECRET, body),
        }
        outcome = self._post_via_mock(body, headers, installation_state="deleted")
        assert outcome.status == "processed"  # processed but with 0 affected
        assert outcome.affected == 0
        row = WatchedRepository.objects.get(host=HOST, owner=OWNER, repository_name="a")
        assert row.status == "opted_in"  # unchanged because stale create was ignored

    def test_legitimate_reinstall_does_opt_in(self):
        assert WatchedRepository.objects.count() == 0
        body = json.dumps(
            {
                "action": "created",
                "installation": {"id": INSTALLATION_ID, "account": {"login": OWNER}},
                "repositories": [{"full_name": f"{OWNER}/a"}],
            }
        ).encode()
        headers = {
            "X-GitHub-Event": "installation",
            "X-GitHub-Delivery": "recon-created-legit",
            "X-Hub-Signature-256": _sign(WEBHOOK_SECRET, body),
        }
        outcome = self._post_via_mock(body, headers)
        assert outcome.status == "processed"
        assert outcome.affected == 1
        assert self._rows() == {(OWNER, "a"): "opted_in"}

    def test_stale_unsuspend_while_already_active_does_not_revive(self):
        self.watched.opt_in(host=HOST, owner=OWNER, repository_name="a", installation_id=INSTALLATION_ID)
        self.watched.suspend_installation(host=HOST, installation_id=INSTALLATION_ID)
        assert self._rows() == {(OWNER, "a"): "suspended"}

        body = json.dumps({"action": "unsuspend", "installation": {"id": INSTALLATION_ID}}).encode()
        headers = {
            "X-GitHub-Event": "installation",
            "X-GitHub-Delivery": "recon-unsuspend-stale",
            "X-Hub-Signature-256": _sign(WEBHOOK_SECRET, body),
        }
        # Installation is already active (unsuspend already happened), so this is stale
        outcome = self._post_via_mock(body, headers, installation_state="active")
        assert outcome.status == "processed"
        assert outcome.affected == 0
        row = WatchedRepository.objects.get(host=HOST, owner=OWNER, repository_name="a")
        assert row.status == "suspended"  # unchanged because stale unsuspend was ignored

    def test_legitimate_unsuspend_while_currently_suspended_works(self):
        self.watched.opt_in(host=HOST, owner=OWNER, repository_name="a", installation_id=INSTALLATION_ID)
        self.watched.suspend_installation(host=HOST, installation_id=INSTALLATION_ID)
        assert self._rows() == {(OWNER, "a"): "suspended"}

        body = json.dumps({"action": "unsuspend", "installation": {"id": INSTALLATION_ID}}).encode()
        headers = {
            "X-GitHub-Event": "installation",
            "X-GitHub-Delivery": "recon-unsuspend-legit",
            "X-Hub-Signature-256": _sign(WEBHOOK_SECRET, body),
        }
        # Installation is still suspended, so this is a legitimate unsuspend
        outcome = self._post_via_mock(body, headers, installation_state="suspended")
        assert outcome.status == "processed"
        assert outcome.affected == 1
        assert self._rows() == {(OWNER, "a"): "opted_in"}

    def test_duplicate_delivery_still_ignored_with_reconciliation(self):
        from apps.dependabot.models import WebhookDelivery

        body = json.dumps(
            {
                "action": "created",
                "installation": {"id": INSTALLATION_ID, "account": {"login": OWNER}},
                "repositories": [{"full_name": f"{OWNER}/a"}],
            }
        ).encode()
        headers = {
            "X-GitHub-Event": "installation",
            "X-GitHub-Delivery": "recon-dup-delivery",
            "X-Hub-Signature-256": _sign(WEBHOOK_SECRET, body),
        }
        first = self._post_via_mock(body, headers)
        second = self._post_via_mock(body, headers)
        assert first.status == "processed"
        assert second.status == "ignored"
        assert WebhookDelivery.objects.filter(delivery_id="recon-dup-delivery").count() == 1
        assert WatchedRepository.objects.count() == 1
        assert self._rows() == {(OWNER, "a"): "opted_in"}


class GitHubWebhookReconciliationFailClosedTest(TestCase):
    """State-granting transitions raise on reconciliation failure — never trust payload."""

    def setUp(self):
        super().setUp()
        self.watched = WatchedRepositoryService()
        from apps.dependabot.services.github_token import clear_installation_token_cache

        clear_installation_token_cache()

    def _settings(self, **overrides):
        values = {
            "ENABLE_ITQAN_DEPENDABOT": True,
            "GITHUB_WEBHOOK_SECRET": WEBHOOK_SECRET,
            "GITHUB_APP_ID": GITHUB_APP_ID,
            "GITHUB_APP_PRIVATE_KEY": GITHUB_APP_PRIVATE_KEY,
        }
        values.update(overrides)
        return override_settings(**values)

    def _rows(self):
        return {
            (w.owner, w.repository_name): w.status
            for w in WatchedRepository.objects.filter(host=HOST).order_by("owner", "repository_name")
        }

    def _make_error_handler(self, *, error_type: str = "timeout", fail_on: str = "any"):
        """Create a mock transport that raises a consistent error on selected endpoints."""
        import httpx

        def handler(request: httpx.Request) -> httpx.Response:
            path = str(request.url.path)
            # Token exchange always succeeds so we can isolate the error to
            # the reconciliation call itself.
            if path.endswith("/access_tokens"):
                return httpx.Response(201, json={"token": STUB_TOKEN, "expires_at": FAR_FUTURE.isoformat()})
            if error_type == "timeout":
                raise httpx.TimeoutException("request timed out")
            if error_type == "connection":
                raise httpx.ConnectError("connection refused")
            if error_type == "5xx":
                if fail_on in ("any", "repo") and path.endswith("/repos/octo/a"):
                    return httpx.Response(502, json={"message": "GitHub API error"})
                if fail_on in ("any", "install") and "/app/installations/" in path and "/access_tokens" not in path:
                    return httpx.Response(502, json={"message": "GitHub API error"})
                if fail_on == "any":
                    return httpx.Response(502, json={"message": "GitHub API error"})
                return httpx.Response(200, json={"id": INSTALLATION_ID, "suspended_by": None})
            if error_type == "401":
                # 401 on installation state returns None (stale), not an exception.
                # We test that case separately; this branch is for token-level 401.
                if "/repos/" in path:
                    return httpx.Response(
                        401, json={"message": "Bad credentials", "documentation_url": "https://docs.github.com/rest"}
                    )
                return httpx.Response(200, json={"id": INSTALLATION_ID, "suspended_by": None})
            if error_type == "429":
                if fail_on == "any" or path.endswith("/repos/octo/a") or "/app/installations/" in path:
                    return httpx.Response(
                        429,
                        json={
                            "message": "API rate limit exceeded",
                            "documentation_url": "https://docs.github.com/rest/using-the-rest-api/rate-limiting",
                        },
                        headers={"retry-after": "60"},
                    )
                return httpx.Response(200, json={"id": INSTALLATION_ID, "suspended_by": None})
            if path.endswith("/app/installations/"):
                return httpx.Response(200, json={"id": INSTALLATION_ID, "suspended_by": None})
            if "/repos/" in path and "/contents/" not in path:
                return httpx.Response(200, json={"default_branch": "main"})
            return httpx.Response(404)

        return handler

    def _post_via_mock_raises(
        self,
        body: bytes,
        headers: dict[str, str],
        *,
        error_type: str = "timeout",
        fail_on: str = "any",
    ):
        import httpx

        from apps.dependabot.services.github_client import GitHubContentsClient
        from apps.dependabot.services.github_webhook import GitHubWebhookService

        with self._settings():
            double = self._make_error_handler(error_type=error_type, fail_on=fail_on)
            transport = httpx.MockTransport(double)
            client = httpx.Client(transport=transport)
            token_service = GitHubInstallationTokenService(http_client=client)
            contents_client = GitHubContentsClient(token_service=token_service, http_client=client)
            service = GitHubWebhookService(
                watched_service=self.watched,
                github_client=contents_client,
            )
            return service.handle(
                event=headers.get("X-GitHub-Event"),
                payload=body,
                signature_header=headers.get("X-Hub-Signature-256"),
                secret=WEBHOOK_SECRET,
                delivery_id=headers.get("X-GitHub-Delivery"),
            )

    def test_created_where_github_timeout_raises_instead_of_opting_in(self):
        body = json.dumps(
            {
                "action": "created",
                "installation": {"id": INSTALLATION_ID, "account": {"login": OWNER}},
                "repositories": [{"full_name": f"{OWNER}/a"}],
            }
        ).encode()
        headers = {
            "X-GitHub-Event": "installation",
            "X-GitHub-Delivery": "fail-closed-created-timeout",
            "X-Hub-Signature-256": _sign(WEBHOOK_SECRET, body),
        }
        with pytest.raises(ItqanError) as exc_info:
            self._post_via_mock_raises(body, headers, error_type="timeout")
        assert exc_info.value.error_name == "github_upstream_error"
        assert WatchedRepository.objects.count() == 0

    def test_created_where_github_5xx_raises_instead_of_opting_in(self):
        body = json.dumps(
            {
                "action": "created",
                "installation": {"id": INSTALLATION_ID, "account": {"login": OWNER}},
                "repositories": [{"full_name": f"{OWNER}/a"}],
            }
        ).encode()
        headers = {
            "X-GitHub-Event": "installation",
            "X-GitHub-Delivery": "fail-closed-created-5xx",
            "X-Hub-Signature-256": _sign(WEBHOOK_SECRET, body),
        }
        with pytest.raises(ItqanError) as exc_info:
            self._post_via_mock_raises(body, headers, error_type="5xx")
        assert exc_info.value.error_name == "github_upstream_error"
        assert WatchedRepository.objects.count() == 0

    def test_added_where_github_5xx_raises_instead_of_opting_in(self):
        body = json.dumps(
            {
                "action": "added",
                "installation": {"id": INSTALLATION_ID},
                "repositories_added": [{"full_name": f"{OWNER}/a"}],
            }
        ).encode()
        headers = {
            "X-GitHub-Event": "installation_repositories",
            "X-GitHub-Delivery": "fail-closed-added-5xx",
            "X-Hub-Signature-256": _sign(WEBHOOK_SECRET, body),
        }
        with pytest.raises(ItqanError) as exc_info:
            self._post_via_mock_raises(body, headers, error_type="5xx", fail_on="repo")
        assert exc_info.value.error_name == "github_upstream_error"
        assert WatchedRepository.objects.count() == 0

    def test_unsuspend_where_github_auth_failure_blocks_revival(self):
        """401 on installation state returns None → treated as stale → no revival."""
        self.watched.opt_in(host=HOST, owner=OWNER, repository_name="a", installation_id=INSTALLATION_ID)
        self.watched.suspend_installation(host=HOST, installation_id=INSTALLATION_ID)
        assert self._rows() == {(OWNER, "a"): "suspended"}

        body = json.dumps({"action": "unsuspend", "installation": {"id": INSTALLATION_ID}}).encode()
        headers = {
            "X-GitHub-Event": "installation",
            "X-GitHub-Delivery": "fail-closed-unsuspend-401",
            "X-Hub-Signature-256": _sign(WEBHOOK_SECRET, body),
        }
        outcome = self._post_via_mock_raises(body, headers, error_type="401")
        assert outcome.status == "processed"
        assert outcome.affected == 0
        row = WatchedRepository.objects.get(host=HOST, owner=OWNER, repository_name="a")
        assert row.status == "suspended"  # unchanged — auth failure treated as stale, not revived

    def test_unsuspend_where_github_5xx_raises_instead_of_reviving(self):
        """5xx on installation state raises → no revival."""
        self.watched.opt_in(host=HOST, owner=OWNER, repository_name="a", installation_id=INSTALLATION_ID)
        self.watched.suspend_installation(host=HOST, installation_id=INSTALLATION_ID)
        assert self._rows() == {(OWNER, "a"): "suspended"}

        body = json.dumps({"action": "unsuspend", "installation": {"id": INSTALLATION_ID}}).encode()
        headers = {
            "X-GitHub-Event": "installation",
            "X-GitHub-Delivery": "fail-closed-unsuspend-5xx",
            "X-Hub-Signature-256": _sign(WEBHOOK_SECRET, body),
        }
        with pytest.raises(ItqanError) as exc_info:
            self._post_via_mock_raises(body, headers, error_type="5xx", fail_on="install")
        assert exc_info.value.error_name == "github_upstream_error"
        row = WatchedRepository.objects.get(host=HOST, owner=OWNER, repository_name="a")
        assert row.status == "suspended"  # unchanged — revival blocked by upstream error

    def test_removed_where_github_timeout_does_not_block_opt_out(self):
        """Restrictive events (removed) do not call GitHub — they still work."""
        self.watched.opt_in(host=HOST, owner=OWNER, repository_name="a", installation_id=INSTALLATION_ID)
        assert self._rows() == {(OWNER, "a"): "opted_in"}

        body = json.dumps(
            {
                "action": "removed",
                "installation": {"id": INSTALLATION_ID},
                "repositories_removed": [{"full_name": f"{OWNER}/a"}],
            }
        ).encode()
        headers = {
            "X-GitHub-Event": "installation_repositories",
            "X-GitHub-Delivery": "fail-closed-removed-should-work",
            "X-Hub-Signature-256": _sign(WEBHOOK_SECRET, body),
        }
        outcome = self._post_via_mock_raises(body, headers, error_type="timeout")
        assert outcome.status == "processed"
        assert outcome.affected == 1
        assert self._rows() == {(OWNER, "a"): "opted_out"}


class GitHubWebhookConcurrencyTest(TestCase):
    """Duplicate delivery deduplication: same GUID produces one claim row."""

    def setUp(self):
        super().setUp()
        self.watched = WatchedRepositoryService()
        # Patch GitHubContentsClient so the real endpoint never makes outbound calls.
        import httpx

        from apps.dependabot.services.github_client import GitHubContentsClient
        from apps.dependabot.services.github_token import GitHubInstallationTokenService, clear_installation_token_cache

        clear_installation_token_cache()

        def _mock_handler(request: httpx.Request) -> httpx.Response:
            path = str(request.url.path)
            if path.endswith("/access_tokens"):
                return httpx.Response(201, json={"token": STUB_TOKEN, "expires_at": FAR_FUTURE.isoformat()})
            if "/app/installations/" in path and "/access_tokens" not in path:
                return httpx.Response(200, json={"id": INSTALLATION_ID, "suspended_by": None})
            if "/repos/" in path and "/contents/" not in path:
                return httpx.Response(200, json={"default_branch": "main"})
            return httpx.Response(404)

        mock_transport = httpx.MockTransport(_mock_handler)
        self._mock_client = httpx.Client(transport=mock_transport)
        self._mock_contents = GitHubContentsClient(
            token_service=GitHubInstallationTokenService(http_client=self._mock_client),
            http_client=self._mock_client,
        )
        self._patcher = unittest.mock.patch(
            "apps.dependabot.services.github_webhook.GitHubContentsClient",
            return_value=self._mock_contents,
        )
        self._patcher.start()
        self.addCleanup(self._patcher.stop)
        self.addCleanup(clear_installation_token_cache)

    def _settings(self, **overrides):
        values = {
            "ENABLE_ITQAN_DEPENDABOT": True,
            "GITHUB_WEBHOOK_SECRET": WEBHOOK_SECRET,
            "GITHUB_APP_ID": GITHUB_APP_ID,
            "GITHUB_APP_PRIVATE_KEY": GITHUB_APP_PRIVATE_KEY,
        }
        values.update(overrides)
        return override_settings(**values)

    def _deliver(self, event: str, payload: dict[str, Any], *, delivery_id: str | None = None):
        from django.test import Client as DjangoClient

        body = json.dumps(payload).encode()
        headers = {
            "HTTP_X_GITHUB_EVENT": event,
            "HTTP_X_HUB_SIGNATURE_256": _sign(WEBHOOK_SECRET, body),
        }
        if delivery_id:
            headers["HTTP_X_GITHUB_DELIVERY"] = delivery_id
        return DjangoClient().post(WEBHOOK_URL, data=body, content_type="application/json", **headers)

    def _rows(self):
        return {
            (w.owner, w.repository_name): w.status
            for w in WatchedRepository.objects.filter(host=HOST).order_by("owner", "repository_name")
        }

    def test_duplicate_delivery_applies_once(self):
        from apps.dependabot.models import WebhookDelivery

        payload = {
            "action": "created",
            "installation": {"id": INSTALLATION_ID, "account": {"login": OWNER}},
            "repositories": [{"full_name": f"{OWNER}/a"}],
        }
        with self._settings():
            first = self._deliver(event="installation", payload=payload, delivery_id="dup-delivery-1")
            second = self._deliver(event="installation", payload=payload, delivery_id="dup-delivery-1")
        assert first.status_code == 200
        assert first.json()["status"] == "processed"
        assert second.status_code == 200
        assert second.json()["status"] == "ignored"
        assert WebhookDelivery.objects.filter(delivery_id="dup-delivery-1").count() == 1
        assert WatchedRepository.objects.count() == 1
        assert self._rows() == {(OWNER, "a"): "opted_in"}


class GitHubWebhookSecrecyTest(SimpleTestCase):
    def test_rejected_delivery_does_not_leak_secret(self):
        canary = "whsec_CANARY_DO_NOT_LEAK"
        body = json.dumps({"action": "created", "installation": {"id": 1}}).encode()
        with override_settings(ENABLE_ITQAN_DEPENDABOT=True, GITHUB_WEBHOOK_SECRET=canary):
            with self.assertLogs("apps.dependabot.services.github_webhook", level=logging.DEBUG) as cm:
                service = GitHubWebhookService()
                with pytest.raises(ItqanError) as exc_info:
                    service.handle(
                        event="installation",
                        payload=body,
                        signature_header="sha256=wrong",
                        secret=canary,
                        delivery_id="test-delivery-secrecy",
                    )
        assert exc_info.value.error_name == "github_webhook_signature_invalid"
        assert canary not in exc_info.value.message
        assert canary not in str(exc_info.value.extra)
        for record in cm.records:
            assert canary not in record.getMessage()
