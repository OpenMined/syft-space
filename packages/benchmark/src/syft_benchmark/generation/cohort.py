"""A cohort of the set: the same material, a different pool of questions.

The benchmark measures a model with questions it composed itself. Hence the
question everyone who looks at its numbers asks sooner or later: **are the
questions themselves any good?** A gold answer can be inaccurate, a wording
ambiguous, and the generator is of the same breed as the models under test and
errs in similar ways.

This question cannot be answered directly: to check questions you need other
questions. But it can be answered indirectly, and the answer comes out
convincing. We take **the same material** and build a set over it afresh — with
a different model, a different prompt, simply a different pass. The material is
the same, the corpus is the same, the endpoint is the same, the models under
test are the same. If the metrics matched, the questions are beside the point,
and the figure speaks about the model. If they diverged, it speaks about the
questions, and it is the generator that has to be looked into.

That is what a cohort is: one pool of questions built in a single pass, with a
label and a date. Three things hold its design together.

**Duplicates are forbidden within a cohort, not in general.** A question
repeating between cohorts is legitimate and meaningful: it means the generator
produced the same question from the same material — that is, it is stable. Had
we forbidden such a repeat, rebuilds would be impossible: the second pass would
be rejected wholesale by the unique index.

**The processed mark belongs to the cohort too.** A rebuild is a fresh pass over
the same material, and the previous build mark must not stop it. Clearing
``processed_units`` is not needed for that: the new cohort simply has no marks,
while the previous one keeps its own — and so it is reproducible.

**The previous cohort is not deleted but taken out of the measurement.** Its
items carry the verdicts of every run that went over it — the very thing we
want to compare the new one against. Deleting it would mean destroying the
second half of the comparison.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import func, select

from syft_benchmark.config import PairStatus, Settings, get_settings
from syft_benchmark.db import QaPair, session_scope

# The cohort label: the date and time of the build. It reads by eye, sorts as a
# string and needs no counter that would have to be stored somewhere. The
# minutes in the label are needed: two builds in a day is an ordinary thing
# while tuning the generator prompts.
_LABEL = "%Y%m%d-%H%M"


@dataclass(frozen=True, slots=True)
class Cohort:
    """One pool of questions: what built it, when, how much is in the measurement."""

    label: str
    space: str
    pairs: int
    active: int
    rejected: int
    built_by: tuple[str, ...]
    first_seen: datetime | None
    last_seen: datetime | None

    @property
    def name(self) -> str:
        """A name for a human. An empty label — a set from before cohorts."""
        return self.label or "(before cohorts)"

    @property
    def models(self) -> str:
        return ", ".join(self.built_by) or "—"


def new_label(*, now: datetime | None = None) -> str:
    """A label for a new cohort."""
    return (now or datetime.now(UTC)).strftime(_LABEL)


def current(space: str, settings: Settings | None = None) -> str:
    """The cohort new items go into.

    It is the latest of the existing ones: the label sorts as a string because
    that is how it is built — a date and a time. An empty string means either an
    empty set or a set built before cohorts existed; both are topped up as
    before, without any rebuild.
    """
    conf = settings or get_settings()
    with session_scope(conf) as session:
        label = session.execute(
            select(func.max(QaPair.cohort)).where(QaPair.space == space)
        ).scalar()
    return str(label or "")


@dataclass(slots=True)
class _Tally:
    """A running tally for one cohort while the selection is processed."""

    pairs: int = 0
    active: int = 0
    rejected: int = 0
    models: set[str] = field(default_factory=set)
    first: datetime | None = None
    last: datetime | None = None

    def saw(self, at: datetime | None) -> None:
        if at is None:
            return
        if self.first is None or at < self.first:
            self.first = at
        if self.last is None or at > self.last:
            self.last = at


def listing(space: str, settings: Settings | None = None) -> list[Cohort]:
    """All the cohorts of the set, newest first.

    Screened-out items are counted separately: the screening rate is the first
    thing to look at when cohorts diverge. A generator that had a third of its
    gold answers rejected probably did not build the other two thirds any better.
    """
    conf = settings or get_settings()
    with session_scope(conf) as session:
        rows = session.execute(
            select(
                QaPair.cohort,
                QaPair.status,
                QaPair.model,
                func.count().label("n"),
                func.min(QaPair.created_at).label("first"),
                func.max(QaPair.created_at).label("last"),
            )
            .where(QaPair.space == space)
            .group_by(QaPair.cohort, QaPair.status, QaPair.model)
        ).all()

    collected: dict[str, _Tally] = {}
    for row in rows:
        tally = collected.setdefault(str(row.cohort or ""), _Tally())
        count = int(row.n)
        tally.pairs += count
        if row.status == PairStatus.ACTIVE.value:
            tally.active += count
        elif row.status == PairStatus.REJECTED.value:
            tally.rejected += count
        if row.model:
            tally.models.add(str(row.model))
        tally.saw(row.first)
        tally.saw(row.last)

    cohorts = [
        Cohort(
            label=label,
            space=space,
            pairs=tally.pairs,
            active=tally.active,
            rejected=tally.rejected,
            built_by=tuple(sorted(tally.models)),
            first_seen=tally.first,
            last_seen=tally.last,
        )
        for label, tally in collected.items()
    ]
    cohorts.sort(key=lambda c: c.label, reverse=True)
    return cohorts
