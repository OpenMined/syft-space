"""The cuts of a Space's metrics: by item type, judge agreement, text scores.

A summary share says how many times the model erred; these cuts say where it
erred and whether the judges that counted it agree. They are computed over the
same counted verdict per question as the whole report, and over one half of
the set at a time: mixing the halves gives a share that drops simply because
there came to be more control questions.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from itertools import combinations

from sqlalchemy import select

from syft_benchmark.config import (
    ARM_LETTER,
    ContextMode,
    EvalBlock,
    ExpectedBehavior,
    Verdict,
)
from syft_benchmark.db import QaPair, session_scope
from syft_benchmark.report.counted import OUTCOMES
from syft_benchmark.report.metrics import (
    Metrics,
    VerdictShares,
    judges_seen,
    latest_results,
)
from syft_benchmark.runs.judge import is_technical
from syft_benchmark.runs.textmetrics import average

# Below this judge agreement comparing models with one another is meaningless:
# the difference is smaller than the spread of the assessments themselves. The
# value comes not from the literature but from the meaning: at an agreement of
# 0.7 every third verdict is disputable.
AGREEMENT_FLOOR = 0.7


# The generators whose correct answer is picked from ready-made options. They
# have a GUESSING FLOOR: four options in `mcq` give 25% correct answers blind,
# three in `two_truths_one_lie` give 33%. For accuracy this is no obstacle: the
# floor is the same for everyone under test, and the comparison between them does
# not suffer from it. But for "how public the corpus is" it is the whole quantity
# being measured, because there a correct answer in arm A is READ as the model
# being acquainted with the corpus.
CHOICE_GENERATORS = frozenset({"mcq", "two_truths_one_lie"})

# The guessing floor by the number of options — so that it can be said how far a
# multiple-choice result differs from tossing a coin.
GUESS_FLOOR = {"mcq": 0.25, "two_truths_one_lie": 1 / 3}


@dataclass(frozen=True, slots=True)
class Exposure:
    """How far the corpus is already familiar to the model — and how sure we are.

    The quantity is computed over arm A, where the model does not see corpus
    chunks, and a correct answer there means one of three things: the fact is
    common knowledge, the corpus made it into training, or the model guessed.
    There is nothing to tell the first two apart — and the report does not hide
    that. The third CAN be separated out, and not separating it means recording
    the arithmetic of the number of options as corpus publicity.
    """

    free_form: float | None
    free_form_graded: int
    choice: float | None
    choice_graded: int
    choice_floor: float

    @property
    def above_guessing(self) -> float | None:
        """How far a multiple choice beat blind guessing."""
        if self.choice is None:
            return None
        return self.choice - self.choice_floor


def corpus_exposure(
    space: str,
    *,
    model: str | None = None,
    judge: str | None = None,
) -> Exposure:
    """Corpus publicity separately: free answer and multiple choice.

    Computed over arm A and over the answerable half only.

    A free answer has no guessing floor: the span either matches the gold answer
    or it does not, and a correct answer without access to the corpus means
    exactly what it says — the model knew. That is the publicity estimate.

    Multiple choice has a floor, and a considerable one. It goes on a separate
    line so that the reader sees what to compare against: 27% on four options is
    zero knowledge, not "the corpus is a quarter known".

    Args:
        space: The Space key
        model: The model under test; None — all
        judge: The judge; None — the counted verdict (primary judge)

    Returns:
        An Exposure; ``None`` in a share means there were no such items
    """
    rows = by_generator(
        space,
        ContextMode.CLOSED_BOOK,
        EvalBlock.DIRECT,
        model=model,
        judge=judge,
    )

    free_correct = free_graded = 0
    choice_correct = choice_graded = 0
    weighted_floor = 0.0
    for row in rows:
        if row.generator in CHOICE_GENERATORS:
            choice_correct += row.correct
            choice_graded += row.graded
            weighted_floor += GUESS_FLOOR.get(row.generator, 0.25) * row.graded
        else:
            free_correct += row.correct
            free_graded += row.graded

    return Exposure(
        free_form=free_correct / free_graded if free_graded else None,
        free_form_graded=free_graded,
        choice=choice_correct / choice_graded if choice_graded else None,
        choice_graded=choice_graded,
        choice_floor=weighted_floor / choice_graded if choice_graded else 0.0,
    )


@dataclass(frozen=True, slots=True)
class GeneratorSlice(VerdictShares):
    """The shares of one generator within one arm and block."""

    generator: str
    graded: int
    correct: int
    abstain: int
    hallucinate: int
    failed: int
    # Control answers its web search supports: graded, not a hallucination.
    web_sourced: int = 0
    # Explanations short of the key-facts bar: graded, neither right nor wrong.
    incomplete: int = 0


@dataclass(frozen=True, slots=True)
class JudgePair:
    """How far two judges agreed on one and the same answers."""

    left: str
    right: str
    shared: int
    agreed: int

    @property
    def rate(self) -> float:
        return self.agreed / self.shared if self.shared else 0.0


def by_generator(
    space: str,
    mode: ContextMode,
    block: EvalBlock = EvalBlock.DIRECT,
    model: str | None = None,
    judge: str | None = None,
    expected: ExpectedBehavior | None = ExpectedBehavior.ANSWER,
    job: str | None = None,
) -> list[GeneratorSlice]:
    """The shares per generator within one arm.

    The generator lives on the item, not on the verdict, and that is right: the
    item type is a property of the question, not of the run. So it is pulled in by
    a separate query rather than copied into every result row.

    Args:
        space: The Space key
        mode: The measurement arm
        block: The test block
        model: The answerer; None — all
        judge: The judge; None — the counted verdict (primary judge)
        expected: Which half of the set; None — both (rarely meaningful)
        job: Narrow it to one launch; None — whatever is graded now

    Returns:
        One row per generator, from the worst accuracy to the best; a generator
        not asked has no row (a row at zero means asked and all wrong)
    """
    rows = latest_results(space, mode, block, model, judge, expected, job=job)
    if not rows:
        return []

    with session_scope() as session:
        generators: dict[str, str] = {
            str(row.id): str(row.generator)
            for row in session.execute(
                select(QaPair.id, QaPair.generator).where(
                    QaPair.id.in_([r.qa_id for r in rows])
                )
            ).all()
        }

    tally: dict[str, Counter[str]] = {}
    for row in rows:
        key = str(generators.get(row.qa_id) or "—")
        # Failed calls leave the denominator by the same mark as in the summary.
        tally.setdefault(key, Counter())[row.verdict] += 1

    slices = [
        GeneratorSlice(
            generator=key,
            graded=sum(counts[v] for v in OUTCOMES),
            correct=counts[Verdict.CORRECT.value],
            abstain=counts[Verdict.ABSTAIN.value],
            hallucinate=counts[Verdict.HALLUCINATE.value],
            failed=counts[Verdict.TECHNICAL.value],
            web_sourced=counts[Verdict.WEB_SOURCED.value],
            incomplete=counts[Verdict.INCOMPLETE.value],
        )
        for key, counts in tally.items()
    ]
    # Worst first: a report is read for what is broken.
    slices.sort(key=lambda s: (s.accuracy, s.generator))
    return slices


def judge_agreement(
    space: str,
    mode: ContextMode,
    block: EvalBlock = EvalBlock.DIRECT,
    model: str | None = None,
    expected: ExpectedBehavior | None = ExpectedBehavior.ANSWER,
    job: str | None = None,
) -> list[JudgePair]:
    """How far the judges agreed, pairwise.

    Computed over the questions BOTH judges saw: a recusal and an interrupted run
    leave the judges with different sets, and dividing agreement by the full set
    would mean recording someone else gap as a disagreement.

    Args:
        space: The Space key
        mode: The measurement arm
        block: The test block
        model: The answerer; None — all
        expected: Which half of the set
        job: Narrow it to one launch; None — whatever is graded now

    Returns:
        One row per pair of judges; empty if there is only one judge
    """
    judges = judges_seen(space, mode, block, job)
    if len(judges) < 2:
        return []

    verdicts: dict[str, dict[str, str]] = {}
    for name in judges:
        rows = latest_results(space, mode, block, model, name, expected, job=job)
        verdicts[name] = {
            row.qa_id: row.verdict
            for row in rows
            # A failure is not a judge opinion, and cannot be a disagreement.
            if not is_technical(row.verdict) and row.verdict != Verdict.PENDING.value
        }

    pairs: list[JudgePair] = []
    for left, right in combinations(judges, 2):
        shared = set(verdicts[left]) & set(verdicts[right])
        if not shared:
            continue
        agreed = sum(1 for qa in shared if verdicts[left][qa] == verdicts[right][qa])
        pairs.append(
            JudgePair(left=left, right=right, shared=len(shared), agreed=agreed)
        )

    pairs.sort(key=lambda p: p.rate)
    return pairs


def average_agreement(pairs: list[JudgePair]) -> float | None:
    """The average agreement across all pairs of judges.

    Weighted by the number of shared questions: a pair that agreed on three
    questions must not count as much as a pair that agreed on a hundred.
    """
    shared = sum(p.shared for p in pairs)
    if not shared:
        return None
    return sum(p.agreed for p in pairs) / shared


def _combos(results: list[Metrics]) -> list[tuple[str, ContextMode, EvalBlock, str]]:
    """The combinations it makes sense to compute the cut for.

    Only the answerable half and only the rows where someone was assessed: on the
    control half "accuracy by generator" is a quantity that does not exist, and an
    empty row takes up space and says nothing. One entry per combination whatever
    the judge: the cuts are over the counted verdict.
    """
    seen: list[tuple[str, ContextMode, EvalBlock, str]] = []
    for m in results:
        if m.expected is not ExpectedBehavior.ANSWER or not m.graded:
            continue
        key = (m.space, m.context_mode, m.block, m.model)
        if key not in seen:
            seen.append(key)
    return seen


def _arm_label(mode: ContextMode) -> str:
    return f"{ARM_LETTER.get(mode.value, '?')} {mode.value}"


@dataclass(frozen=True, slots=True)
class GeneratorRow:
    """One generator's shares within one combination of the report."""

    space: str
    arm: str
    block: str
    model: str
    entry: GeneratorSlice


@dataclass(frozen=True, slots=True)
class AgreementRow:
    """One pair of judges within one combination of the report."""

    space: str
    arm: str
    model: str
    pair: JudgePair


def generator_rows(results: list[Metrics]) -> list[GeneratorRow]:
    """The cut by item type for every combination of ``results``: the rows of
    the "by item type" section, whichever renderer draws it.

    The summary answers how many times the model erred; this cut answers where
    exactly. A model can hold dates confidently and fall apart on connecting
    facts, while in the summary that is one share, by which there is nothing to
    fix.
    """
    rows: list[GeneratorRow] = []
    for space, mode, block, model in _combos(results):
        for entry in by_generator(space, mode, block, model or None):
            if entry.graded:
                rows.append(
                    GeneratorRow(space, _arm_label(mode), block.value, model, entry)
                )
    return rows


def agreement_rows(results: list[Metrics]) -> list[AgreementRow]:
    """Judge agreement for every combination of ``results``: the rows of the
    "judge agreement" section, whichever renderer draws it.

    Columns with different verdicts show that the judges diverged but not by how
    much. If they diverge on a third of the questions, any difference between
    models smaller than a third is noise, and the reader has to be told so before
    comparing percentages.
    """
    return [
        AgreementRow(space, _arm_label(mode), model, pair)
        for space, mode, block, model in _combos(results)
        for pair in judge_agreement(space, mode, block, model or None)
    ]


@dataclass(frozen=True, slots=True)
class TextScores:
    """The average similarity measures of an answer to the gold one, per combination."""

    space: str
    arm: str
    block: str
    model: str
    judge: str
    counted: int
    scores: dict[str, float]


def text_scores(results: list[Metrics]) -> list[TextScores]:
    """The average text metrics where they were computed.

    They enter no share of the report and therefore live in a separate table:
    mixing them with accuracy would hint that resemblance to the gold answer is
    correctness, which is exactly what they are not.
    """
    out: list[TextScores] = []
    for m in results:
        if not m.graded:
            continue
        rows = latest_results(
            m.space,
            m.context_mode,
            m.block,
            m.model or None,
            m.judge or None,
            m.expected,
        )
        records = [
            (r.extra or {}).get("text_metrics")
            for r in rows
            if (r.extra or {}).get("text_metrics")
        ]
        if not records:
            continue
        out.append(
            TextScores(
                space=m.space,
                arm=m.arm_label,
                block=m.block.value,
                model=m.model or m.endpoint or "—",
                judge=m.judge,
                counted=len(records),
                scores=average(records),  # type: ignore[arg-type]
            )
        )
    return out
