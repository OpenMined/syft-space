"""The set's stability: same material, different questions — same numbers?

The benchmark measures a model with questions it composed itself, and that is
its weak spot. A gold answer can be inaccurate, a wording ambiguous, and the
generator is of the same breed as the models under test and errs in similar
ways. The questions cannot be checked directly: that would take other questions.

Indirectly they can be, and the answer comes out convincing. We take the same
material and build a set over it afresh, as a separate cohort. The corpus is the
same, the endpoint is the same, the models under test are the same, the judge is
the same. One thing changes — the pool of questions. Then:

  * **the numbers matched** — the questions are beside the point, and the
    difference between models speaks about the models;
  * **the numbers diverged** — then they speak about the questions. Where
    exactly to look is hinted at by the screening rate: a generator that had a
    third of its gold answers rejected probably did not build the other two
    thirds any better.

Cohorts have to be compared over items that are no longer in the measurement:
the previous pool has been taken out but not deleted — it is kept for exactly
this comparison. So the computation goes past the ordinary "what is in the
measurement now" selection and takes a cohort by name.

**What this comparison does not prove.** Matching numbers do not mean the
questions are good: two passes of one and the same model over one prompt will
err identically, and the match will mean no more than the reproducibility of the
error. The comparison becomes convincing when the cohorts are built by DIFFERENT
generators: that is a real independent check rather than a repeat.
"""

from __future__ import annotations

from dataclasses import dataclass

from syft_benchmark.config import ContextMode, EvalBlock, ExpectedBehavior
from syft_benchmark.generation.cohort import Cohort
from syft_benchmark.generation.cohort import listing as cohort_listing
from syft_benchmark.report.metrics import Metrics, summarize

# How far the shares of two cohorts may diverge before the divergence stops
# being explainable by sampling. The value comes not from the literature but
# from the report in practice: up to ten points between sets over the same
# material is the ordinary spread; beyond that, it is grounds for looking at the
# questions rather than at the model.
DIVERGENCE_LIMIT = 0.10


@dataclass(frozen=True, slots=True)
class CohortRun:
    """The metrics of one cohort in one arm and block."""

    cohort: Cohort
    metrics: Metrics


@dataclass(frozen=True, slots=True)
class Comparison:
    """A comparison of cohorts for one (arm, block, model, judge) combination."""

    space: str
    context_mode: ContextMode
    block: EvalBlock
    model: str
    judge: str
    runs: list[CohortRun]

    @property
    def spread(self) -> float:
        """The spread of accuracy between the cohorts."""
        values = [run.metrics.accuracy for run in self.runs]
        return max(values) - min(values) if len(values) > 1 else 0.0

    @property
    def hallucination_spread(self) -> float:
        values = [run.metrics.hallucination_rate for run in self.runs]
        return max(values) - min(values) if len(values) > 1 else 0.0

    @property
    def suspect(self) -> bool:
        """Whether to look at the questions rather than at the model.

        We look at the worse of the two spreads: a set whose accuracy matched
        but whose share of inventions diverged twofold is a diverged set too.
        """
        return max(self.spread, self.hallucination_spread) > DIVERGENCE_LIMIT

    @property
    def built_by_different_generators(self) -> bool:
        """Whether the cohorts were built by different generators.

        What the comparison proves at all depends on this: a repeat of one model
        over one prompt reproduces its own errors as well, whereas different
        generators are an independent check.
        """
        return len({run.cohort.built_by for run in self.runs}) > 1


def compare(
    space: str,
    mode: ContextMode,
    block: EvalBlock = EvalBlock.DIRECT,
    model: str | None = None,
    judge: str | None = None,
    expected: ExpectedBehavior = ExpectedBehavior.ANSWER,
) -> Comparison | None:
    """Compare the cohorts for one combination.

    Args:
        space: The Space key
        mode: The measurement arm
        block: The test block
        model: The answerer; None — all of them
        judge: The judge; None — every verdict alike
        expected: Which half of the set

    Returns:
        A Comparison if at least two cohorts have verdicts; otherwise None —
        there is nothing to compare, and it is too early to speak of stability
    """
    runs: list[CohortRun] = []
    for cohort in cohort_listing(space):
        metrics = summarize(
            space, mode, block, model, judge, expected, cohort=cohort.label
        )
        if metrics is not None and metrics.graded:
            runs.append(CohortRun(cohort=cohort, metrics=metrics))

    if len(runs) < 2:
        return None
    return Comparison(
        space=space,
        context_mode=mode,
        block=block,
        model=model or "",
        judge=judge or "",
        runs=runs,
    )


def lines(comparison: Comparison | None) -> list[str]:
    """The Markdown section "the set's stability"."""
    if comparison is None:
        return []

    out = [
        "",
        "## The stability of the set",
        "",
        "One and the same material, different pools of questions. The corpus,",
        "the endpoint, the models under test and the judge are the same — only",
        "the questions change. If the numbers matched, the difference between",
        "models speaks about the models; if they diverged, about the questions.",
        "",
        "| Cohort | Built by | Items | Screened out | Accuracy | Inventions |",
        "| --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for run in comparison.runs:
        share = (
            f"{run.cohort.rejected / run.cohort.pairs:.0%}" if run.cohort.pairs else "—"
        )
        out.append(
            f"| {run.cohort.name} | {run.cohort.models} | {run.metrics.graded} "
            f"| {share} | {run.metrics.accuracy:.0%} "
            f"| {run.metrics.hallucination_rate:.0%} |"
        )

    out += ["", f"The spread of accuracy between cohorts is {comparison.spread:.0%}."]
    if comparison.suspect:
        out.append(
            f"That is more than {DIVERGENCE_LIMIT:.0%}, and the material is one "
            f"and the same. So the divergence speaks not about the model under "
            f"test but about the questions and the gold answers: look at the "
            f"screening rate and at the items of the cohort that stands out."
        )
        if not comparison.built_by_different_generators:
            out.append(
                "Note that the cohorts were built by one generator: it is "
                "unstable in itself, and the divergence is its own spread "
                "rather than an argument between two independent opinions "
                "about the material."
            )
    else:
        out.append(
            "The set is stable: the pool of questions does not affect the "
            "numbers, and the difference between models can be read as a "
            "difference between models."
        )
        if not comparison.built_by_different_generators:
            out.append(
                "But that proves less than it seems: the cohorts were built by "
                "one generator, and a match means the reproducibility of its "
                "decisions, not their correctness. An independent check is a "
                "cohort built by a DIFFERENT model."
            )
    return out
