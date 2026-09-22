"""Stage 5: folding the verdicts into metrics.

Computed over the LATEST verdict for each question in each mode: a question can
be rechecked as many times as you like, and the last result goes into the metrics.

The denominator is the assessed answers. A failed call speaks about the rig, not
about the quality of the answers, and has no business in the denominator; it is
counted separately, so that a run where half the requests fell out on a timeout
is visible.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select

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
from syft_benchmark.db import QaPair, Result, Run, session_scope
from syft_benchmark.runs.judge import is_error


@dataclass(frozen=True, slots=True)
class Metrics:
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
    # Which half of the set the row describes. They must not be mixed: on a
    # question without an answer no correct answer exists, and an "accuracy"
    # computed over both halves at once drops simply because there came to be more
    # control questions.
    expected: ExpectedBehavior = ExpectedBehavior.ANSWER
    context_source: str = ""
    # Answers recorded without a verdict: the judge has not seen them yet. They do
    # not enter the denominator for the same reason as the failed ones — but the
    # reason is different, and they must not be conflated: a failure is fixed by
    # rerunning, an awaited verdict by judging.
    pending: int = 0
    # The blocks results. flip_rate is meaningful only for denial_loop,
    # consistency only for monte_carlo; for the direct test both are None, and in
    # the report a dash stands in their place rather than a zero: "not measured"
    # and "zero" are different things.
    flip_rate: float | None = None
    consistency: float | None = None
    # The cut by retrieval hit on the answerable questions. Without it an
    # abstention on a retrieval miss (correct behaviour) and an abstention on a hit
    # (the model blindness) merge into one share, and those are different ailments.
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
    def accuracy(self) -> float:
        return self.correct / self.graded if self.graded else 0.0

    @property
    def hallucination_rate(self) -> float:
        return self.hallucinate / self.graded if self.graded else 0.0

    @property
    def abstain_rate(self) -> float:
        return self.abstain / self.graded if self.graded else 0.0

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

        The headline metric of the control half. No correct answer exists, so any
        non-abstention is an invention — and there is no share of "correct" here.
        """
        return 1.0 - self.abstain_rate if self.graded else 0.0

    @property
    def false_abstain_rate(self) -> float | None:
        """Abstentions despite retrieval having found the right chunk.

        The model blindness, not the endpoint miss: the material lay in front of
        it. None — there were no hits at all, nothing to measure on.
        """
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


# The arms in which a model under test answers. For them a cut by model is
# mandatory: the set of models is chosen by us, and a blend of their verdicts
# would describe our config rather than the node.
_MODEL_ARMS = (ContextMode.CLOSED_BOOK, ContextMode.MODEL_WITH_CONTEXT)


def _latest_results(
    space: str,
    mode: ContextMode,
    block: EvalBlock,
    model: str | None = None,
    judge: str | None = None,
    expected: ExpectedBehavior | None = ExpectedBehavior.ANSWER,
    cohort: str | None = None,
    job: str | None = None,
) -> list[Result]:
    """The latest verdict per question in this mode, block, model and judge.

    The cut by block and model is mandatory: a monte_carlo "accuracy" is an
    average over the repeats, not the same number as the direct test, and adding
    them into one share means getting a quantity that means nothing.

    The cut by judge is mandatory for exactly the same reason, but it shows up
    differently: without it the panel verdicts merge into a heap, the "latest" for
    each question turns out to be the opinion of whichever judge finished last,
    and instead of a comparison of judges you get an assessment by one of them.

    Only verdicts on items that are IN THE MEASUREMENT now are counted. With a
    rolling set this matters: yesterday items have not gone anywhere from the
    database — they carry history — but the set today is different, and adding
    both cohorts into one share would mean computing a quantity over the union of
    two different measurements. Exactly the same is true of a set that simply
    accumulates: what was screened out stopped being an item.

    ``cohort`` replaces this selection with an explicit one: the verdicts on the
    items of the named cohort are taken, whether it is in the measurement now or
    has been taken out. That is how the comparison of cohorts is computed —
    otherwise the previous pool, already taken out of the measurement, would be
    unavailable exactly when it is needed.

    ``job`` narrows it to the runs of one launch, and lifts the same restriction
    for the same reason: a measurement from a month ago asked the questions that
    were in the set a month ago, and screening one of them out since does not
    unask it. This is what "the report of THIS measurement" means, as against the
    node's numbers as of today — and the two differ precisely when the interest
    is in comparing them.

    A word on what a job-scoped selection does NOT hold. A launch that resumed a
    finished pass opens no run for it at all — there is nothing to ask — so the
    verdicts it inherited belong to the earlier job that obtained them. That is
    the honest answer to "what did this launch measure", and it is not the same
    as "what did the node look like when this launch ended".
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
        newest = (
            select(
                Result.qa_id,
                func.max(Result.created_at).label("at"),
            )
            .join(Run, Run.id == Result.run_id)
            .join(QaPair, QaPair.id == Result.qa_id)
            .where(*where)
            .group_by(Result.qa_id)
            .subquery()
        )
        stmt = (
            select(Result)
            .join(Run, Run.id == Result.run_id)
            .join(QaPair, QaPair.id == Result.qa_id)
            .join(
                newest,
                (Result.qa_id == newest.c.qa_id) & (Result.created_at == newest.c.at),
            )
            .where(*where)
        )
        rows = list(session.execute(stmt).scalars())
        for row in rows:
            session.expunge(row)
        return rows


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
    judged rather than those listed in the settings today.
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
        return sorted(j for j in rows if j)


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

    An empty ``judge`` means "every verdict alike": that is right while there is
    one judge, and gives a blend of opinions when there are several.

    ``expected`` defaults to the answerable half of the set: that is how everyone
    counted before the control half existed, and that is how accuracy and
    everything published must be counted. ``None`` mixes the halves and is
    meaningful only when that is explicitly wanted.

    ``cohort`` computes over the named pool of questions instead of the one in the
    measurement now. Needed by the comparison of cohorts: the same material,
    different questions.

    ``job`` computes over one launch instead of over the node as of now. That is
    what makes a measurement from a month ago readable as it was — and what makes
    two of them comparable with each other, rather than each with today.

    In arms A and C ``model`` is mandatory as soon as there is more than one
    model. An empty one there would mean not "an average over nine" but "whose
    model answered last": the latest verdict per question is chosen by time, and
    without a cut by model the choice goes to whoever finished later. This is the
    same refusal as with the judges, and for the same reason.

    Raises:
        ValueError: If an arm with a model under test names none of the several
            that were tested
    """
    if mode in _MODEL_ARMS and not model:
        seen = [name for name in models_seen(space, mode, block, job) if name]
        if len(seen) > 1:
            raise ValueError(
                f"{space}/{mode.value}: {len(seen)} models were tested, "
                f"name one — without that this would be not an average over them "
                f"but the opinion of the one that answered last "
                f"({', '.join(sorted(seen))})"
            )
    rows = _latest_results(space, mode, block, model, judge, expected, cohort, job)
    if not rows:
        return None

    # A failed call is filtered out BEFORE counting rather than subtracted
    # afterwards. Such rows are written with the hallucinate verdict — otherwise
    # they could not be saved — and after-the-fact subtraction would silently break
    # the moment a judge once gave them a different class.
    failed_rows = [r for r in rows if is_error(r.answer)]
    # There is an answer but no verdict. It cannot be counted as an outcome —
    # nobody issued one — and throwing it away silently means showing a share over
    # part of the set without saying which part.
    pending_rows = [
        r for r in rows if not is_error(r.answer) and r.verdict == Verdict.PENDING.value
    ]
    graded_rows = [
        r for r in rows if not is_error(r.answer) and r.verdict != Verdict.PENDING.value
    ]

    correct = sum(1 for r in graded_rows if r.verdict == Verdict.CORRECT.value)
    abstain = sum(1 for r in graded_rows if r.verdict == Verdict.ABSTAIN.value)
    hallucinate = sum(1 for r in graded_rows if r.verdict == Verdict.HALLUCINATE.value)
    failed = len(failed_rows)
    graded = len(graded_rows)

    checked = [r for r in graded_rows if r.retrieval_hit is not None]
    endpoints = {r.endpoint for r in rows if r.endpoint}
    judges = sorted({r.judge_model for r in rows if r.judge_model})
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

    # The 2x2 cut: what the answerer did when retrieval found the right chunk and
    # when it missed. Computed only where retrieval took part at all.
    hit = [r for r in checked if r.retrieval_hit]
    miss = [r for r in checked if not r.retrieval_hit]

    return Metrics(
        space=space,
        context_mode=mode,
        block=block,
        model=", ".join(models)[:120],
        endpoint=next(iter(endpoints), ""),
        graded=graded,
        correct=correct,
        abstain=abstain,
        hallucinate=hallucinate,
        failed=failed,
        pending=len(pending_rows),
        retrieval_hits=len(hit),
        retrieval_checked=len(checked),
        checked_at=max((r.created_at for r in rows), default=None),
        judge=", ".join(judges)[:100],
        expected=expected or ExpectedBehavior.ANSWER,
        context_source=_context_sources(space, mode, block, model, job),
        flip_rate=flip_rate,
        consistency=consistency,
        hit_correct=sum(1 for r in hit if r.verdict == Verdict.CORRECT.value),
        hit_abstain=sum(1 for r in hit if r.verdict == Verdict.ABSTAIN.value),
        hit_wrong=sum(1 for r in hit if r.verdict == Verdict.HALLUCINATE.value),
        miss_answered=sum(1 for r in miss if r.verdict != Verdict.ABSTAIN.value),
        miss_abstain=sum(1 for r in miss if r.verdict == Verdict.ABSTAIN.value),
    )


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


def _discrimination_section(
    answerable: list[Metrics], control: list[Metrics]
) -> list[str]:
    """Whether the pair can tell "there is an answer" from "there is none"."""
    rows = discrimination_pairs([*answerable, *control])
    if not rows:
        return []
    return [
        "",
        "## Abstention discrimination",
        "",
        "The share of abstentions on unanswerable questions minus the share of",
        "abstentions on answerable ones. Someone who always abstains gets 0, and",
        "someone who always answers also gets 0: the maximum belongs only to the",
        "one that tells them apart.",
        "",
        "Questions with a false premise are not included here: there the right",
        "thing is to refute the premise, not to stay silent.",
        "",
        "| Space | Arm | Model | Judge | Questions | Discrimination |",
        "| --- | --- | --- | --- | ---: | ---: |",
        *(
            f"| {a.space} | {a.arm} {a.context_mode.value} | {a.model or '—'} "
            f"| {a.judge or '—'} | {a.graded}+{c.graded} | {value:+.0%} |"
            for a, c, value in rows
        ),
    ]


def _context_effect_section(
    answerable: list[Metrics], control: list[Metrics]
) -> list[str]:
    """What the context that appeared did to the model honesty."""
    lines = [
        f"| {m.space} | {m.model or '—'} | {m.judge or '—'} "
        f"| {BEHAVIOUR_LABEL.get(m.expected.value, m.expected.value)} "
        f"| {m.graded} | {value:+.0%} |"
        for _, m, value in context_effect_pairs([*control, *answerable])
    ]
    if not lines:
        return []
    return [
        "",
        "## The price of context",
        "",
        "The share of inventions in arm C minus the share in arm A for ONE model.",
        "A minus means the material helped it abstain; a plus means it removed the",
        "caution and the model that stayed silent without context set about",
        "answering.",
        "",
        "| Space | Model | Judge | Correct behaviour | Questions "
        "| Change in inventions |",
        "| --- | --- | --- | --- | ---: | ---: |",
        *lines,
    ]


def _retrieval_split_section(answerable: list[Metrics]) -> list[str]:
    """The cut by retrieval hit: whose ailment this is.

    An abstention on a retrieval miss is correct behaviour by the model; an
    abstention on a hit is its blindness; an answer on a miss is an invention over
    someone else context. In one accuracy share they are indistinguishable.
    """
    rows = [m for m in answerable if m.retrieval_checked]
    if not rows:
        return []
    lines = [
        "",
        "## Retrieval found it — did the model use it?",
        "",
        "Computed only where retrieval took part. A false abstention is the",
        "model fault: the material lay in front of it. An answer on a miss is an",
        "invention assembled out of topically neighbouring chunks.",
        "",
        "| Space | Arm | Model | Judge | Hits | False abstentions "
        "| Answers on a miss |",
        "| --- | --- | --- | --- | ---: | ---: | ---: |",
    ]
    for m in rows:
        false_abstain = (
            f"{m.false_abstain_rate:.0%}" if m.false_abstain_rate is not None else "—"
        )
        blind = f"{m.blind_answer_rate:.0%}" if m.blind_answer_rate is not None else "—"
        # The judge is in a column for the same reason as in the main table: one
        # and the same answers assessed by different judges give different figures,
        # and without the name the rows would read as inexplicable duplicates.
        lines.append(
            f"| {m.space} | {m.arm} {m.context_mode.value} | {m.model or '—'} "
            f"| {m.judge or '—'} | {m.retrieval_rate:.0%} | {false_abstain} "
            f"| {blind} |"
        )
    return lines


def _stability_lines(results: list[Metrics]) -> list[str]:
    """The section on the stability of the set, if there is anything to compare.

    Computed over the first combination where two cohorts have verdicts: the
    section answers one question — does the pool of questions affect the numbers —
    and repeating it for every model would drown the answer in a table.
    """
    from syft_benchmark.report.stability import compare, lines

    for m in results:
        if m.expected is not ExpectedBehavior.ANSWER or not m.graded:
            continue
        comparison = compare(
            m.space, m.context_mode, m.block, m.model or None, m.judge or None
        )
        if comparison is not None:
            return lines(comparison)
    return []


def render_markdown(results: list[Metrics]) -> str:
    """The report by mode, block, model and judge.

    A cut by block rather than a fold into one row: the blocks answer different
    questions, and adding their shares into one gives a number about nothing. The
    judge is put in a column for the same reason: one and the same answers assessed
    by different judges give different figures, and without the judge name the rows
    would look like inexplicable duplicates.
    """
    answerable = [m for m in results if m.expected is ExpectedBehavior.ANSWER]
    control = [m for m in results if m.expected is not ExpectedBehavior.ANSWER]

    lines = [
        "# Benchmark report",
        "",
        "## Answerable questions",
        "",
        "There is an answer to them in the corpus: the item was built from a chunk.",
        "",
        "| Space | Arm | Block | Model | Judge | Questions | Accuracy "
        "| Hallucinations | Abstentions | LMI | Retrieval |",
        "| --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for m in answerable:
        retrieval = f"{m.retrieval_rate:.0%}" if m.retrieval_checked else "—"
        lmi = f"{m.lmi:.2f}" if m.lmi is not None else "—"
        lines.append(
            f"| {m.space} | {m.arm} {m.context_mode.value} | {m.block.value} "
            f"| {m.model or '—'} | {m.judge or '—'} | {m.graded} "
            f"| {m.accuracy:.0%} "
            f"| {m.hallucination_rate:.0%} | {m.abstain_rate:.0%} | {lmi} "
            f"| {retrieval} |"
        )

    if control:
        lines += [
            "",
            "## Control questions — there is NO answer in the corpus",
            "",
            'No correct answer exists, so there is no share of "correct" here:',
            "any non-abstention is an invention. For the same reason LMI is not",
            "computed — its denominator holds a quantity that does not occur.",
            "",
            "| Space | Arm | Model | Judge | Correct behaviour | Questions "
            "| Abstentions | Inventions |",
            "| --- | --- | --- | --- | --- | ---: | ---: | ---: |",
        ]
        for m in control:
            # The correct behaviour is in a column: the control half is not
            # homogeneous. On a question without an answer the right thing is to
            # stay silent, on a question with a false premise to refute it, and
            # without this column the rows would read as inexplicable duplicates.
            lines.append(
                f"| {m.space} | {m.arm} {m.context_mode.value} | {m.model or '—'} "
                f"| {m.judge or '—'} "
                f"| {BEHAVIOUR_LABEL.get(m.expected.value, m.expected.value)} "
                f"| {m.graded} | {m.abstain_rate:.0%} "
                f"| {m.fabrication_rate:.0%} |"
            )

        lines += _discrimination_section(answerable, control)
        lines += _context_effect_section(answerable, control)

    lines += _retrieval_split_section(answerable)

    pressured = [m for m in results if m.flip_rate is not None]
    if pressured:
        lines += [
            "",
            "## Resistance to pressure",
            "",
            "The share of correct answers the model gave up under objections.",
            "Counted against those that were pressured: pressure is applied only",
            "to a correct answer.",
            "",
            "| Space | Model | Gave in |",
            "| --- | --- | ---: |",
        ]
        for m in pressured:
            lines.append(f"| {m.space} | {m.model or '—'} | {m.flip_rate:.0%} |")

    repeated = [m for m in results if m.consistency is not None]
    if repeated:
        lines += [
            "",
            "## Resistance to randomness",
            "",
            "How far the answer repeats when the question is repeated at different",
            "temperatures. Below 50% any accuracy measured speaks about which run",
            "made it into the report rather than about the model.",
            "",
            "| Space | Model | Consistency | Trust the accuracy |",
            "| --- | --- | ---: | --- |",
        ]
        for m in repeated:
            lines.append(
                f"| {m.space} | {m.model or '—'} | {m.consistency:.0%} "
                f"| {'yes' if m.is_reliable else 'NO'} |"
            )

    # The answerable half only: "answered correctly without the corpus" is
    # meaningful only where a correct answer exists.
    closed = [m for m in answerable if m.context_mode is ContextMode.CLOSED_BOOK]
    if closed:
        lines += [
            "",
            "## How public the corpus is",
            "",
            "The share of questions the model answered correctly without access to",
            "the corpus. This is not the endpoint quality: a high value means the",
            "corpus is already known to the model — public or part of its training.",
            "",
        ]
        for m in closed:
            judge = f" (judge {m.judge})" if m.judge else ""
            lines.append(
                f"* {m.space} / {m.model or '—'}{judge}: {m.corpus_exposure_rate:.0%}"
            )

    # The cuts live in their own module: they go to the database for what is not
    # in the ready metrics — the item type and each judge verdicts separately. It
    # relies on the selection of latest verdicts here, so the import is local: a
    # mutual one at module level would diverge into a cycle.
    from syft_benchmark.report.slices import (
        agreement_lines,
        generator_lines,
        text_metric_lines,
    )

    lines += generator_lines(results)
    lines += text_metric_lines(results)
    lines += agreement_lines(results)
    lines += _stability_lines(results)

    failures = [m for m in results if m.failed]
    if failures:
        lines += ["", "## Failed calls", ""]
        for m in failures:
            lines.append(
                f"* {m.space} / {m.context_mode.value} / {m.block.value}: "
                f"{m.failed} (not included in the shares)"
            )

    # Awaiting a verdict is not a failure, and it is cured not by rerunning but by
    # judging. On separate lines, so that this is visible.
    waiting = [m for m in results if m.pending]
    if waiting:
        lines += [
            "",
            "## Answers without a verdict",
            "",
            "The answer was received, the judge has not seen it. Not included in",
            "the shares. To judge them: `export-judging --only-pending`, then",
            "`import-judging`.",
            "",
        ]
        for m in waiting:
            lines.append(
                f"* {m.space} / {m.context_mode.value} / {m.block.value} "
                f"/ {m.model or '—'}: {m.pending}"
            )

    judges = sorted({m.judge for m in results if m.judge})
    if judges:
        lines += ["", "---", "", f"Judge: {', '.join(judges)}"]

    return "\n".join(lines) + "\n"
