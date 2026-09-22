"""What is collected, what is missing and what will finish it.

A port of `cmd_status` from LiveTruth `run_console.py`. The point of the command
is one: a measurement runs for hours and gets interrupted, and the first question
after an interruption is "what is already there". Without an answer to it a human
goes into the database by hand or, worse, launches everything again.

It is computed by the same rule the report uses: the latest verdict for each
question. Otherwise "collected" and "in the report" would diverge — and diverge
silently.

Four states are distinguished, and they must not be conflated:

  * **assessed** — there is a verdict;
  * **failed** — there is no answer, the call did not get through. This is a
    hole: the report filters such a row out of the denominator, and ``--resume``
    re-asks it;
  * **awaiting a verdict** — the answer was received, the judge has not seen it
    yet. Happens with deferred judging, and is cured not by rerunning but by
    judging;
  * **not asked** — this question was never put to this judge at all.

Each has its own remedy, and it is printed beside the number: a command unable to
say what to do next saves not time but letters.

Coverage by item type is computed separately, and that is not decoration. An
interrupted run leaves it UNEVEN: questions go in a batch, and by the moment of
interruption some generators have been got through entirely and others not
started. A report assembled over such a state will compute shares over a skewed
sample and will show nothing of it — the share will look like an ordinary share.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime

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
from syft_benchmark.runs.judge import ERROR_PREFIX


@dataclass(frozen=True, slots=True)
class PassStatus:
    """The state of one (arm, block, model, judge) combination."""

    space: str
    context_mode: ContextMode
    context_source: str
    block: EvalBlock
    model: str
    judge: str
    total: int
    graded: int
    failed: int
    pending: int
    last_at: datetime | None

    @property
    def arm(self) -> str:
        return ARM_LETTER.get(self.context_mode.value, "?")

    @property
    def missing(self) -> int:
        """The questions this judge was never asked at all."""
        return max(0, self.total - self.graded - self.failed - self.pending)

    @property
    def done(self) -> bool:
        return self.missing == 0 and self.failed == 0 and self.pending == 0

    def line(self) -> str:
        """One line for the console."""
        parts = [f"assessed {self.graded}"]
        if self.failed:
            parts.append(f"failed {self.failed}")
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


# How far an item type may lag behind the best before this stops being an
# unevenness of progress and becomes a skew of the sample. The value comes from
# practice: on an interruption the lag tends to be a multiple, not a quarter.
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
            # Nothing has been collected at all. "Everything is done" here would
            # be an untruth of exactly the kind the command exists to prevent.
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
                Result.created_at,
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
    # The walk goes in ascending time order, so the next one overrides the previous.
    freshest: dict[tuple[object, ...], tuple[str, datetime]] = {}
    for row in rows:
        freshest[(*key_of[row.run_id], row.qa_id)] = (
            _state(str(row.answer or ""), str(row.verdict or "")),
            row.created_at,
        )

    tally: dict[tuple[object, ...], dict[str, int]] = {}
    last: dict[tuple[object, ...], datetime] = {}
    for full_key, (state, at) in freshest.items():
        key = full_key[:-1]
        counts = tally.setdefault(key, {"graded": 0, "failed": 0, "pending": 0})
        counts[state] += 1
        if at is not None and (key not in last or at > last[key]):
            last[key] = at

    passes = [
        PassStatus(
            space=space,
            context_mode=ContextMode(str(key[0])),
            context_source=str(key[1]),
            block=EvalBlock(str(key[2])),
            model=str(key[3]),
            judge=str(key[4]),
            total=total,
            graded=counts["graded"],
            failed=counts["failed"],
            pending=counts["pending"],
            last_at=last.get(key),
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
    freshest: dict[tuple[object, ...], tuple[str, datetime]],
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
    for key, (state, _at) in freshest.items():
        if state != "graded":
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


def _state(answer: str, verdict: str) -> str:
    """Which of the three states a recorded row belongs to."""
    if answer.startswith(ERROR_PREFIX):
        return "failed"
    if verdict == Verdict.PENDING.value:
        return "pending"
    return "graded"
