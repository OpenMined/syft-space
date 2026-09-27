"""Reading and removing generated pairs — the console's Generation review.

The one thing worth a real database here is the delete guard: a pair with a
Result pointing at it must never be hard-deleted, because the foreign key
itself will not stop it (`ondelete="CASCADE"`, not `RESTRICT`).
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import delete

from syft_benchmark.config import PairStatus
from syft_benchmark.db import QaPair, Result, Run, session_scope
from syft_benchmark.generation.pairs import delete_pair, get_pair, list_pairs

SPACE = "pytest-pairs"


def _db_ready() -> bool:
    try:
        with session_scope() as session:
            session.execute(delete(QaPair).where(QaPair.space == SPACE))
        return True
    except Exception:  # noqa: BLE001 - the database may simply not be at hand
        return False


needs_db = pytest.mark.skipif(
    not _db_ready(), reason="the benchmark database is unavailable"
)


@pytest.fixture
def clean():  # type: ignore[no-untyped-def]
    def wipe() -> None:
        with session_scope() as session:
            session.execute(delete(Result).where(Result.space == SPACE))
            session.execute(delete(Run).where(Run.space == SPACE))
            session.execute(delete(QaPair).where(QaPair.space == SPACE))

    wipe()
    yield
    wipe()


def _pair(
    pair_id: str, *, status: str = PairStatus.PENDING.value, **extra: object
) -> QaPair:
    return QaPair(
        id=pair_id,
        space=SPACE,
        generator="cloze",
        question="What port does the benchmark database listen on?",
        answer="5442",
        context="The benchmark database listens on port 5442.",
        status=status,
        model="test-model",
        question_hash=uuid.uuid4().hex,
        **extra,  # type: ignore[arg-type]
    )


@needs_db
def test_a_pair_with_no_results_is_deleted_outright(clean: None) -> None:
    with session_scope() as session:
        session.add(_pair("p-lonely"))

    assert delete_pair("p-lonely") == "deleted"
    assert get_pair("p-lonely") is None


@needs_db
def test_a_pair_with_a_result_is_never_hard_deleted(clean: None) -> None:
    with session_scope() as session:
        session.add(_pair("p-measured", status=PairStatus.ACTIVE.value))
        session.add(
            Run(
                id="run-measured",
                space=SPACE,
                context_mode="closed_book",
                model="m",
            )
        )
        session.add(
            Result(
                id="result-measured",
                run_id="run-measured",
                qa_id="p-measured",
                space=SPACE,
                verdict="correct",
            )
        )

    assert delete_pair("p-measured") == "has_results"

    # Still there, untouched — the guard refused, it did not silently retire it.
    view = get_pair("p-measured")
    assert view is not None
    assert view.status == PairStatus.ACTIVE.value
    assert view.has_results is True


@needs_db
def test_deleting_an_unknown_pair_says_so(clean: None) -> None:
    assert delete_pair("no-such-pair") == "not_found"


@needs_db
def test_listing_filters_by_status_and_reports_has_results(clean: None) -> None:
    with session_scope() as session:
        session.add(_pair("p-pending", status=PairStatus.PENDING.value))
        session.add(_pair("p-active", status=PairStatus.ACTIVE.value))
        session.add(
            Run(id="run-listing", space=SPACE, context_mode="closed_book", model="m")
        )
        session.add(
            Result(
                id="result-listing",
                run_id="run-listing",
                qa_id="p-active",
                space=SPACE,
                verdict="correct",
            )
        )

    pending, total_pending = list_pairs(SPACE, status=PairStatus.PENDING.value)
    assert total_pending == 1
    assert pending[0].id == "p-pending"
    assert pending[0].has_results is False

    active, total_active = list_pairs(SPACE, status=PairStatus.ACTIVE.value)
    assert total_active == 1
    assert active[0].id == "p-active"
    assert active[0].has_results is True

    everything, total_all = list_pairs(SPACE)
    assert total_all == 2
    assert {row.id for row in everything} == {"p-pending", "p-active"}
