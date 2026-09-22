"""Stopping a measurement the owner has called off.

Pressing stop used to end the pass in flight and nothing else. The next pass
started fresh, knew nothing, and dispatched its whole batch of questions before
it found out — so a measurement stopped at pass 39 of 54 went on to pay for
fifteen more batches. What is checked here is that a cancellation is read where
the decision to carry on is actually taken: between passes, and between the
units of a build.

None of it needs a database or a model: the cancellation has to work by the
shape of the loops, and a check that stubbed the loops would be checking
itself.
"""

from __future__ import annotations

from typing import Any

import pytest

from syft_benchmark.config import (
    ContextMode,
    EvalBlock,
    JobPhase,
    Settings,
    SpaceConfig,
)
from syft_benchmark.runs.parallel import Progress
from syft_benchmark.scheduler import measure

SPACE = SpaceConfig(key="pytest-space", url="http://localhost:0", endpoint="kb")


def _settings(**overrides: Any) -> Settings:
    """Two model arms, two subjects, one block: four passes, countable by hand."""
    body: dict[str, Any] = {
        "arms": [ContextMode.CLOSED_BOOK, ContextMode.MODEL_WITH_CONTEXT],
        "blocks": [EvalBlock.DIRECT],
        "generate_in_cycle": False,
    }
    body.update(overrides)
    return Settings(**body)


class Watcher:
    """An Observer that reports nothing and is cancelled on cue.

    ``stop_after`` counts passes: 0 means the owner pressed stop before the
    first one, 1 means during the first, and so on.
    """

    def __init__(self, stop_after: int | None = None) -> None:
        self.stop_after = stop_after
        self.passes_started = 0
        self.asked_about_stopping = 0
        self.phases: list[JobPhase] = []

    def planned(self, passes: int) -> None: ...

    def phase(self, phase: JobPhase, message: str = "") -> None:
        self.phases.append(phase)

    def pass_started(self, index: int, arm: str, block: str, model: str) -> None:
        self.passes_started = index

    def pass_done(self, index: int, label: str) -> None: ...

    def watcher(self, label: str) -> Any:
        return None

    def stop_requested(self) -> bool:
        self.asked_about_stopping += 1
        return self.stop_after is not None and self.passes_started >= self.stop_after


@pytest.fixture
def two_subjects(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Two subject models and one judge, so the arms differ in pass count."""
    calls: list[str] = []

    class Provider:
        def __init__(self, model: str) -> None:
            self.model = model

    monkeypatch.setattr(
        "syft_benchmark.scheduler.subject_providers",
        lambda conf: [Provider("model-a"), Provider("model-b")],
    )
    monkeypatch.setattr(
        "syft_benchmark.scheduler.judge_providers", lambda conf: [Provider("judge")]
    )

    def fake_run_pass(space: Any, mode: Any, **kwargs: Any) -> list[Any]:
        calls.append(f"{mode.value}")
        return []

    monkeypatch.setattr("syft_benchmark.scheduler.run_pass", fake_run_pass)
    return calls


def test_a_measurement_stopped_by_the_owner_starts_no_further_passes(
    two_subjects: list[str],
) -> None:
    """The defect, stated as a check.

    A pass stopped from within is still followed by the next one, which is
    fresh and dispatches its whole batch before it learns anything. Stopping
    has to be read before the pass exists, or every remaining pass costs a
    batch of questions that nobody will look at.
    """
    watcher = Watcher(stop_after=1)

    measure(SPACE, _settings(), observer=watcher)

    # Four passes were planned, two per arm. Only the first ran.
    assert len(two_subjects) == 1


def test_a_measurement_nobody_stopped_runs_every_pass(two_subjects: list[str]) -> None:
    """The guard must not end the measurement on its own."""
    watcher = Watcher(stop_after=None)

    measure(SPACE, _settings(), observer=watcher)

    assert len(two_subjects) == 4


def test_a_measurement_without_an_observer_runs_every_pass(
    two_subjects: list[str],
) -> None:
    """The daily cycle passes no observer, and must keep working."""
    measure(SPACE, _settings(), observer=None)

    assert len(two_subjects) == 4


def test_evaluate_false_asks_nothing(two_subjects: list[str]) -> None:
    """A launch that only wants the question set refreshed asks no questions.

    Building the dataset is cheap; asking a model about every item in it is
    not, and a launch that asked for the first must not be charged for the
    second.
    """
    watcher = Watcher()

    measure(SPACE, _settings(), observer=watcher, evaluate=False)

    assert len(two_subjects) == 0
    assert JobPhase.EVALUATE not in watcher.phases


def test_stopping_during_the_build_does_not_start_the_runs(
    monkeypatch: pytest.MonkeyPatch, two_subjects: list[str]
) -> None:
    """Generation is the cheap half; the runs are the expensive one.

    Reaching the end of a build that was called off and then starting to ask
    questions would answer a button press with more spending.
    """
    monkeypatch.setattr(
        "syft_benchmark.scheduler.generate_for_space",
        lambda space, **kwargs: _Built(),
    )
    watcher = Watcher(stop_after=0)

    measure(SPACE, _settings(generate_in_cycle=True), observer=watcher)

    assert two_subjects == []
    # The build was entered and the runs were not.
    assert JobPhase.GENERATE in watcher.phases
    assert JobPhase.EVALUATE not in watcher.phases


def test_the_build_is_handed_a_way_to_be_stopped(
    monkeypatch: pytest.MonkeyPatch, two_subjects: list[str]
) -> None:
    """Generation reports no progress, so it cannot be told — it has to ask.

    Without this the phase is deaf: a stop pressed during a build on a paid
    model does nothing for the tens of minutes it runs.
    """
    seen: dict[str, Any] = {}

    def fake_generate(space: Any, **kwargs: Any) -> Any:
        seen.update(kwargs)
        return _Built()

    monkeypatch.setattr("syft_benchmark.scheduler.generate_for_space", fake_generate)
    watcher = Watcher()

    measure(SPACE, _settings(generate_in_cycle=True), observer=watcher)

    assert "should_stop" in seen
    # A bound method is a fresh object on every attribute access, so identity
    # is asked of what it is bound to.
    assert seen["should_stop"].__self__ is watcher
    assert seen["should_stop"].__func__ is Watcher.stop_requested


class _Built:
    """What generate_for_space gives back, reduced to what measure reads."""

    pairs_made = 0
    pairs_active = 0


# --- within a pass ----------------------------------------------------------


def test_a_pass_stops_at_the_first_question_after_the_word_is_given() -> None:
    """The other half of the answer: Progress still ends the pass in flight.

    Checked so that fixing the loop above does not quietly remove the reason
    the loop below existed.
    """
    progress = Progress(total=10, label="pytest")
    progress.stop("stopped by the owner")

    assert progress.stopped is True
    assert progress.fatal == "stopped by the owner"


def test_a_stop_keeps_the_first_reason_it_was_given() -> None:
    """A run that gave up on failures and was then cancelled is not recast.

    The first reason is the true one; overwriting it would report the owner as
    having stopped a run that had already stopped itself.
    """
    progress = Progress(total=10, label="pytest")
    progress.stop("8 questions in a row failed")
    progress.stop("stopped by the owner")

    assert progress.fatal == "8 questions in a row failed"
