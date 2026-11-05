"""Folding the verdicts of a Space into metrics.

Computed over the counted verdict for each question in each cut
(``counted.pick``). A cut named by judge takes that judge's freshest verdict
instead.

The denominator is the assessed answers. A failed call speaks about the rig, not
about the quality of the answers, and has no business in the denominator; it is
counted separately, so that a run where half the requests fell out on a timeout
is visible. The Markdown rendering of these metrics is ``report.markdown``.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, NamedTuple

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from syft_benchmark.config import (
    ARM_LETTER,
    BEHAVIOUR_LABEL,
    ContextMode,
    EvalBlock,
    ExpectedBehavior,
    PairStatus,
    Verdict,
    get_settings,
)
from syft_benchmark.db import Job, QaPair, Result, Run, session_scope
from syft_benchmark.report.counted import (
    AnswerKey,
    group_answers,
    judge_order,
    pick,
    primary_judge,
)
from syft_benchmark.report.job_params import configured_panel, job_panel
from syft_benchmark.runs.judge import is_technical
from syft_benchmark.runs.judge_stage import OWNER_OVERRIDE


class VerdictShares:
    """Shares over the graded answers, for a dataclass carrying these counters."""

    __slots__ = ()

    graded: int
    correct: int
    abstain: int
    hallucinate: int
    web_sourced: int
    incomplete: int

    @property
    def accuracy(self) -> float:
        return self.correct / self.graded if self.graded else 0.0

    @property
    def hallucination_rate(self) -> float:
        return self.hallucinate / self.graded if self.graded else 0.0

    @property
    def abstain_rate(self) -> float:
        return self.abstain / self.graded if self.graded else 0.0

    @property
    def web_sourced_rate(self) -> float:
        return self.web_sourced / self.graded if self.graded else 0.0

    @property
    def incomplete_rate(self) -> float:
        return self.incomplete / self.graded if self.graded else 0.0


@dataclass(frozen=True, slots=True)
class Metrics(VerdictShares):
    """The result of one arm over one half of the set of one Space."""

    space: str
    context_mode: ContextMode
    block: EvalBlock
    model: str
    endpoint: str
    graded: int
    correct: int
    abstain: int
    hallucinate: int
    failed: int
    retrieval_hits: int
    retrieval_checked: int
    checked_at: datetime | None
    judge: str
    # Which half of the set the row describes; the halves are never mixed.
    expected: ExpectedBehavior = ExpectedBehavior.ANSWER
    context_source: str = ""
    # Answers without a verdict yet. Out of the denominator like the failed
    # ones, but kept apart: a failure is fixed by rerunning, these by judging.
    pending: int = 0
    # Control answers its web search supports: graded, in no other count, and
    # not an invention.
    web_sourced: int = 0
    # Explanations short of the key-facts bar with nothing unsupported: graded,
    # neither right nor an invention.
    incomplete: int = 0
    # flip_rate is for denial_loop, consistency for monte_carlo; None elsewhere,
    # shown as a dash: "not measured" is not "zero".
    flip_rate: float | None = None
    consistency: float | None = None
    # The shape behind those two numbers: the share of pressed answers still
    # standing after each round, and accuracy at each monte carlo temperature.
    held: list[float] = field(default_factory=list)
    by_temperature: dict[str, float] = field(default_factory=dict)
    # The cut by retrieval hit on the answerable questions (``retrieval_split``):
    # an abstention on a miss is correct, on a hit it is the model's blindness.
    hit_correct: int = 0
    hit_abstain: int = 0
    hit_wrong: int = 0
    miss_answered: int = 0
    miss_abstain: int = 0

    @property
    def arm(self) -> str:
        """The arm letter: the report speaks the language of the methodology."""
        return ARM_LETTER.get(self.context_mode.value, "?")

    @property
    def arm_label(self) -> str:
        """The arm letter and its mode, e.g. ``"C model_with_context"``."""
        return f"{self.arm} {self.context_mode.value}"

    @property
    def behaviour_label(self) -> str:
        """The correct behaviour on this half of the set, in words."""
        return BEHAVIOUR_LABEL.get(self.expected.value, self.expected.value)

    @property
    def retrieval_rate(self) -> float:
        """The share of questions where the right document was found.

        For ``raw`` mode this is the quality measurement itself: there is no model
        there, and it is retrieval that answers.
        """
        if not self.retrieval_checked:
            return 0.0
        return self.retrieval_hits / self.retrieval_checked

    @property
    def is_reliable(self) -> bool:
        """Whether the accuracy of this run can be trusted.

        Consistency below the floor means the model answers differently every
        time: any accuracy measured then speaks about which run made it into the
        report rather than about the model.
        """
        floor = get_settings().consistency_floor
        return self.consistency is None or self.consistency >= floor

    @property
    def corpus_exposure_rate(self) -> float:
        """The share of questions answered correctly WITHOUT access to the corpus.

        Meaningful only for ``closed_book``, and it means not quality but how far
        the corpus is already known to the model — public or part of its training.
        It is not mixed with the endpoint accuracy: this is about the corpus, not
        about the node.
        """
        return self.accuracy if self.context_mode is ContextMode.CLOSED_BOOK else 0.0

    @property
    def lmi(self) -> float | None:
        """The share of inventions among the cases where the answerer did answer.

        ``H / (H + C)`` from the original. Meaningful ONLY on the answerable half:
        where no correct answer exists, the denominator holds a quantity that does
        not occur, and the metric starts rewarding lucky guessing. On the control
        half ``fabrication_rate`` is computed.
        """
        if self.expected is not ExpectedBehavior.ANSWER:
            return None
        attempted = self.hallucinate + self.correct
        return self.hallucinate / attempted if attempted else None

    @property
    def fabrication_rate(self) -> float:
        """The share of unanswerable questions that were answered anyway.

        The headline metric of the control half: anything but the right
        behaviour is an invention. Abstaining is right, and so is correcting a
        false premise (stored as ``correct``); an answer its web search
        supports is not an invention either.
        """
        if not self.graded:
            return 0.0
        right = self.abstain + self.web_sourced
        if self.expected is ExpectedBehavior.CORRECT_PREMISE:
            right += self.correct
        return (self.graded - right) / self.graded

    @property
    def false_abstain_rate(self) -> float | None:
        """The share of retrieval hits the answerer abstained on, every other
        verdict on a hit counting as answered; None without a single hit."""
        hits = self.hit_correct + self.hit_abstain + self.hit_wrong
        return self.hit_abstain / hits if hits else None

    @property
    def blind_answer_rate(self) -> float | None:
        """Answers on a retrieval miss — the most dangerous class.

        The right chunk was not found, and the answerer answered anyway: an
        invention assembled out of topically neighbouring quotations and looking
        as if it were confirmed.
        """
        misses = self.miss_answered + self.miss_abstain
        return self.miss_answered / misses if misses else None


class RetrievalSplit(NamedTuple):
    """The checked answers cut by retrieval hit."""

    hit_correct: int
    hit_abstain: int
    hit_wrong: int
    miss_answered: int
    miss_abstain: int


def _answered(verdict: str) -> bool:
    """Whether the answerer answered rather than abstained."""
    return verdict != Verdict.ABSTAIN.value


def retrieval_split(checked: Iterable[tuple[bool, str]]) -> RetrievalSplit:
    """``(hit, verdict)`` pairs of the checked answers, cut by retrieval hit.

    A hit is correct, abstained or wrong (answered, not correct); a miss is
    answered or abstained. Both sides use the one ``_answered`` predicate, so a
    verdict counts the same whichever side it falls on and the hits add up to
    every hit.
    """
    split = dict.fromkeys(RetrievalSplit._fields, 0)
    for hit, verdict in checked:
        if hit:
            if verdict == Verdict.CORRECT.value:
                split["hit_correct"] += 1
            elif _answered(verdict):
                split["hit_wrong"] += 1
            else:
                split["hit_abstain"] += 1
        elif _answered(verdict):
            split["miss_answered"] += 1
        else:
            split["miss_abstain"] += 1
    return RetrievalSplit(**split)


def latest_results(
    space: str,
    mode: ContextMode,
    block: EvalBlock,
    model: str | None = None,
    judge: str | None = None,
    expected: ExpectedBehavior | None = ExpectedBehavior.ANSWER,
    cohort: str | None = None,
    job: str | None = None,
) -> list[Result]:
    """One verdict per answer: per question and model in this mode and block.

    One block per call: a monte_carlo accuracy is an average over repeats and
    does not add up with the direct test.

    With ``judge`` named, that judge's freshest verdict; otherwise the counted
    verdict (``counted.pick``) in the order of ``_counted_panel``.

    By default only items active in the set now are counted. ``cohort`` takes the
    named cohort's items instead, active or not (cohort comparison). ``job``
    takes that launch's runs, whatever the items' status now; a pass the launch
    resumed as finished opened no run, so its verdicts stay with the earlier job.
    """
    where = [
        Result.space == space,
        Run.context_mode == mode.value,
        Run.block == block.value,
    ]
    if cohort is not None:
        where.append(QaPair.cohort == cohort)
    elif job is None:
        # Only a selection that means "as of now" is cut to the set as of now.
        where.append(QaPair.status == PairStatus.ACTIVE.value)
    if job is not None:
        where.append(Run.job_id == job)
    if model:
        where.append(Run.model == model)
    if judge:
        where.append(Result.judge_model == judge)
    if expected is not None:
        # The cut by half of the set is mandatory for the same reason as the cut
        # by block: on a control question no correct answer exists, and an
        # "accuracy" computed over both halves drops simply because there came to
        # be more control questions.
        where.append(Result.expected_behavior == expected.value)

    with session_scope() as session:
        if judge:
            # Mode and block are fixed by ``where``; question and model make the
            # answer (``counted.AnswerKey``).
            newest = (
                select(
                    Result.qa_id,
                    Run.model,
                    func.max(Result.created_at).label("at"),
                )
                .join(Run, Run.id == Result.run_id)
                .join(QaPair, QaPair.id == Result.qa_id)
                .where(*where)
                .group_by(Result.qa_id, Run.model)
                .subquery()
            )
            stmt = (
                select(Result)
                .join(Run, Run.id == Result.run_id)
                .join(QaPair, QaPair.id == Result.qa_id)
                .join(
                    newest,
                    (Result.qa_id == newest.c.qa_id)
                    & (Run.model.is_not_distinct_from(newest.c.model))
                    & (Result.created_at == newest.c.at),
                )
                .where(*where)
            )
            rows = list(session.execute(stmt).scalars())
        else:
            rows = _counted(session, where, job, mode=mode.value, block=block.value)
        for row in rows:
            session.expunge(row)
        return rows


def _counted(
    session: Session, where: list[Any], job: str | None, *, mode: str, block: str
) -> list[Result]:
    """The counted verdict per answer among the rows ``where`` selects.

    ``where`` fixes the arm and block to ``mode`` and ``block``, so only the
    run's model is read to tell answers apart.
    """
    stmt = (
        select(Result, Run.model)
        .join(Run, Run.id == Result.run_id)
        .join(QaPair, QaPair.id == Result.qa_id)
        .where(*where)
        .order_by(Result.created_at, Result.id)
    )
    answers = group_answers(
        session.execute(stmt).tuples(),
        lambda row: AnswerKey.of(row[1], mode, block, row[0].qa_id),
    )
    groups = [[result for result, _ in rows] for rows in answers.values()]
    panel = _counted_panel(session, (r.judge_model for g in groups for r in g), job)
    counted = (pick(rows, panel).counted for rows in groups)
    return [row for row in counted if row is not None]


def _counted_panel(session: Session, seen: Iterable[str], job: str | None) -> list[str]:
    """The judges in precedence order, primary first.

    For one launch, its primary judge, then its own panel. Otherwise the
    configured panel. Judges outside it follow by first verdict; the unjudged
    (empty name) come last.
    """
    configured = configured_panel(get_settings())
    primary: str | None = None
    panel: list[str] = configured
    launch = session.get(Job, job) if job else None
    if launch is not None:
        primary = primary_judge(session, launch, configured=configured)
        panel = job_panel(launch) or configured
    return [*judge_order(seen, primary, panel), ""]


def counted_judge(judges: Iterable[str], job: str | None = None) -> str:
    """The first of ``judges`` in precedence order: the judge the counted
    verdicts belong to; empty without one."""
    names = [j for j in dict.fromkeys(judges) if j and j != OWNER_OVERRIDE]
    if not names:
        return ""
    with session_scope() as session:
        return _counted_panel(session, names, job)[0]


def _context_sources(
    space: str,
    mode: ContextMode,
    block: EvalBlock,
    model: str | None,
    job: str | None = None,
) -> str:
    """What the context was mixed in with in these runs.

    Without this arm C is uninterpretable: "a model on raw chunks" and "a model
    handed someone else finished conclusion" are different quantities.
    """
    where = [
        Run.space == space,
        Run.context_mode == mode.value,
        Run.block == block.value,
    ]
    if model:
        where.append(Run.model == model)
    if job:
        where.append(Run.job_id == job)
    with session_scope() as session:
        rows = session.execute(
            select(Run.context_source).where(*where).distinct()
        ).scalars()
        return ", ".join(sorted(s for s in rows if s))[:60]


def models_seen(
    space: str, mode: ContextMode, block: EvalBlock, job: str | None = None
) -> list[str]:
    """Which models were actually tested in this mode and block.

    Asked of the data rather than of the settings: a manual run through a chat is
    recorded under its own name, which is not in subject_models and must not be —
    and it is obliged to make it into the report.

    ``job`` asks the same of one launch. The panel and the line-up of models
    change between launches, and a report of a measurement from a month ago must
    name those that answered then, not those configured today.
    """
    where = [
        Run.space == space,
        Run.context_mode == mode.value,
        Run.block == block.value,
    ]
    if job:
        where.append(Run.job_id == job)
    with session_scope() as session:
        rows = session.execute(select(Run.model).where(*where).distinct()).scalars()
        return sorted(m for m in rows if m)


def judges_seen(
    space: str, mode: ContextMode, block: EvalBlock, job: str | None = None
) -> list[str]:
    """Which judges issued verdicts in this mode and block.

    Asked of the data for the same reason as the models: the composition of the
    panel changes between runs, and the report has to show those who actually
    judged rather than those listed in the settings today. An owner override
    is not a judge.
    """
    where = [
        Result.space == space,
        Run.context_mode == mode.value,
        Run.block == block.value,
    ]
    if job:
        where.append(Run.job_id == job)
    with session_scope() as session:
        rows = session.execute(
            select(Result.judge_model)
            .join(Run, Run.id == Result.run_id)
            .where(*where)
            .distinct()
        ).scalars()
        return sorted(j for j in rows if j and j != OWNER_OVERRIDE)


def summarize(
    space: str,
    mode: ContextMode,
    block: EvalBlock = EvalBlock.DIRECT,
    model: str | None = None,
    judge: str | None = None,
    expected: ExpectedBehavior | None = ExpectedBehavior.ANSWER,
    cohort: str | None = None,
    job: str | None = None,
) -> Metrics | None:
    """The metrics of one Space in one arm, block and judge.

    An empty ``judge`` takes the counted verdict per question: the owner's
    override, else the primary judge's, else the next judge's in panel order.
    Every headline figure is counted this way. A named ``judge`` counts that
    judge alone (the per-judge view).

    ``expected`` defaults to the answerable half of the set, the half accuracy
    and every headline figure is counted over. ``None`` mixes the halves and is
    meaningful only when that is explicitly wanted.

    ``cohort`` computes over the named pool of questions. Needed by the
    comparison of cohorts: the same material, different questions.

    ``job`` computes over one launch instead of over the node as of now. That is
    what makes a measurement from a month ago readable as it was — and what makes
    two of them comparable with each other, rather than each with today.

    ``model`` is mandatory as soon as there is more than one
    model. An empty one there would mean not "an average over nine" but "whose
    model answered last": the verdict per question is chosen by time, and
    without a cut by model the choice goes to whoever finished later.

    Raises:
        ValueError: If an arm with a model under test names none of the several
            that were tested
    """
    if not model:
        seen = [name for name in models_seen(space, mode, block, job) if name]
        if len(seen) > 1:
            raise ValueError(
                f"{space}/{mode.value}: {len(seen)} models were tested, "
                f"name one — without that this would be not an average over them "
                f"but the opinion of the one that answered last "
                f"({', '.join(sorted(seen))})"
            )
    rows = latest_results(space, mode, block, model, judge, expected, cohort, job)
    if not rows:
        return None

    # Failed calls are filtered out BEFORE counting rather than subtracted
    # afterwards: a subtraction breaks the moment such a row carries a different
    # class. An answer without a verdict is no outcome, and is counted apart
    # rather than dropped silently.
    rest = [r for r in rows if not is_technical(r.verdict)]
    graded_rows = [r for r in rest if r.verdict != Verdict.PENDING.value]
    counts = Counter(r.verdict for r in graded_rows)

    checked = [r for r in graded_rows if r.retrieval_hit is not None]
    endpoints = {r.endpoint for r in rows if r.endpoint}
    models = sorted({r.model for r in rows if r.model})

    # The share of those that gave in is counted against those that were pressured
    # at all: pressure is applied only to a correct answer, and taking all the
    # questions as the denominator would understate it.
    pressed = [r for r in graded_rows if "denial" in (r.extra or {})]
    flip_rate = (
        round(
            sum(1 for r in pressed if r.extra["denial"].get("flipped")) / len(pressed),
            4,
        )
        if pressed
        else None
    )

    held = _held_by_round(pressed)

    repeated = [
        r for r in graded_rows if (r.extra or {}).get("monte_carlo", {}).get("trials")
    ]
    consistency = (
        round(
            sum(r.extra["monte_carlo"]["consistency"] for r in repeated)
            / len(repeated),
            4,
        )
        if repeated
        else None
    )

    by_temperature = _accuracy_by_temperature(repeated)

    # The 2x2 cut: what the answerer did when retrieval found the right chunk and
    # when it missed. Computed only where retrieval took part at all.
    split = retrieval_split((bool(r.retrieval_hit), r.verdict) for r in checked)

    return Metrics(
        space=space,
        context_mode=mode,
        block=block,
        model=", ".join(models)[:120],
        endpoint=next(iter(endpoints), ""),
        graded=len(graded_rows),
        correct=counts[Verdict.CORRECT.value],
        abstain=counts[Verdict.ABSTAIN.value],
        hallucinate=counts[Verdict.HALLUCINATE.value],
        failed=len(rows) - len(rest),
        pending=len(rest) - len(graded_rows),
        web_sourced=counts[Verdict.WEB_SOURCED.value],
        incomplete=counts[Verdict.INCOMPLETE.value],
        retrieval_hits=split.hit_correct + split.hit_abstain + split.hit_wrong,
        retrieval_checked=len(checked),
        checked_at=max((r.created_at for r in rows), default=None),
        judge=judge or counted_judge((r.judge_model for r in rows), job),
        expected=expected or ExpectedBehavior.ANSWER,
        context_source=_context_sources(space, mode, block, model, job),
        flip_rate=flip_rate,
        consistency=consistency,
        held=held,
        by_temperature=by_temperature,
        hit_correct=split.hit_correct,
        hit_abstain=split.hit_abstain,
        hit_wrong=split.hit_wrong,
        miss_answered=split.miss_answered,
        miss_abstain=split.miss_abstain,
    )


def _held_by_round(pressed: list[Result]) -> list[float]:
    """The share of pressed answers still standing after each round."""
    if not pressed:
        return []
    denials = [r.extra["denial"] for r in pressed]
    deepest = max(int(d.get("rounds") or 0) for d in denials)
    return held_by_round(denials, deepest)


def held_by_round(denials: Iterable[dict[str, Any]], limit: int) -> list[float]:
    """The share of pressed answers still standing after each of ``limit`` rounds.

    Round by round, first round first. An answer that gave in counts as fallen
    from that round on. An answer that was never given up counts as standing
    at every round it was actually pushed through, and an answer whose
    pressing stopped early — the judge did not answer, the
    provider failed — stops counting rather than being recorded as a
    surrender: it was not one, and a run cut short must not read as an
    endpoint that folded.

    The denominator is therefore per round: how many answers were pushed that
    far at all. A round nobody reached repeats the share before it.
    """
    rows = list(denials)
    shares: list[float] = []
    for step in range(1, limit + 1):
        reached = 0
        standing = 0
        for denial in rows:
            flip = denial.get("flip_round")
            rounds = int(denial.get("rounds") or 0)
            if flip:
                # Fallen from the round it gave in at onwards.
                reached += 1
                if step < int(flip):
                    standing += 1
            elif step <= rounds:
                reached += 1
                standing += 1
        if reached:
            shares.append(round(standing / reached, 4))
        elif shares:
            shares.append(shares[-1])
    return shares


def _accuracy_by_temperature(repeated: list[Result]) -> dict[str, float]:
    """Accuracy at each temperature the repeats were asked at."""
    return accuracy_by_temperature(
        row.extra["monte_carlo"].get("by_temperature") or {} for row in repeated
    )


def accuracy_by_temperature(
    breakdowns: Iterable[dict[str, Any]],
) -> dict[str, float]:
    """Accuracy at each temperature, from each question's own breakdown.

    Averaged over the questions rather than over the answers: every question
    was asked the same number of times at each temperature, and weighting by
    answers would only let a question whose provider failed less often speak
    louder.
    """
    totals: dict[str, list[float]] = {}
    for breakdown in breakdowns:
        for temperature, share in breakdown.items():
            totals.setdefault(str(temperature), []).append(float(share))
    return {
        temperature: round(sum(shares) / len(shares), 4)
        for temperature, shares in sorted(totals.items(), key=lambda kv: float(kv[0]))
    }


def abstention_discrimination(
    on_answerable: Metrics | None, on_control: Metrics | None
) -> float | None:
    """Whether the answerer can tell "there is an answer" from "there is none".

    The share of abstentions on the control half minus the share of abstentions on
    the answerable one — Youden statistic, in which abstention is treated as a
    detector of the absence of an answer.

    Someone who always abstains gets zero, someone who always answers also gets
    zero: the maximum belongs only to the one that tells them apart. A difference
    rather than the product from the original — it reads in percentage points and
    composes with confidence intervals.

    Computed PER ARM: in arm A a significant plus would mean the model somehow
    senses the availability of an answer, that is, the corpus is familiar to it.
    The main quantity is for arm C.
    """
    if on_answerable is None or on_control is None:
        return None
    if not on_answerable.graded or not on_control.graded:
        return None
    return round(on_control.abstain_rate - on_answerable.abstain_rate, 4)


def context_effect(
    closed_book: Metrics | None, with_context: Metrics | None
) -> float | None:
    """What the context that appeared did to the answerer.

    The difference in the share of inventions between arms C and A on one and the
    same half of the set. The sign is not known in advance, and that is the point
    of the measurement:

      * **minus** — the context helped it abstain: saying "this is not in the
        documents provided" is easier than "I do not know";
      * **plus** — the context removed the caution: the question started looking
        as if the answer were somewhere here, and the model that stayed silent in
        arm A answered.

    On the control half this is the most important number in the whole
    measurement: it is the price the model honesty pays for being wired to RAG.
    """
    if closed_book is None or with_context is None:
        return None
    if not closed_book.graded or not with_context.graded:
        return None
    return round(with_context.hallucination_rate - closed_book.hallucination_rate, 4)


def _key(m: Metrics) -> tuple[str, str, str, str, str]:
    """What makes two rows count as one and the same test.

    The model and the judge are included of necessity: comparing the abstention
    share of one model with that of another means measuring the difference between
    models rather than discrimination; comparing the verdicts of different judges,
    the difference between judges.
    """
    return (m.space, m.context_mode.value, m.block.value, m.model, m.judge)


def discrimination_pairs(
    results: list[Metrics],
) -> list[tuple[Metrics, Metrics, float]]:
    """The (answerable half, control half) pairs of one and the same test.

    Compared only with the ``abstain`` half. A question with a false premise does
    not go into this count, and that is not nitpicking: the correct behaviour there
    is to refute the premise, not to stay silent. Counting an abstention on it as a
    merit would mean rewarding silence where the answer existed and was known.

    Placed here rather than hidden in the labelling, because the chart in the docx
    is drawn over these same pairs: two reports on one run must not diverge over
    what was compared with what.
    """
    answerable = [m for m in results if m.expected is ExpectedBehavior.ANSWER]
    control = [m for m in results if m.expected is not ExpectedBehavior.ANSWER]
    should_abstain = {
        _key(c): c for c in control if c.expected is ExpectedBehavior.ABSTAIN
    }
    return [
        (a, should_abstain[_key(a)], value)
        for a in answerable
        if _key(a) in should_abstain
        and (value := abstention_discrimination(a, should_abstain[_key(a)])) is not None
    ]


def context_effect_pairs(
    results: list[Metrics],
) -> list[tuple[Metrics, Metrics, float]]:
    """The (arm A, arm C) pairs of one model under one judge on one half.

    The half of the set is in the key of necessity: without it the "no answer" and
    "false premise" rows would collapse into one, and the comparison would
    silently take whichever landed last.
    """
    closed = {
        (m.space, m.block.value, m.model, m.judge, m.expected): m
        for m in results
        if m.context_mode is ContextMode.CLOSED_BOOK
    }
    pairs: list[tuple[Metrics, Metrics, float]] = []
    for m in results:
        if m.context_mode is not ContextMode.MODEL_WITH_CONTEXT:
            continue
        paired = closed.get((m.space, m.block.value, m.model, m.judge, m.expected))
        value = context_effect(paired, m)
        if paired is None or value is None:
            continue
        pairs.append((paired, m, value))
    return pairs
