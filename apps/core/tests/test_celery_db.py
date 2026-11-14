from types import SimpleNamespace
from unittest.mock import patch

from django.db import connections
from django.db.utils import InterfaceError
import pytest

from apps.core import celery_db
from apps.core.celery_db import reset_stuck_transactions, reset_stuck_transactions_before_task
from apps.core.tests.base import BaseTestCase


class TestResetStuckTransactions(BaseTestCase):
    def setUp(self):
        super().setUp()
        # A connection of its own: the test's connection is inside the test case's transaction.
        self.wrapper = connections.create_connection("default")
        self.addCleanup(self._close_wrapper)

    def _close_wrapper(self) -> None:
        self.wrapper.in_atomic_block = False
        self.wrapper.closed_in_transaction = False
        self.wrapper.close()

    def _stuck_wrapper(self):
        """The state a soft time limit inside `Atomic.__exit__` leaves, after Celery's per-task close."""
        self.wrapper.ensure_connection()
        self.wrapper.in_atomic_block = True
        self.wrapper.close()
        return self.wrapper

    def test_reset_stuck_transactions_where_left_in_atomic_block_should_reconnect(self):
        # Arrange
        wrapper = self._stuck_wrapper()
        with pytest.raises(InterfaceError):
            wrapper.cursor()

        # Act
        reset = reset_stuck_transactions([wrapper])

        # Assert
        assert reset == ["default"]
        with wrapper.cursor() as cursor:
            cursor.execute("SELECT 1")
            assert cursor.fetchone() == (1,)

    def test_reset_stuck_transactions_where_connection_healthy_should_leave_it_open(self):
        # Arrange
        self.wrapper.ensure_connection()
        raw = self.wrapper.connection

        # Act
        reset = reset_stuck_transactions([self.wrapper])

        # Assert
        assert reset == []
        assert self.wrapper.connection is raw

    def test_reset_stuck_transactions_before_task_where_task_is_eager_should_skip(self):
        # Arrange
        task = SimpleNamespace(name="eager", request=SimpleNamespace(is_eager=True))

        # Act
        with patch.object(celery_db, reset_stuck_transactions.__name__) as reset:
            reset_stuck_transactions_before_task(task=task)

        # Assert
        reset.assert_not_called()
