from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from threading import Event
from time import monotonic
from typing import Any
from unittest import skipUnless
from unittest.mock import patch

from django.db import connection, connections
from django.test import TransactionTestCase

from apps.content.models import Asset, AssetAccess, AssetAccessRequest, CategoryChoice, LicenseChoice
from apps.content.repositories.access_request import AssetAccessRequestRepository
from apps.content.services.asset_access import AssetAccessRequestService
from apps.core.ninja_utils.errors import ItqanError
from apps.publishers.models import Publisher
from apps.users.models import User


@skipUnless(connection.vendor == "postgresql", "Requires PostgreSQL row locks")
class AssetAccessConcurrencyTests(TransactionTestCase):
    def setUp(self) -> None:
        self.actor = User.objects.create_user(email="access-review@example.invalid", is_staff=True)
        self.addCleanup(self.actor.delete)
        self.developer = User.objects.create_user(email="access-developer@example.invalid")
        self.addCleanup(self.developer.delete)
        self.publisher = Publisher.objects.create(name="Access concurrency", auto_accept_access_requests=False)
        self.addCleanup(self.publisher.delete)
        self.addCleanup(Asset.objects.filter(publisher=self.publisher).delete)
        self.service = AssetAccessRequestService(AssetAccessRequestRepository())
        self.email_patch = patch.object(
            AssetAccessRequestService, AssetAccessRequestService._enqueue_outcome_email.__name__
        )
        self.email_patch.start()
        self.addCleanup(self.email_patch.stop)

    def _fixture_teardown(self) -> None:
        # addCleanup deletes assets (and their requests and grants) before the
        # protected publisher, then users, even when setup or a worker fails.
        # Keep migrated reference data and avoid rerunning unrelated post_migrate seeders.
        pass

    def _asset(self, *, auto_approve: bool = False) -> Asset:
        self.publisher.auto_accept_access_requests = auto_approve
        self.publisher.save(update_fields=["auto_accept_access_requests"])
        return Asset.objects.create(
            publisher=self.publisher,
            name="Access race asset",
            category=CategoryChoice.FONT,
            license=LicenseChoice.CC0,
            description="Concurrency fixture",
            format="ttf",
            file_size="0 B",
            language="en",
        )

    def _request(self, asset: Asset) -> AssetAccessRequest:
        return AssetAccessRequest.objects.create(
            developer_user=self.developer, asset=asset, developer_access_reason="test", intended_use="non-commercial"
        )

    def _submit(self, asset: Asset) -> tuple[AssetAccessRequest, AssetAccess | None]:
        return self.service.request_access(
            user=self.developer, asset=asset, purpose="test", intended_use="non-commercial"
        )

    def _run_pair(self, first: Callable[[], Any], second: Callable[[], Any]) -> tuple[Any, Any]:
        # Keep the first read uncommitted until the second read completes or
        # PostgreSQL confirms that the second backend is waiting on the first.
        first_read, second_read, first_done = Event(), Event(), Event()
        release_first, second_connected = Event(), Event()
        backend_pids: dict[int, int] = {}

        def worker(index: int, operation: Callable[[], Any]) -> Any:
            db = connections["default"]
            seen = False

            def coordinate(
                execute: Callable[..., Any], sql: str, params: Any, many: bool, context: dict[str, Any]
            ) -> Any:
                nonlocal seen
                result = execute(sql, params, many, context)
                if not seen and sql.lstrip().upper().startswith("SELECT") and AssetAccessRequest._meta.db_table in sql:
                    seen = True
                    if index == 0:
                        first_read.set()
                        if not release_first.wait(timeout=20):
                            raise TimeoutError("First worker was never released")
                    else:
                        second_read.set()
                        if not first_done.wait(timeout=8):
                            raise TimeoutError("First operation failed to finish")
                return result

            try:
                with db.cursor() as cursor:
                    cursor.execute("SET statement_timeout = '8s'")
                    cursor.execute("SELECT pg_backend_pid()")
                    backend_pids[index] = cursor.fetchone()[0]
                if index == 1:
                    second_connected.set()
                with db.execute_wrapper(coordinate):
                    return operation()
            except ItqanError as exc:
                return exc
            finally:
                if index == 0:
                    first_done.set()
                db.close()

        with ThreadPoolExecutor(max_workers=2) as pool:
            first_future = pool.submit(worker, 0, first)
            try:
                self.assertTrue(first_read.wait(timeout=8), "First worker never read an access request")
                second_future = pool.submit(worker, 1, second)
                self.assertTrue(second_connected.wait(timeout=8), "Second worker never connected to PostgreSQL")
                deadline = monotonic() + 5
                while not second_read.is_set():
                    if second_future.done():
                        second_future.result()
                        self.fail("Second worker finished without a competing access request read")
                    with connection.cursor() as cursor:
                        cursor.execute("SELECT %s = ANY(pg_blocking_pids(%s))", [backend_pids[0], backend_pids[1]])
                        blocked_by_first = cursor.fetchone()[0]
                    if blocked_by_first:
                        break
                    self.assertLess(
                        monotonic(), deadline, "Second worker neither read the request nor waited on the first worker"
                    )
                    second_read.wait(timeout=0.01)
            finally:
                release_first.set()
            return first_future.result(timeout=12), second_future.result(timeout=12)

    def _assert_conflict(self, result: Any) -> None:
        self.assertIsInstance(result, ItqanError)
        self.assertEqual("invalid_status", result.error_name)
        self.assertEqual(409, result.status_code)

    def test_accept_and_reject_where_concurrent_should_preserve_one_outcome(self) -> None:
        for first_action in ("accept", "reject"):
            with self.subTest(first_action=first_action):
                # Arrange
                asset = self._asset()
                request = self._request(asset)
                accept = partial(self.service.accept, self.actor, request.pk)
                reject = partial(self.service.reject, self.actor, request.pk, "Declined")
                operations = (accept, reject) if first_action == "accept" else (reject, accept)

                # Act
                first, second = self._run_pair(*operations)

                # Assert
                self.assertEqual(request.pk, first.pk)
                self._assert_conflict(second)
                request.refresh_from_db()
                self.assertEqual("approved" if first_action == "accept" else "rejected", request.status)
                self.assertEqual(first_action == "accept", AssetAccess.objects.filter(asset=asset).exists())
                self.assertFalse(request.approved_at and request.rejected_at)

    def test_accept_where_concurrent_should_create_one_grant_and_return_conflict(self) -> None:
        # Arrange
        asset = self._asset()
        request = self._request(asset)
        accept = partial(self.service.accept, self.actor, request.pk)

        # Act
        first, second = self._run_pair(accept, accept)

        # Assert
        self.assertEqual(request.pk, first.pk)
        self._assert_conflict(second)
        self.assertEqual(1, AssetAccess.objects.filter(asset=asset).count())

    def test_accept_where_second_worker_is_delayed_should_wait_for_contention(self) -> None:
        # Arrange
        asset = self._asset()
        request = self._request(asset)
        first_finished, second_started, release_second = Event(), Event(), Event()

        def accept_first() -> AssetAccessRequest:
            result = self.service.accept(self.actor, request.pk)
            first_finished.set()
            return result

        def accept_second() -> AssetAccessRequest:
            second_started.set()
            if not release_second.wait(timeout=8):
                raise TimeoutError("Delayed second worker was never released")
            return self.service.accept(self.actor, request.pk)

        def run_pair() -> tuple[Any, Any]:
            try:
                return self._run_pair(accept_first, accept_second)
            finally:
                connections["default"].close()

        # Act
        with ThreadPoolExecutor(max_workers=1) as pool:
            pair_future = pool.submit(run_pair)
            try:
                self.assertTrue(second_started.wait(timeout=8), "Second worker never started")
                self.assertFalse(
                    first_finished.wait(timeout=1), "First worker committed before the second attempted its query"
                )
            finally:
                release_second.set()
            first, second = pair_future.result(timeout=12)

        # Assert
        self.assertEqual(request.pk, first.pk)
        self._assert_conflict(second)
        self.assertEqual(1, AssetAccess.objects.filter(asset=asset).count())

    def test_submissions_where_concurrent_should_reuse_request_and_grant(self) -> None:
        for auto_approve, existing in [(False, False), (True, False), (True, True)]:
            with self.subTest(auto_approve=auto_approve, existing=existing):
                # Arrange
                asset = self._asset(auto_approve=auto_approve)
                if existing:
                    self._request(asset)

                submit = partial(self._submit, asset)
                # Act
                first, second = self._run_pair(submit, submit)

                # Assert
                self.assertEqual(first[0].pk, second[0].pk)
                self.assertEqual("approved" if auto_approve else "pending", second[0].status)
                self.assertEqual(1, AssetAccessRequest.objects.filter(asset=asset).count())
                self.assertEqual(int(auto_approve), AssetAccess.objects.filter(asset=asset).count())
                if auto_approve:
                    self.assertEqual(first[1].pk, second[1].pk)

    def test_auto_approval_and_publisher_accept_where_concurrent_should_avoid_deadlock(self) -> None:
        # The submission holds the asset lock while waiting for the request lock.
        # The reviewer must still be able to insert the grant's FK to that asset.
        for reviewer_first in (True, False):
            with self.subTest(reviewer_first=reviewer_first):
                # Arrange
                asset = self._asset(auto_approve=True)
                request = self._request(asset)
                accept = partial(self.service.accept, self.actor, request.pk)
                submit = partial(self._submit, asset)

                # Act
                first, second = self._run_pair(accept, submit) if reviewer_first else self._run_pair(submit, accept)

                # Assert
                if reviewer_first:
                    self.assertEqual(request.pk, first.pk)
                    self.assertEqual(request.pk, second[0].pk)
                    self.assertTrue(second[1].is_active)
                else:
                    self.assertEqual(request.pk, first[0].pk)
                    self._assert_conflict(second)
                request.refresh_from_db()
                self.assertEqual("approved", request.status)
                self.assertEqual(1, AssetAccess.objects.filter(asset=asset).count())
