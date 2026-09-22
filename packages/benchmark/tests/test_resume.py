"""Resuming an interrupted measurement.

A measurement runs for hours, and it gets cut short regularly: the node
rebooted, the balance ran out, someone pressed Ctrl-C. What is checked is what
resuming turns into a forgery without: a failure is re-asked, the incomparable
is not reused, and the split goes by judge rather than by question.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from syft_benchmark.config import (
    ContextMode,
    ContextSource,
    EvalBlock,
    Settings,
    SpaceConfig,
)
from syft_benchmark.runs import resume as resume_mod
from syft_benchmark.runs.resume import done_units, window_start

SPACE = SpaceConfig(key="docs", url="http://node.local", endpoint="kb")
PARAMS: dict[str, Any] = {"profile": "default", "similarity_threshold": 0.0}


def _settings(**kwargs: object) -> Settings:
    return Settings(**kwargs)  # type: ignore[arg-type]


@dataclass
class _Run:
    id: str
    params: dict[str, Any]


@dataclass
class _Row:
    judge_model: str
    qa_id: str
    answer: str
    created_at: datetime
    verdict: str = "correct"


class _Store:
    """The database in the extent picking out what is done needs.

    There are two queries here and both are simple; the session is substituted
    rather than the engine, so the check does not need a running Postgres.
    """

    def __init__(self, runs: list[_Run], rows: list[_Row]) -> None:
        self.runs = runs
        self.rows = rows
        self.queries = 0

    def __call__(self, *args: Any, **kwargs: Any) -> _Store:
        return self

    def __enter__(self) -> _Store:
        return self

    def __exit__(self, *exc: Any) -> bool:
        return False

    def execute(self, stmt: Any) -> _Store:
        self.queries += 1
        self._last = stmt
        return self

    def all(self) -> list[Any]:
        # The first query is the runs, the second the verdicts. Telling them
        # apart by the text is more reliable than by a counter: the order of the
        # calls may change.
        text = str(self._last)
        return self.runs if "FROM runs" in text else self.rows


def _install(monkeypatch: Any, runs: list[_Run], rows: list[_Row]) -> _Store:
    store = _Store(runs, rows)
    monkeypatch.setattr(resume_mod, "session_scope", store)
    return store


def _done(monkeypatch: Any, runs: list[_Run], rows: list[_Row], **kwargs: Any) -> Any:
    _install(monkeypatch, runs, rows)
    return done_units(
        "docs",
        ContextMode.MODEL_WITH_CONTEXT,
        source=ContextSource.ENDPOINT_FRAGMENTS,
        block=EvalBlock.DIRECT,
        model="vendor/m",
        settings=kwargs.pop("settings", _settings()),
        params=kwargs.pop("params", PARAMS),
        since=kwargs.pop("since", None),
    )


_NOW = datetime(2026, 9, 14, 12, 0, tzinfo=UTC)


def test_a_graded_question_is_not_asked_again(monkeypatch: Any) -> None:
    """What the whole thing exists for: what is done is not asked again."""
    done = _done(
        monkeypatch,
        [_Run("r1", PARAMS)],
        [
            _Row("judge/a", "p1", "Port 5442.", _NOW),
            _Row("judge/a", "p2", "I don't know.", _NOW),
        ],
    )
    assert done == {"judge/a": {"p1", "p2"}}


def test_a_failed_call_is_a_hole_and_gets_asked_again(monkeypatch: Any) -> None:
    """A failure is not a result.

    A row with ``ERROR:`` is recorded so the run is visible whole, but it holds
    no verdict: the report filters it out of the denominator. Counting it as
    done means fixing a failure of the rig in place forever — that is exactly
    the one to re-ask.
    """
    done = _done(
        monkeypatch,
        [_Run("r1", PARAMS)],
        [
            _Row("judge/a", "p1", "Port 5442.", _NOW),
            _Row("judge/a", "p2", "ERROR: ConnectError", _NOW),
        ],
    )
    assert done == {"judge/a": {"p1"}}


def test_the_freshest_verdict_decides(monkeypatch: Any) -> None:
    """Freshness is counted the same way as in the report.

    Re-asked and failed — the question is a hole again: the report will take the
    latest record and count it a failure, and resuming is bound to agree with it.
    """
    done = _done(
        monkeypatch,
        [_Run("r1", PARAMS)],
        [
            _Row("judge/a", "p1", "Port 5442.", _NOW - timedelta(hours=2)),
            _Row("judge/a", "p1", "ERROR: timeout", _NOW),
        ],
    )
    assert done == {}


def test_a_later_success_closes_an_earlier_failure(monkeypatch: Any) -> None:
    """And the other way round: re-asked successfully — the question is closed."""
    done = _done(
        monkeypatch,
        [_Run("r1", PARAMS)],
        [
            _Row("judge/a", "p1", "ERROR: timeout", _NOW - timedelta(hours=2)),
            _Row("judge/a", "p1", "Port 5442.", _NOW),
        ],
    )
    assert done == {"judge/a": {"p1"}}


def test_each_judge_is_counted_separately(monkeypatch: Any) -> None:
    """A run gets cut off in the middle of a panel.

    The first judge managed to grade the answer, the second did not. "The
    question is done" would credit the second with work it never did, and the
    report for it would be left with a hole.
    """
    done = _done(
        monkeypatch,
        [_Run("r1", PARAMS)],
        [
            _Row("judge/a", "p1", "Port 5442.", _NOW),
            _Row("judge/b", "p1", "Port 5442.", _NOW),
            _Row("judge/a", "p2", "Port 5442.", _NOW),
        ],
    )
    assert done == {"judge/a": {"p1", "p2"}, "judge/b": {"p1"}}


def test_another_settings_snapshot_is_never_reused(monkeypatch: Any) -> None:
    """The similarity threshold is an axis of the measurement, not a constant.

    A run at 0.0 and a run at 0.45 answer different questions, and adding their
    halves into one share yields a quantity that means nothing. That is exactly
    what ``runs.params`` was created for.
    """
    done = _done(
        monkeypatch,
        [_Run("r1", {"profile": "default", "similarity_threshold": 0.45})],
        [_Row("judge/a", "p1", "Port 5442.", _NOW)],
    )
    assert done == {}, "a run with a different threshold does not count as done"


def test_nothing_recorded_means_nothing_to_skip(monkeypatch: Any) -> None:
    """The first launch with --resume behaves like an ordinary one."""
    assert _done(monkeypatch, [], []) == {}


def test_the_verdicts_are_not_even_read_without_a_matching_run(
    monkeypatch: Any,
) -> None:
    """The snapshot did not match — the second query is not made at all."""
    store = _install(monkeypatch, [_Run("r1", {"profile": "strict"})], [])
    done_units(
        "docs",
        ContextMode.CLOSED_BOOK,
        source=ContextSource.NONE,
        block=EvalBlock.DIRECT,
        model="vendor/m",
        settings=_settings(),
        params=PARAMS,
        since=None,
    )
    assert store.queries == 1


# --- the time window -------------------------------------------------------


def test_the_window_keeps_the_daily_cycle_measuring() -> None:
    """What is resumed is an interrupted attempt, not yesterday's measurement undone.

    Without the window the daily cycle would decide on the second day that
    everything was already done, and would measure nothing.
    """
    start = window_start(_settings(resume_window_hours=24))
    assert start is not None
    assert timedelta(hours=23) < datetime.now(UTC) - start < timedelta(hours=25)


def test_the_window_can_be_removed() -> None:
    """A measurement that ran for a week cannot be cut off at the start of a day."""
    assert window_start(_settings(resume_window_hours=0)) is None
