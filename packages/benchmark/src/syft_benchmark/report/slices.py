"""Two cuts, without which the summary answers the wrong question.

A summary share says "how many times the model erred". The node owner and an
auditor need something else: **where** it erred and **whether whoever counted it**
can be trusted. Both cuts are ports from LiveTruth: ``by_dataset`` and the
analysis of judge bias.

**The cut by generator.** There are ten generators, and they measure different
skills: number masking — precision about a figure, multihop — the ability to
connect two facts, tiered — an extended explanation, the control ones — the
ability to stay silent. One share laid over all ten hides exactly what the owner
needs: a model can hold dates confidently and fall apart on connecting facts,
while in the summary that will be "accuracy 71%". There is nothing to fix by such
a number.

**Judge agreement.** A panel is set up so that the divergence of assessments can
be seen — but by itself the presence of three columns in the report shows
nothing. The question this cut answers is: do the judges agree. If two out of
three diverge on a third of the questions, then any difference between models
smaller than a third is noise, and that has to be said outright rather than
leaving the reader to compare percentages that mean nothing.

Both are computed over the same latest verdict per question as the whole report,
and over the same half of the set: mixing the halves means getting a quantity
that drops simply because there came to be more control questions.
"""

from __future__ import annotations

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
from syft_benchmark.report.metrics import Metrics, _latest_results, judges_seen
from syft_benchmark.runs.judge import is_error
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
        judge: The judge; None — every verdict alike

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
class GeneratorSlice:
    """The shares of one generator within one arm and block."""

    generator: str
    graded: int
    correct: int
    abstain: int
    hallucinate: int
    failed: int

    @property
    def accuracy(self) -> float:
        return self.correct / self.graded if self.graded else 0.0

    @property
    def hallucination_rate(self) -> float:
        return self.hallucinate / self.graded if self.graded else 0.0

    @property
    def abstain_rate(self) -> float:
        return self.abstain / self.graded if self.graded else 0.0


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
        judge: The judge; None — every verdict alike
        expected: Which half of the set; None — both (rarely meaningful)

    Returns:
        One row per generator, from the worst accuracy to the best
    """
    rows = _latest_results(space, mode, block, model, judge, expected)
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

    tally: dict[str, dict[str, int]] = {}
    for row in rows:
        key = str(generators.get(row.qa_id) or "—")
        counts = tally.setdefault(
            key, {"correct": 0, "abstain": 0, "hallucinate": 0, "failed": 0}
        )
        # A failed call is filtered out by the same mark as in the summary: it is
        # recorded with the hallucinate verdict, otherwise it could not be saved —
        # and they cannot be told apart by the verdict.
        if is_error(row.answer):
            counts["failed"] += 1
        elif row.verdict == Verdict.CORRECT.value:
            counts["correct"] += 1
        elif row.verdict == Verdict.ABSTAIN.value:
            counts["abstain"] += 1
        elif row.verdict == Verdict.HALLUCINATE.value:
            counts["hallucinate"] += 1

    slices = [
        GeneratorSlice(
            generator=key,
            graded=counts["correct"] + counts["abstain"] + counts["hallucinate"],
            correct=counts["correct"],
            abstain=counts["abstain"],
            hallucinate=counts["hallucinate"],
            failed=counts["failed"],
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

    Returns:
        One row per pair of judges; empty if there is only one judge
    """
    judges = judges_seen(space, mode, block)
    if len(judges) < 2:
        return []

    verdicts: dict[str, dict[str, str]] = {}
    for name in judges:
        rows = _latest_results(space, mode, block, model, name, expected)
        verdicts[name] = {
            row.qa_id: row.verdict
            for row in rows
            # A failure is not a judge opinion, and cannot be a disagreement.
            if not is_error(row.answer) and row.verdict != Verdict.PENDING.value
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


# --- the report sections ---------------------------------------------------


def _combos(results: list[Metrics]) -> list[tuple[str, ContextMode, EvalBlock, str]]:
    """The combinations it makes sense to compute the cut for.

    Only the answerable half and only the rows where someone was assessed: on the
    control half "accuracy by generator" is a quantity that does not exist, and an
    empty row takes up space and says nothing.
    """
    seen: list[tuple[str, ContextMode, EvalBlock, str]] = []
    for m in results:
        if m.expected is not ExpectedBehavior.ANSWER or not m.graded:
            continue
        key = (m.space, m.context_mode, m.block, m.model)
        if key not in seen:
            seen.append(key)
    return seen


def generator_lines(results: list[Metrics]) -> list[str]:
    """The Markdown section "by item type".

    The summary answers how many times the model erred; this cut answers where
    exactly. A model can hold dates confidently and fall apart on connecting
    facts, while in the summary that will be one share, by which there is nothing
    to fix.
    """
    rows: list[tuple[str, str, str, str, GeneratorSlice]] = []
    for space, mode, block, model in _combos(results):
        arm = f"{ARM_LETTER.get(mode.value, '?')} {mode.value}"
        for entry in by_generator(space, mode, block, model or None):
            if entry.graded:
                rows.append((space, arm, block.value, model or "—", entry))
    if not rows:
        return []

    lines = [
        "",
        "## By item type",
        "",
        "The generators measure different skills: number masking — precision",
        "about a figure, multihop — the ability to connect two facts, tiered —",
        "an extended explanation. One share laid over all of them hides exactly",
        "what the owner needs; worst first.",
        "",
        "| Space | Arm | Block | Model | Item type | Questions | Accuracy "
        "| Hallucinations | Abstentions |",
        "| --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for space, arm, block_name, model, entry in rows:
        lines.append(
            f"| {space} | {arm} | {block_name} | {model} | {entry.generator} "
            f"| {entry.graded} | {entry.accuracy:.0%} "
            f"| {entry.hallucination_rate:.0%} | {entry.abstain_rate:.0%} |"
        )
    return lines


def agreement_lines(results: list[Metrics]) -> list[str]:
    """The Markdown section "judge agreement".

    Three columns with different verdicts show that the judges diverged but not
    by how much. Without that number the reader compares percentages whose
    difference may lie entirely within the spread of the assessments.
    """
    rows: list[tuple[str, str, str, JudgePair]] = []
    for space, mode, block, model in _combos(results):
        for pair in judge_agreement(space, mode, block, model or None):
            rows.append(
                (
                    space,
                    f"{ARM_LETTER.get(mode.value, '?')} {mode.value}",
                    model or "—",
                    pair,
                )
            )
    if not rows:
        return []

    average = average_agreement([pair for *_, pair in rows])
    lines = [
        "",
        "## Judge agreement",
        "",
        "The share of questions on which two judges issued ONE verdict. Computed",
        "over the questions both of them saw: a recusal and an interrupted run",
        "leave the judges with different sets, and someone else gap is not a",
        "disagreement.",
        "",
        "| Space | Arm | Model | Judge | Judge | Shared | Agreement |",
        "| --- | --- | --- | --- | --- | ---: | ---: |",
    ]
    for space, arm, model, pair in rows:
        lines.append(
            f"| {space} | {arm} | {model} | {pair.left} | {pair.right} "
            f"| {pair.shared} | {pair.rate:.0%} |"
        )
    if average is not None:
        lines += ["", f"Average agreement — {average:.0%}."]
        if average < AGREEMENT_FLOOR:
            lines.append(
                f"That is below {AGREEMENT_FLOOR:.0%}: the judges diverge too "
                f"often, and the difference between models is smaller than that "
                f"spread — noise. Models cannot be compared on such a measurement."
            )
    return lines


# --- the text metrics ------------------------------------------------------


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
        rows = _latest_results(
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
                arm=f"{m.arm} {m.context_mode.value}",
                block=m.block.value,
                model=m.model or m.endpoint or "—",
                judge=m.judge,
                counted=len(records),
                scores=average(records),  # type: ignore[arg-type]
            )
        )
    return out


def text_metric_lines(results: list[Metrics]) -> list[str]:
    """The Markdown section "similarity to the gold answer"."""
    rows = text_scores(results)
    if not rows:
        return []

    keys = sorted({key for row in rows for key in row.scores})
    header = " | ".join(keys)
    dashes = " | ".join("---:" for _ in keys)
    lines = [
        "",
        "## Similarity to the gold answer",
        "",
        "Mechanical measures of word overlap. They do NOT know correctness: a",
        "retelling in one own words gets a low score with a correct answer,",
        "while a verbatim quotation off the point gets a high one. They enter no",
        "share of the report and are not published; they are needed as a view of",
        "the same answers that is independent of the judge. Comparing them makes",
        "sense within one report, not against other people numbers.",
        "",
        f"| Space | Arm | Block | Model | Judge | Answers | {header} |",
        f"| --- | --- | --- | --- | --- | ---: | {dashes} |",
    ]
    for row in rows:
        values = " | ".join(
            f"{row.scores[key]:.3f}" if key in row.scores else "—" for key in keys
        )
        lines.append(
            f"| {row.space} | {row.arm} | {row.block} | {row.model} "
            f"| {row.judge or '—'} | {row.counted} | {values} |"
        )
    return lines
