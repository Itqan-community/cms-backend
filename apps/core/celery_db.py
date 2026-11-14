"""Keep one interrupted task from breaking the database connection of every later task.

A soft time limit is an exception raised asynchronously, so it can fire inside Django's
``Atomic.__exit__`` before it clears ``in_atomic_block``. The worker process then believes it
is still in a transaction: Celery's per-task ``conn.close()`` closes the socket but keeps the
dead connection object (Django defers that to the outermost atomic block, which never exits),
and every later task in the process fails with ``InterfaceError: connection already closed``
until the worker restarts. No task starts inside a transaction, so any such state at task
start is that leftover: drop it.
"""

from __future__ import annotations

from collections.abc import Iterable
import logging
from typing import Any

from django.db import connections
from django.db.backends.base.base import BaseDatabaseWrapper

logger = logging.getLogger(__name__)


def reset_stuck_transactions(wrappers: Iterable[BaseDatabaseWrapper]) -> list[str]:
    """Drop the connection of every wrapper left inside a transaction; returns their aliases."""
    reset: list[str] = []
    for conn in wrappers:
        if not (conn.in_atomic_block or conn.closed_in_transaction):
            continue
        try:
            if conn.connection is not None:
                conn.connection.close()
        except Exception:  # noqa: BLE001, S110 — already broken: dropping it below is all that is left
            pass
        conn.connection = None
        conn.in_atomic_block = False
        conn.closed_in_transaction = False
        conn.needs_rollback = False
        conn.atomic_blocks = []
        conn.savepoint_ids = []
        conn.commit_on_exit = True
        conn.run_on_commit = []
        reset.append(conn.alias)
    return reset


def reset_stuck_transactions_before_task(**kwargs: Any) -> None:
    """``task_prerun`` receiver (eager tasks run inside the caller's transaction: skip them)."""
    task = kwargs.get("task")
    if getattr(getattr(task, "request", None), "is_eager", False):
        return
    aliases = reset_stuck_transactions(connections.all(initialized_only=True))
    if aliases:
        logger.error(
            "Reset database connection(s) %s left inside a transaction before task %s",
            ", ".join(aliases),
            getattr(task, "name", "?"),
        )
