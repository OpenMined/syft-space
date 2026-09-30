"""Which launch a card is of, when nobody says.

The console builds a card without being told which run it describes, and gets
it from the newest run of that Space. The distinction this holds is the one it
was written wrong the first time: *the newest run's launch*, not *the newest
launch*. A run started outside the queue belongs to no launch, and answering
with the newest launch there would describe an older measurement while the
freshest one sat unmentioned in the database.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import delete

from syft_benchmark.db.models import Run
from syft_benchmark.db.session import session_scope
from syft_benchmark.report.metrics import latest_measuring_job

KEY = "pytest-latest-job"
_NOW = datetime(2026, 9, 27, 12, 0, tzinfo=UTC)


def _db_ready() -> bool:
    try:
        with session_scope() as session:
            session.execute(delete(Run).where(Run.space == KEY))
        return True
    except Exception:  # noqa: BLE001 - the database may simply not be at hand
        return False


needs_db = pytest.mark.skipif(
    not _db_ready(), reason="the benchmark database is unavailable"
)


@pytest.fixture
def clean() -> Any:
    def wipe() -> None:
        with session_scope() as session:
            session.execute(delete(Run).where(Run.space == KEY))

    wipe()
    yield
    wipe()


def _run(run_id: str, *, job: str | None, minutes: int) -> None:
    with session_scope() as session:
        session.add(
            Run(
                id=run_id,
                space=KEY,
                endpoint="kb",
                job_id=job,
                context_mode="closed_book",
                model="m",
                started_at=_NOW + timedelta(minutes=minutes),
            )
        )


@needs_db
def test_the_newest_run_names_the_launch(clean: Any) -> None:
    """Judging or filtering afterwards opens no run, so the launch still stands."""
    _run("r1", job="job-old", minutes=0)
    _run("r2", job="job-new", minutes=10)

    assert latest_measuring_job(KEY) == "job-new"


@needs_db
def test_a_run_outside_the_queue_names_no_launch(clean: Any) -> None:
    """The CLI opens runs that belong to no job, and so do runs older than the
    job table. Reaching past them for the newest launch would hand back a card
    describing an older measurement while the freshest one went unmentioned —
    so the honest answer is None, and the card is the node as of now."""
    _run("r1", job="job-old", minutes=0)
    _run("r2", job=None, minutes=10)

    assert latest_measuring_job(KEY) is None


@needs_db
def test_a_space_nobody_measured_has_no_launch(clean: Any) -> None:
    assert latest_measuring_job(KEY) is None
