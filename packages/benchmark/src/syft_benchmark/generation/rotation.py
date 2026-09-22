"""The rolling set: what is in the measurement now and what has left it.

The corpus grows, the measurement does not. Three arms across nine models multiply
by every item, and sooner or later you have to choose not "how much we can manage"
but "what exactly we are measuring". That choice is substantive rather than
technical: last year document answers a question nobody asks any more.

Hence two set modes, and the difference between them is in their attitude to time.
The incremental one accumulates: that is how a stable corpus is measured, where a
correct answer does not go out of date. The rolling one moves with time: in the
measurement is what grew out of documents from the last N days.

**What leaves the set is not deleted.** This is the main decision of the module,
and it is the only possible one: an item carries the verdicts of every previous
run, and the foreign key is set with a cascade. Deleting a question means carrying
off the history of measurements with it, that is, precisely what the benchmark is
kept for. So what leaves is moved to ``retired``: out of the measurement, not out
of the database.

**What returns comes back.** A one-week window, shifting by a day, keeps six
sevenths of yesterday documents inside it. Building items over them again would
mean paying the generator for what has already been bought and getting duplicates
that the unique index would reject anyway. So recomputing the set is not "delete
and generate" but "recompute what is active": items from documents in the window
are active, items from documents outside it are not, and the generator is called
only where items do not yet exist.

**A document without a date is not cut off by the window.** The header is written
by the node ETL, and it is sometimes incomplete. Silently discarding an undated
document would mean emptying the set because of a foreign format; so it stays, and
the number of such documents is said out loud — otherwise "took a week worth" would
be an untruth nobody learned about.

**An empty list of documents is no reason to empty the set.** Zero documents means
not "all the material has aged out" but that there was nothing to read: the
collection is empty, all the chunks are below the threshold, the index is being
rebuilt. Deciding on such an input is not allowed: a recompute would take every
last item out of the measurement, the next run would measure emptiness, and it
would look like the ordinary progress of the window.

**The cohort decides on a par with the window.** There can be only one pool of
questions in the measurement: two builds over the same material would give two
verdicts for one and the same thing, and the share would be computed over the union
of two different sets. So the current cohort stays active and the previous ones are
taken out whole — without being deleted: they carry the verdicts the new one will
be compared against.

This module does not see the documents — only their identifiers and dates. Corpus
text is read by one package, ``sources`` (invariant 1), and the decision "what is
in the measurement now" must not know it: it is about time and bookkeeping, not
about content.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from loguru import logger
from sqlalchemy import select, update

from syft_benchmark.config import DatasetMode, PairStatus, Settings, get_settings
from syft_benchmark.db import QaPair, session_scope


@dataclass(slots=True)
class RotationReport:
    """What became of the set after a recompute."""

    space: str
    active: int = 0
    retired: int = 0
    revived: int = 0
    over_cap: int = 0
    undated: int = 0
    window_days: int = 0
    cohort: str = ""
    # Items of previous cohorts taken out of the measurement by this recompute.
    # Counted separately from those that left by the window: the reason is different,
    # and so is the cure.
    other_cohorts: int = 0
    notes: list[str] = field(default_factory=list)

    def line(self) -> str:
        parts = [f"in the measurement {self.active}"]
        if self.revived:
            parts.append(f"returned {self.revived}")
        if self.retired:
            parts.append(f"left the set {self.retired}")
        if self.over_cap:
            parts.append(f"over the cap {self.over_cap}")
        if self.other_cohorts:
            parts.append(f"from previous cohorts {self.other_cohorts}")
        return ", ".join(parts)


# How many days in a unit of the period. A month and a year are approximate here,
# and that is deliberate: the freshness window answers the question "how long ago",
# not "since what date". Calendar precision would add a difference of a day or two
# to a quantity that is set by eye in the first place.
_PERIOD_UNITS = {"d": 1, "w": 7, "m": 30, "y": 365}


class BadPeriod(ValueError):
    """The period is written in a way that cannot be read."""


def parse_period(text: str) -> int:
    """The period in days from a human notation.

    Accepts ``7d``, ``2w``, ``1m``, ``1y`` and a bare number of days. Zero means "no
    window" — the whole corpus.

    Days, not dates: the period is counted backwards from "now", not from midnight.
    For the nightly cycle it makes no difference, and for a run in the middle of the
    day "since yesterday" is more honestly read as "over the last 24 hours" than to
    guess that a human meant a calendar day.

    Args:
        text: The period notation

    Returns:
        The number of days; 0 — no window

    Raises:
        BadPeriod: the notation does not parse
    """
    raw = (text or "").strip().lower()
    if not raw:
        return 0
    unit = 1
    if raw[-1] in _PERIOD_UNITS:
        unit = _PERIOD_UNITS[raw[-1]]
        raw = raw[:-1].strip()
    try:
        count = int(raw)
    except ValueError as exc:
        raise BadPeriod(
            f"the period {text!r} cannot be read: a number of days is needed, or a "
            f"notation of the form 7d, 2w, 1m, 1y"
        ) from exc
    if count < 0:
        raise BadPeriod(f"the period {text!r} is negative")
    return count * unit


def window_start(settings: Settings, *, now: datetime | None = None) -> datetime | None:
    """The boundary of the freshness window, or None if there is no window."""
    days = settings.document_window_days
    if days <= 0:
        return None
    return (now or datetime.now(UTC)) - timedelta(days=days)


def fresh_ids(
    dated: Mapping[str, datetime | None],
    settings: Settings,
    *,
    now: datetime | None = None,
) -> tuple[set[str], int]:
    """The documents that fall inside the freshness window.

    Args:
        dated: Document identifier -> its date; None means "there is no date"
        settings: The process settings
        now: The moment to count from; None — now

    Returns:
        The identifiers inside the window and how many of them are undated
    """
    since = window_start(settings, now=now)
    if since is None:
        return set(dated), 0

    kept: set[str] = set()
    undated = 0
    for doc_id, at in dated.items():
        if at is None:
            # The header is written by the node ETL, and it is sometimes incomplete.
            # Discarding a document because of a foreign format means emptying the
            # set silently.
            undated += 1
            kept.add(doc_id)
            continue
        if at >= since:
            kept.add(doc_id)
    return kept, undated


def _count_active(space: str, settings: Settings) -> int:
    """How many items are in the measurement now."""
    with session_scope(settings) as session:
        return len(
            list(
                session.execute(
                    select(QaPair.id).where(
                        QaPair.space == space,
                        QaPair.status == PairStatus.ACTIVE.value,
                    )
                ).scalars()
            )
        )


def _pick_within_cap(rows: list[QaPair], cap: int) -> set[str]:
    """Which items to keep in the measurement when there are more than the cap.

    The cap is a total, so it is divided round-robin across the generators: an item
    to each in turn, until either the budget or the items run out. That way all the
    skills are represented rather than those that happened to come first.

    There is deliberately no round-robin over the halves of the set here, and that is
    not a simplification. Each generator produces items of exactly one half, so
    having the generators represented already entails having the halves represented —
    whereas a separate round over halves would give the two control generators as
    much room as the eight ordinary ones.
    """
    if cap <= 0 or len(rows) <= cap:
        return {row.id for row in rows}

    buckets: dict[str, list[QaPair]] = {}
    for row in rows:
        buckets.setdefault(row.generator or "", []).append(row)

    picked: set[str] = set()
    while len(picked) < cap:
        taken = False
        for key in sorted(buckets):
            bucket = buckets[key]
            if not bucket:
                continue
            picked.add(bucket.pop(0).id)
            taken = True
            if len(picked) >= cap:
                break
        if not taken:
            break
    return picked


def rotate(
    space: str,
    dated: Mapping[str, datetime | None],
    *,
    cohort: str = "",
    rebuilding: bool = False,
    settings: Settings | None = None,
    now: datetime | None = None,
) -> RotationReport:
    """Recompute which items are in the measurement now.

    Called after generation: it adds items from new material, and here it is decided
    what of what has accumulated takes part in the measurement today.

    Works only in rolling mode. In incremental mode the set accumulates and there is
    nothing to take out of it — the call returns the state without changing anything.

    Args:
        space: The Space key
        dated: Document identifier -> its date; the window is built from them
        cohort: The cohort that stays in the measurement; earlier ones are taken out
        rebuilding: A rebuild is under way. The period then applies regardless of the
            mode: a human named it outright, and the set is obliged to keep within it
        settings: The process settings
        now: The moment to count from; None — now

    Returns:
        # There was nothing to read. This is a state of the rig rather than a
        # sentence on the set: a recompute over such an input would take every
        # last item out of the measurement, and the next run would measure
        # emptiness.
    """
    conf = settings or get_settings()
    report = RotationReport(
        space=space, window_days=conf.document_window_days, cohort=cohort
    )

    if not dated:
        # There was nothing to read. This is a state of the rig rather than a sentence
        # on the set: a recompute over such an input would take every last item out of
        # the measurement, and the next run would measure emptiness.
        report.notes.append(
            "no documents were read — the set was left as it is: "
            "an empty corpus is no reason to take items out of the measurement"
        )
        report.active = _count_active(space, conf)
        # The freshness window takes items out of the measurement where the set moves
        # with time, and on every rebuild. In incremental mode without a rebuild it
        # limits what to BUILD from, while what has been built stays: an accumulating
        # set accumulates for a reason.
        return report

    # The freshness window takes items out of the measurement where the set moves with
    # time, and on every rebuild. In incremental mode without a rebuild it limits what
    # to BUILD from, while what has been built stays: an accumulating set accumulates
    # for a reason.
    windowed = rebuilding or conf.dataset_mode in (
        DatasetMode.ROLLING,
        DatasetMode.REBUILD,
    )
    if windowed:
        fresh, undated = fresh_ids(dated, conf, now=now)
        report.undated = undated
        if undated:
            report.notes.append(
                f"{undated} documents have no date in the header — the window does "
                f"not apply to them, and they stay in the set"
            )
    else:
        # Without a window the document is beside the point: the set accumulates, and
        # a document that has disappeared from the collection is no reason to take out
        # of the measurement an item that already has verdicts collected.
        fresh = set()

    # Fit ones are the active and the retired: screened-out ones never come back —
    # their gold answer failed the check, and the window has nothing to do with it.
    with session_scope(conf) as session:
        rows = list(
            session.execute(
                select(QaPair).where(
                    QaPair.space == space,
                    QaPair.status.in_(
                        [PairStatus.ACTIVE.value, PairStatus.RETIRED.value]
                    ),
                )
            ).scalars()
        )
        for row in rows:
            session.expunge(row)

    # Only the current cohort is in the measurement. Two builds over the same material
    # would give two verdicts for one question, and the share would be computed over
    # the union of two different sets.
    eligible = [
        row
        for row in rows
        if (not windowed or row.doc_id in fresh) and (row.cohort or "") == cohort
    ]
    report.other_cohorts = sum(
        1
        for row in rows
        if (row.cohort or "") != cohort and row.status == PairStatus.ACTIVE.value
    )
    keep = _pick_within_cap(eligible, conf.dataset_max_pairs)
    report.over_cap = len(eligible) - len(keep)

    to_activate = [
        row.id
        for row in rows
        if row.id in keep and row.status == PairStatus.RETIRED.value
    ]
    to_retire = [
        row.id
        for row in rows
        if row.id not in keep and row.status == PairStatus.ACTIVE.value
    ]

    with session_scope(conf) as session:
        if to_activate:
            session.execute(
                update(QaPair)
                .where(QaPair.id.in_(to_activate))
                .values(
                    status=PairStatus.ACTIVE.value,
                    status_note="returned into the freshness window",
                )
            )
        if to_retire:
            session.execute(
                update(QaPair)
                .where(QaPair.id.in_(to_retire))
                .values(
                    status=PairStatus.RETIRED.value,
                    status_note=(
                        f"cohort {cohort} replaced the previous one"
                        if cohort
                        else f"the document is outside the "
                        f"{conf.document_window_days}-day window"
                        if conf.document_window_days
                        else "over the set cap"
                    ),
                )
            )

    report.revived = len(to_activate)
    report.retired = len(to_retire)
    report.active = len(keep)

    logger.info(f"{space}: the set was recomputed — {report.line()}")
    return report
