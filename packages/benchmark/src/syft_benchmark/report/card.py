"""The endpoint card: everything the node shows the world.

A report answers the question "what did we get" and is written for the owner. A
card answers a different one — "what will an outsider see" — and so is built not
as a slice of the database but as an answer to three questions from three
different readers:

* the **badge** — is it worth opening at all. Two numbers and a state;
* the **storefront page** — what do I get if I connect my own model;
* the **Space own page** — does the owner vouch for these numbers.

The first two are assembled here and leave the perimeter. The third stays with
the owner and takes its data from the database directly: invariant 3 limits what
leaves the perimeter, and the owner is not limited in their own data at all.

**The kind of product decides which numbers are meaningful at all.** An endpoint
in ``raw`` mode does not formulate an answer — it searches; arm B is not run
against it at all, and there is nothing to measure its "accuracy" from. Its
product is the retrieval hit, and its responsibility is whether the material it
returns nudges someone else model into invention. An endpoint in ``summary`` or
``both`` mode answers itself, and is judged by its answer. Two different products,
two different headline numbers — which is why the kind is mandatory in the
payload: without it the reader will take "finds 82%" for "correct 82%".

**Nine models are not folded into an average.** An average over nine would change
because we added a tenth to our config, even though nothing happened to the
endpoint. So arm C goes out as a spread, named one by one: it is for the reader
to decide what to connect, and the spread answers them directly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from syft_benchmark.config import (
    ContextMode,
    EvalBlock,
    ExpectedBehavior,
    Settings,
    get_settings,
)
from syft_benchmark.report.metrics import (
    Metrics,
    abstention_discrimination,
    context_effect,
    judges_seen,
    models_seen,
    summarize,
)
from syft_benchmark.report.slices import (
    AGREEMENT_FLOOR,
    average_agreement,
    by_generator,
    judge_agreement,
)

# The card format version. The receiving side is obliged to know what it is
# reading: in the first version six flat numbers left the perimeter, of which the
# headline one was computed over one half of the set and did not say whose it was.
#
# Kept in lockstep with CARD_VERSION in
# packages/spaces/backend/syft_space/components/endpoints/schemas.py by hand:
# the two packages must not import each other, so nothing enforces this beyond
# whoever bumps one remembering the other.
CARD_VERSION = 2

# The kind of product. Neither decoration nor a hint to the storefront: which
# number is the headline one, and what this card can be compared with at all,
# depend on it.
ANSWERING = "answering"
RETRIEVAL = "retrieval"

# Below this number of questions a share is not a measurement but an anecdote: on
# twenty questions one verdict moves it by five points, that is, by more than the
# whole difference between a decent node and a mediocre one.
MIN_SAMPLES = 30

# How far an item type may lag behind the best before the sample is considered
# skewed. The same value as in `runs.status`, and for the same reason.
COVERAGE_LAG = 0.25


@dataclass(frozen=True, slots=True)
class ModelRow:
    """What one model under test achieved on this node material."""

    model: str
    samples: int
    accuracy: float
    fabrication: float | None
    lmi: float | None
    context_gain: float | None


@dataclass(frozen=True, slots=True)
class SkillRow:
    """How well the node copes with one item type."""

    generator: str
    samples: int
    accuracy: float


@dataclass(frozen=True, slots=True)
class Trust:
    """What to prop the number up with — and whether to show it at all.

    A share nobody vouches for is worse than no share: the reader sees an absence,
    but believes an unfounded number.
    """

    samples: int
    judges: int
    agreement: float | None
    consistency: float | None
    even_coverage: bool
    failed: int
    pending: int

    @property
    def reliable(self) -> bool:
        """Whether this number can be put on the storefront.

        Four reasons to say "no", and each is its own: too few questions; the
        judges diverge so far that the difference between nodes drowns in the
        spread of assessments; not all the skills were tested; some answers have
        no verdict.
        """
        if self.samples < MIN_SAMPLES:
            return False
        if self.agreement is not None and self.agreement < AGREEMENT_FLOOR:
            return False
        if not self.even_coverage:
            return False
        return self.pending == 0

    @property
    def flags(self) -> list[str]:
        """Why the number cannot be trusted — as codes, not as prose.

        Codes leave the perimeter: the wording is written by whoever displays it —
        they have their own language and their own reader. The benchmark prose on
        a foreign storefront would be both text crossing the perimeter without
        need and a foreign localisation.
        """
        codes: list[str] = []
        if self.samples < MIN_SAMPLES:
            codes.append("few_samples")
        if self.agreement is not None and self.agreement < AGREEMENT_FLOOR:
            codes.append("judges_disagree")
        if not self.even_coverage:
            codes.append("uneven_coverage")
        if self.pending:
            codes.append("pending_verdicts")
        if self.failed:
            codes.append("failed_calls")
        return codes

    @property
    def doubts(self) -> list[str]:
        """The same thing in words — for our own console, not for the storefront."""
        notes: list[str] = []
        if self.samples < MIN_SAMPLES:
            notes.append(
                f"too few questions: {self.samples} against a floor of {MIN_SAMPLES}"
            )
        if self.agreement is not None and self.agreement < AGREEMENT_FLOOR:
            notes.append(
                f"the judges diverge: agreement {self.agreement:.0%} "
                f"is below the floor of {AGREEMENT_FLOOR:.0%}"
            )
        if not self.even_coverage:
            notes.append("coverage by item type is uneven — the sample is skewed")
        if self.pending:
            notes.append(f"{self.pending} answers were left without a verdict")
        if self.failed:
            notes.append(f"failed calls: {self.failed}")
        return notes


@dataclass(frozen=True, slots=True)
class DatasetInfo:
    """Which set it was computed over.

    "71% for yesterday" and "71% for the whole corpus" are different things.
    """

    mode: str
    window_days: int
    cohort: str
    questions: int


@dataclass(frozen=True, slots=True)
class Instrument:
    """What it was measured with.

    Within one benchmark installation several Spaces are measured by one and the
    same thing: the same judge, the same panel, the same models under test, the
    same thresholds. Between different installations nothing is guaranteed, and
    the storefront cannot tell them apart — unless it is told.
    """

    version: int
    profile: str
    judge: str
    judges: int
    subjects: int


@dataclass(frozen=True, slots=True)
class Card:
    """The card of one endpoint: the badge and the public page."""

    space: str
    endpoint: str
    kind: str
    arm: str
    checked_at: datetime | None

    # --- The headline numbers. Their meaning is set by the kind, and separately
    # they do not read.
    score: float | None
    fabrication: float | None

    # --- The cuts of the public page.
    answerable: Metrics | None = None
    control: Metrics | None = None
    discrimination: float | None = None
    retrieval: float | None = None
    models: list[ModelRow] = field(default_factory=list)
    skills: list[SkillRow] = field(default_factory=list)

    trust: Trust | None = None
    dataset: DatasetInfo | None = None
    instrument: Instrument | None = None

    @property
    def reliable(self) -> bool:
        return self.trust.reliable if self.trust else False

    @property
    def score_label(self) -> str:
        """What the headline number is called for this kind of product."""
        return "finds" if self.kind == RETRIEVAL else "correct"

    @property
    def spread(self) -> tuple[float, float] | None:
        """The spread of accuracy across the models under test — worst to best."""
        if len(self.models) < 2:
            return None
        shares = [row.accuracy for row in self.models]
        return min(shares), max(shares)


def endpoint_kind(space: str, settings: Settings | None = None) -> str:
    """The kind of product by what is recorded in the runs, not by the card now.

    The owner can switch the endpoint mode, while the verdicts relate to the
    previous one. Asking the live card would mean describing today node with
    yesterday numbers.
    """
    from sqlalchemy import select

    from syft_benchmark.db import session_scope
    from syft_benchmark.db.models import Result

    conf = settings or get_settings()
    with session_scope(conf) as session:
        seen = {
            str(row or "")
            for row in session.execute(
                select(Result.endpoint_response_type)
                .where(Result.space == space)
                .distinct()
            ).scalars()
        }
    # `both` can do both, but is sold as an answering one: the answer is what the
    # user gets without supplying a model of their own.
    if seen & {"summary", "both"}:
        return ANSWERING
    if "raw" in seen:
        return RETRIEVAL
    return ANSWERING


def _even_coverage(space: str, mode: ContextMode, model: str | None) -> bool:
    """Whether all the item types were tested comparably.

    An interrupted run leaves coverage uneven, and a share computed over such a
    state looks like an ordinary share. The lag is measured against the best:
    while the run is in progress everything lags at once, and that is normal.
    """
    slices = by_generator(space, mode, EvalBlock.DIRECT, model=model)
    counts = [row.graded for row in slices if row.graded]
    if len(counts) < 2:
        return True
    best = max(counts)
    return all(best - count <= best * COVERAGE_LAG for count in counts)


def _model_rows(space: str, settings: Settings) -> list[ModelRow]:
    """Arm C named one by one: what each model under test achieved.

    Named and separate — because an average over them would measure our config
    rather than the node, and would change when a tenth model was added.
    """
    rows: list[ModelRow] = []
    for name in models_seen(space, ContextMode.MODEL_WITH_CONTEXT, EvalBlock.DIRECT):
        if not name:
            continue
        answerable = summarize(space, ContextMode.MODEL_WITH_CONTEXT, model=name)
        if answerable is None or not answerable.graded:
            continue
        control = summarize(
            space,
            ContextMode.MODEL_WITH_CONTEXT,
            model=name,
            expected=ExpectedBehavior.ABSTAIN,
        )
        closed = summarize(space, ContextMode.CLOSED_BOOK, model=name)
        rows.append(
            ModelRow(
                model=name,
                samples=answerable.graded,
                accuracy=round(answerable.accuracy, 4),
                fabrication=(
                    round(control.fabrication_rate, 4)
                    if control and control.graded
                    else None
                ),
                lmi=round(answerable.lmi, 4) if answerable.lmi is not None else None,
                context_gain=context_effect(closed, answerable),
            )
        )
    rows.sort(key=lambda row: (-row.accuracy, row.model))
    return rows


def _skill_rows(space: str, mode: ContextMode, model: str | None) -> list[SkillRow]:
    """The cut by item type: what this node is good for.

    Computed over the answerable half — on the control half there is nothing to
    compute "accuracy by item type" from.
    """
    rows = [
        SkillRow(
            generator=row.generator,
            samples=row.graded,
            accuracy=round(row.correct / row.graded, 4),
        )
        for row in by_generator(space, mode, EvalBlock.DIRECT, model=model)
        if row.graded
    ]
    rows.sort(key=lambda row: (-row.accuracy, row.generator))
    return rows


def _trust(
    space: str,
    mode: ContextMode,
    model: str | None,
    answerable: Metrics | None,
    control: Metrics | None,
) -> Trust:
    """Assemble the grounds for trusting — and not trusting — these numbers."""
    pairs = judge_agreement(space, mode, EvalBlock.DIRECT, model=model)
    graded = (answerable.graded if answerable else 0) + (
        control.graded if control else 0
    )
    failed = (answerable.failed if answerable else 0) + (
        control.failed if control else 0
    )
    pending = (answerable.pending if answerable else 0) + (
        control.pending if control else 0
    )
    return Trust(
        samples=graded,
        judges=len([j for j in judges_seen(space, mode, EvalBlock.DIRECT) if j]),
        agreement=average_agreement(pairs),
        consistency=answerable.consistency if answerable else None,
        even_coverage=_even_coverage(space, mode, model),
        failed=failed,
        pending=pending,
    )


def build(
    space: str,
    endpoint: str = "",
    *,
    settings: Settings | None = None,
) -> Card | None:
    """Assemble the node card: the badge and the public page.

    The arm is chosen by the kind of product rather than by a setting: a ``raw``
    endpoint has no arm B at all — it refuses to run, because there is nothing to
    assess there — and a global publishing setting would leave such a node without
    a single number despite excellent retrieval.

    Args:
        space: The Space key
        endpoint: The endpoint slug — for the payload, it does not affect the count
        settings: The settings; the current ones by default

    Returns:
        The card, or ``None`` if there is nothing to publish
    """
    conf = settings or get_settings()
    kind = endpoint_kind(space, conf)
    mode = (
        ContextMode.MODEL_WITH_CONTEXT if kind == RETRIEVAL else ContextMode.OPEN_BOOK
    )

    # An answering node has no model under test in arm B — it answers itself, and
    # a cut by model is not needed. For a retrieval node the headline numbers are
    # taken from arm C, and there are nine models there, which must not be mixed:
    # the latest verdict per question would turn out to be "whose model finished
    # last".
    model = _spokesmodel(space, kind)
    if kind == RETRIEVAL and model is None:
        return None

    answerable = summarize(space, mode, model=model)
    control = summarize(space, mode, model=model, expected=ExpectedBehavior.ABSTAIN)
    if answerable is None and control is None:
        return None

    retrieval = (
        round(answerable.retrieval_rate, 4)
        if answerable and answerable.retrieval_checked
        else None
    )
    if kind == RETRIEVAL:
        score = retrieval
    else:
        score = round(answerable.accuracy, 4) if answerable else None

    newest = answerable or control
    return Card(
        space=space,
        endpoint=endpoint,
        kind=kind,
        arm=mode.value,
        checked_at=newest.checked_at if newest else None,
        score=score,
        fabrication=(
            round(control.fabrication_rate, 4) if control and control.graded else None
        ),
        answerable=answerable,
        control=control,
        discrimination=abstention_discrimination(answerable, control),
        retrieval=retrieval,
        models=_model_rows(space, conf),
        skills=_skill_rows(space, mode, model),
        trust=_trust(space, mode, model, answerable, control),
        dataset=_dataset(space, conf),
        instrument=_instrument(space, mode, conf),
    )


def _spokesmodel(space: str, kind: str) -> str | None:
    """Whose answers a retrieval node card speaks with.

    A retrieval node has no answer of its own, and the headline numbers have to be
    taken from arm C — and there are nine models there. The best is taken: the card
    answers the question "what is this node capable of", not "how does it look with
    a random model". The spread across all nine is shown alongside and does not
    depend on this choice.
    """
    if kind != RETRIEVAL:
        return None
    best: tuple[float, str] | None = None
    for name in models_seen(space, ContextMode.MODEL_WITH_CONTEXT, EvalBlock.DIRECT):
        if not name:
            continue
        got = summarize(space, ContextMode.MODEL_WITH_CONTEXT, model=name)
        if got is None or not got.graded:
            continue
        if best is None or got.accuracy > best[0]:
            best = (got.accuracy, name)
    return best[1] if best else None


def _dataset(space: str, settings: Settings) -> DatasetInfo:
    """Which set it was computed over."""
    from sqlalchemy import func, select

    from syft_benchmark.config import PairStatus
    from syft_benchmark.db import session_scope
    from syft_benchmark.db.models import QaPair

    with session_scope(settings) as session:
        questions = int(
            session.execute(
                select(func.count(QaPair.id)).where(
                    QaPair.space == space,
                    QaPair.status == PairStatus.ACTIVE.value,
                )
            ).scalar_one()
        )
        cohort = str(
            session.execute(
                select(func.max(QaPair.cohort)).where(QaPair.space == space)
            ).scalar()
            or ""
        )
    return DatasetInfo(
        mode=settings.dataset_mode.value,
        window_days=settings.document_window_days,
        cohort=cohort,
        questions=questions,
    )


def _instrument(space: str, mode: ContextMode, settings: Settings) -> Instrument:
    """What it was measured with — so the storefront compares only the comparable."""
    panel = [j for j in judges_seen(space, mode, EvalBlock.DIRECT) if j]
    return Instrument(
        version=CARD_VERSION,
        profile=settings.methodology_profile,
        judge=panel[0] if panel else settings.judge_model,
        judges=len(panel),
        subjects=len(
            [
                m
                for m in models_seen(
                    space, ContextMode.MODEL_WITH_CONTEXT, EvalBlock.DIRECT
                )
                if m
            ]
        ),
    )
