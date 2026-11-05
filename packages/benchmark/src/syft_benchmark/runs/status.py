"""What is collected, what is missing and what will finish it.

Counted by the report's rule, the latest verdict per question, so "collected"
and "in the report" agree. Five states, each with its own remedy printed beside
the number:

  * **assessed** — there is a verdict;
  * **failed** — the call did not get through; out of the denominator, and
    ``--resume`` re-asks it;
  * **judge failed** — the answer was received, the judge call failed
    (``technical``); judging again (``judge``) cures it without re-asking;
  * **awaiting a verdict** — recorded under deferred judging, cured by judging;
  * **not asked** — never put to this judge at all.

Coverage by item type is reported too: an interrupted run leaves it uneven, and
shares over such a sample look like ordinary shares.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import select

from syft_benchmark.config import (
    ARM_LETTER,
    ContextMode,
    EvalBlock,
    Settings,
    Verdict,
    get_settings,
)
from syft_benchmark.db import Result, Run, session_scope
from syft_benchmark.runs.judge import is_error, is_technical


@dataclass(frozen=True, slots=True)
class PassStatus:
    """The state of one (arm, block, model, judge) combination."""

    context_mode: ContextMode
    block: EvalBlock
    model: str
    judge: str
    total: int
    graded: int
    failed: int
    pending: int
    unjudged: int = 0

    @property
    def arm(self) -> str:
        return ARM_LETTER.get(self.context_mode.value, "?")

    @property
    def missing(self) -> int:
        """The questions this judge was never asked at all."""
        return max(
            0, self.total - self.graded - self.failed - self.unjudged - self.pending
        )

    @property
    def done(self) -> bool:
        return (
            self.missing == 0
            and self.failed == 0
            and self.unjudged == 0
            and self.pending == 0
        )

    def line(self) -> str:
        """One line for the console."""
        parts = [f"assessed {self.graded}"]
        if self.failed:
            parts.append(f"failed {self.failed}")
        if self.unjudged:
            parts.append(f"judge failed {self.unjudged}")
        if self.pending:
            parts.append(f"awaiting a verdict {self.pending}")
        if self.missing:
            parts.append(f"not asked {self.missing}")
        return ", ".join(parts)


@dataclass(frozen=True, slots=True)
class GeneratorCoverage:
    """How far one item type has been got through across all the node runs."""

    generator: str
    in_set: int
    graded: int
    expected: int

    @property
    def share(self) -> float:
        return self.graded / self.expected if self.expected else 0.0


# How far an item type may lag behind the best before it counts as a skew of
# the sample rather than uneven progress.
_LAG = 0.25


@dataclass(frozen=True, slots=True)
class SpaceStatus:
    """The state of the measurement for one node."""

    space: str
    total: int
    frozen: str
    passes: list[PassStatus]
    coverage: list[GeneratorCoverage] = field(default_factory=list)

    @property
    def failed(self) -> int:
        return sum(p.failed for p in self.passes)

    @property
    def unjudged(self) -> int:
        return sum(p.unjudged for p in self.passes)

    @property
    def pending(self) -> int:
        return sum(p.pending for p in self.passes)

    @property
    def missing(self) -> int:
        return sum(p.missing for p in self.passes)

    @property
    def uneven(self) -> list[GeneratorCoverage]:
        """Item types lagging behind the best far enough to be a skew.

        Measured against the best rather than against completeness: while the run
        is in progress everything lags at once and that is the normal course of
        things. A skew is when some have gone ahead and others stand still.
        """
        if len(self.coverage) < 2:
            return []
        best = max(entry.share for entry in self.coverage)
        if best <= 0:
            return []
        return [entry for entry in self.coverage if best - entry.share > _LAG]

    def advice(self) -> list[str]:
        """What will finish it. Each state has its own remedy."""
        if not self.passes:
            # Nothing collected: not "everything is done".
            return [
                "nothing has been collected yet:",
                f"      uv run syft-benchmark evaluate {self.space}",
            ]
        steps: list[str] = []
        if self.missing or self.failed:
            steps.append(
                f"not asked and failed — ask again:\n"
                f"      uv run syft-benchmark evaluate {self.space} --resume"
            )
        if self.unjudged:
            steps.append(
                f"the judge failed on recorded answers — judge them again:\n"
                f"      uv run syft-benchmark judge {self.space}"
            )
        if self.pending:
            steps.append(
                f"answers are awaiting a verdict — judge them:\n"
                f"      uv run syft-benchmark export-judging {self.space} "
                f"--judge <name> --only-pending"
            )
        if not steps:
            steps.append("everything is done — the report can be assembled:")
            steps.append(f"      uv run syft-benchmark report {self.space}")
        if self.uneven:
            steps.insert(
                0,
                "coverage by item type is uneven — the report will compute "
                "shares over a skewed sample:\n      "
                + ", ".join(entry.generator for entry in self.uneven),
            )
        return steps


def collect(
    space: str,
    *,
    total: int,
    frozen: str = "",
    generators: Mapping[str, str] | None = None,
    settings: Settings | None = None,
    since: datetime | None = None,
) -> SpaceStatus:
    """Assemble the state of the measurement for a node.

    Args:
        space: The Space key
        total: How many items are in the selection — the denominator of "not asked"
        frozen: The path of the frozen slice, if the selection is pinned by one
        generators: Item -> its generator; without them coverage by item type is
            not computed
        settings: The process settings
        since: Count runs no earlier than this moment; None — all of them

    Returns:
        A SpaceStatus with the breakdown by combination and advice on what will
        finish it
    """
    conf = settings or get_settings()

    where = [Run.space == space]
    if since is not None:
        where.append(Run.started_at >= since)

    with session_scope(conf) as session:
        runs = session.execute(
            select(
                Run.id,
                Run.context_mode,
                Run.context_source,
                Run.block,
                Run.model,
                Run.judge_model,
            ).where(*where)
        ).all()
        if not runs:
            return SpaceStatus(space=space, total=total, frozen=frozen, passes=[])

        rows = session.execute(
            select(
                Result.run_id,
                Result.qa_id,
                Result.answer,
                Result.verdict,
            )
            .where(Result.run_id.in_([run.id for run in runs]))
            .order_by(Result.created_at)
        ).all()

    # There can be several runs per combination — resuming creates a new one —
    # while a combination has one state. We fold by the report key.
    key_of = {
        run.id: (
            run.context_mode,
            run.context_source,
            run.block,
            run.model,
            run.judge_model,
        )
        for run in runs
    }

    # The latest record per question — by the same rule the report selects with.
    # The walk goes in ascending time order, so the next one overrides the
    # previous. A stored arm that is not measured has no state to report.
    freshest: dict[tuple[object, ...], _RowState] = {}
    for row in rows:
        key = key_of[row.run_id]
        if _known_arm(key[0]) is not None:
            freshest[(*key, row.qa_id)] = _state(
                str(row.answer or ""), str(row.verdict or "")
            )

    tally: dict[tuple[object, ...], dict[_RowState, int]] = {}
    for full_key, state in freshest.items():
        counts = tally.setdefault(full_key[:-1], dict.fromkeys(_RowState, 0))
        counts[state] += 1

    passes = [
        PassStatus(
            context_mode=ContextMode(str(key[0])),
            block=EvalBlock(str(key[2])),
            model=str(key[3]),
            judge=str(key[4]),
            total=total,
            graded=counts[_RowState.GRADED],
            failed=counts[_RowState.FAILED],
            pending=counts[_RowState.PENDING],
            unjudged=counts[_RowState.UNJUDGED],
        )
        for key, counts in tally.items()
    ]
    passes.sort(key=lambda p: (p.context_mode.value, p.block.value, p.model, p.judge))
    return SpaceStatus(
        space=space,
        total=total,
        frozen=frozen,
        passes=passes,
        coverage=_coverage(freshest, generators or {}, len(passes)),
    )


def _coverage(
    freshest: dict[tuple[object, ...], _RowState],
    generators: Mapping[str, str],
    passes: int,
) -> list[GeneratorCoverage]:
    """How many verdicts were obtained per item type, out of how many needed.

    The denominator is the items of that type multiplied by the number of runs: a
    verdict is needed from every run, not one for all of them.
    """
    if not generators or not passes:
        return []

    in_set: dict[str, int] = {}
    for generator in generators.values():
        in_set[generator] = in_set.get(generator, 0) + 1

    graded: dict[str, int] = dict.fromkeys(in_set, 0)
    for key, state in freshest.items():
        if state is not _RowState.GRADED:
            continue
        found = generators.get(str(key[-1]))
        if found is not None:
            graded[found] = graded.get(found, 0) + 1

    entries = [
        GeneratorCoverage(
            generator=generator,
            in_set=count,
            graded=graded.get(generator, 0),
            expected=count * passes,
        )
        for generator, count in in_set.items()
    ]
    entries.sort(key=lambda e: (e.share, e.generator))
    return entries


def _known_arm(value: Any) -> ContextMode | None:
    """The arm a stored ``context_mode`` names; None where it names none."""
    try:
        return ContextMode(str(value))
    except ValueError:
        return None


class _RowState(StrEnum):
    """The recorded state of one question's latest row."""

    GRADED = "graded"
    FAILED = "failed"
    UNJUDGED = "unjudged"
    PENDING = "pending"


def _state(answer: str, verdict: str) -> _RowState:
    """Which of the four recorded states a row belongs to."""
    if is_error(answer):
        return _RowState.FAILED
    if is_technical(verdict):
        return _RowState.UNJUDGED
    if verdict == Verdict.PENDING.value:
        return _RowState.PENDING
    return _RowState.GRADED
