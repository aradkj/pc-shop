"""Helpers for tests that need two database transactions to overlap for real."""

import threading
import time
from collections.abc import Callable
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.database import SessionLocal


def wait_until_blocked(db: Session, expected: int, timeout: float = 10.0) -> None:
    """Wait until `expected` database sessions are waiting for a lock."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        waiting = db.scalar(
            text("SELECT count(*) FROM pg_stat_activity WHERE datname = current_database() AND wait_event_type = 'Lock'")
        )
        db.rollback()  # pg_stat_activity is cached per transaction: end it so the next poll sees fresh data
        if waiting >= expected:
            return
        time.sleep(0.02)
    raise AssertionError(f"expected {expected} sessions waiting for a lock")


def request_during_uncommitted_insert(db: Session, insert: Callable[[Session], None], send_request: Callable[[], Any]) -> Any:
    """Send a request that loses a race against another transaction's INSERT.

    `insert` adds a conflicting row in a second transaction that is *not committed yet*, so the
    request's own "does it exist already?" pre-check cannot see it. The request then blocks on the
    unique index; once it is stuck, the other transaction commits and the request's INSERT fails
    with a unique violation - exactly what happens when two clients really collide.
    """
    outcome: dict[str, Any] = {}
    thread = threading.Thread(target=lambda: outcome.update(response=send_request()))
    blocker = SessionLocal()
    try:
        insert(blocker)
        blocker.flush()
        thread.start()
        wait_until_blocked(db, expected=1)
    finally:
        blocker.commit()
        blocker.close()
    thread.join(timeout=20)
    assert not thread.is_alive()
    return outcome["response"]
