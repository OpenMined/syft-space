"""Cohorts: pools of questions, each built in one pass over the material.

Rebuilding the set from the same material as a new cohort shows whether
diverging metrics come from the questions rather than the models. Hence:

* duplicates are forbidden within a cohort only — a question repeated across
  cohorts means a stable generator, and forbidding it would block rebuilds;
* processed marks belong to the cohort, so a rebuild parses everything afresh
  while the earlier cohort keeps its marks;
* an earlier cohort is taken out of the measurement, never deleted: its
  verdicts are the other half of the comparison.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import func, select

from syft_benchmark.config import PairStatus, Settings, get_settings
from syft_benchmark.db import QaPair, session_scope

# The cohort label: the build's date and time, to the minute. It reads by eye
# and sorts as a string, with no stored counter.
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
    """The cohort new items go into: the latest label (labels sort as strings).

    Empty for an empty set or one built before cohorts; both are topped up
    without a rebuild.
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

    Rejected items are counted separately: the screening rate is the first
    thing to look at when cohorts diverge.
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
