"""Recomputing the set: which items are in the measurement now.

Incremental mode accumulates; rolling and rebuild modes keep only items from
documents inside the freshness window. The rules:

* an item that leaves is ``retired``, never deleted — it carries the verdicts
  of every earlier run;
* an item whose document is back in the window becomes active again, so the
  generator is paid only where no items exist yet;
* an undated document is not cut off by the window, and how many there are is
  reported;
* an empty document list leaves the set as it is: it means nothing was read,
  not that everything aged out;
* only the current cohort is measured: two pools over one material would give
  two verdicts for the same thing;
* the set cap (``dataset_max_pairs``) is shared round-robin across generators;
* a document-scoped launch retires nothing by the window or the cap: it only
  revives its documents' current-cohort items that a recompute took out; after
  its filter pass the control kinds over ``control_max_share`` of what it asks
  are retired for good (``trim_control_share``).

This module sees only document ids and dates, never their text (invariant 1).
"""

from __future__ import annotations

import math
import random
from collections.abc import Callable, Collection, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from loguru import logger
from sqlalchemy import func, select, update

from syft_benchmark.config import (
    DatasetMode,
    PairStatus,
    Settings,
    StatusReason,
    get_settings,
)
from syft_benchmark.db import QaPair, session_scope
from syft_benchmark.db.run_cache import invalidate_runs_with_pairs
from syft_benchmark.generation.generators import CONTROL_KEYS
from syft_benchmark.generation.web_check import passed_filter, web_checked

_EPOCH = datetime.min.replace(tzinfo=UTC)
# The note on an item the set cap took out; the filter stage re-checks these.
OVER_CAP_NOTE = "over the set cap"


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
    # Items of earlier cohorts taken out of the measurement by this recompute,
    # counted apart from those that left by the window.
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


# Days per unit of a period. A month and a year are approximate: the window
# answers "how long ago", not "since what date".
_PERIOD_UNITS = {"d": 1, "w": 7, "m": 30, "y": 365}


class BadPeriod(ValueError):
    """The period is written in a way that cannot be read."""


def parse_period(text: str) -> int:
    """The period in days from a human notation.

    Accepts ``7d``, ``2w``, ``1m``, ``1y`` and a bare number of days. Zero means "no
    window" — the whole corpus. The period counts back from now, not from midnight.

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
        dated: Document identifier -> its date by ``sources.article_date``
            (a whole-day date is its last moment); None means "there is no date"
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
            # Kept, so an incomplete header does not empty the set silently.
            undated += 1
            kept.add(doc_id)
            continue
        if at >= since:
            kept.add(doc_id)
    return kept, undated


@dataclass(frozen=True, slots=True)
class WindowCount:
    """How many articles the time window holds, as generation will see it."""

    count: int  # in the window, the undated included
    undated: int
    total: int
    window_days: int


def window_count(
    dated: Mapping[str, datetime | None],
    settings: Settings,
    *,
    now: datetime | None = None,
) -> WindowCount:
    """The window as a count, by the same rule generation filters with."""
    kept, undated = fresh_ids(dated, settings, now=now)
    return WindowCount(
        count=len(kept),
        undated=undated,
        total=len(dated),
        window_days=settings.document_window_days,
    )


def _count_active(space: str, settings: Settings) -> int:
    """How many items are in the measurement now."""
    with session_scope(settings) as session:
        return session.execute(
            select(func.count())
            .select_from(QaPair)
            .where(
                QaPair.space == space,
                QaPair.status == PairStatus.ACTIVE.value,
            )
        ).scalar_one()


def _round_robin(rows: list[QaPair], cap: int) -> list[str]:
    """Up to ``cap`` ids, one per generator in turn, each bucket in ``rows`` order."""
    buckets: dict[str, list[QaPair]] = {}
    for row in rows:
        buckets.setdefault(row.generator or "", []).append(row)
    picked: list[str] = []
    while len(picked) < cap:
        taken = False
        for key in sorted(buckets):
            bucket = buckets[key]
            if not bucket:
                continue
            picked.append(bucket.pop(0).id)
            taken = True
            if len(picked) >= cap:
                break
        if not taken:
            break
    return picked


def _pick_within_cap(
    rows: list[QaPair],
    cap: int,
    *,
    order: Callable[[QaPair], Any] | None = None,
    checked: Callable[[QaPair], bool] | None = None,
) -> set[str]:
    """Which items to keep in the measurement when there are more than the cap.

    The cap is divided round-robin across the generators, so every skill is
    represented. Within a generator the items go in ``order`` (default: already
    active first, then the oldest, so a recompute does not reshuffle a set that
    still fits). Each generator builds items of one half of the set only
    (ordinary or control), so both halves are represented too; a round over
    the halves instead would give the two control generators as much room as
    all the ordinary ones.

    With ``checked`` (the web check is on) the items that passed it fill the cap
    first, and an unchecked one only takes a place nobody checked wants. Only
    active and retired items reach here.
    """
    if cap <= 0 or len(rows) <= cap:
        return {row.id for row in rows}

    ordered = sorted(rows, key=order or _stable_order)
    if checked is None:
        return set(_round_robin(ordered, cap))
    first = _round_robin([row for row in ordered if checked(row)], cap)
    rest = _round_robin([row for row in ordered if not checked(row)], cap - len(first))
    return {*first, *rest}


def _created(row: QaPair) -> datetime:
    return getattr(row, "created_at", None) or _EPOCH


def _stable_order(row: QaPair) -> tuple[bool, datetime, str]:
    """Already active first, then the oldest."""
    return (row.status != PairStatus.ACTIVE.value, _created(row), row.id)


def _newest_order(
    dated: Mapping[str, datetime | None],
) -> Callable[[QaPair], tuple[float, float, str]]:
    """The newest article first, then the newest pair: the set follows the news."""

    def key(row: QaPair) -> tuple[float, float, str]:
        at = dated.get(row.doc_id) or _EPOCH
        return (-at.timestamp(), -_created(row).timestamp(), row.id)

    return key


def _revive_scope(
    report: RotationReport, scope: Collection[str], conf: Settings
) -> RotationReport:
    """Bring back the scope's items of the cohort that a recompute retired."""
    docs = list(scope)
    with session_scope(conf) as session:
        revived = list(
            session.execute(
                update(QaPair)
                .where(
                    QaPair.space == report.space,
                    QaPair.cohort == report.cohort,
                    QaPair.doc_id.in_(docs),
                    QaPair.status == PairStatus.RETIRED.value,
                    QaPair.status_reason == StatusReason.ROTATION.value,
                )
                .values(
                    status=PairStatus.ACTIVE.value,
                    status_note="back in the measurement",
                    status_reason=None,
                )
                .returning(QaPair.id)
            ).scalars()
        )
        invalidate_runs_with_pairs(session, revived)
        report.active = session.execute(
            select(func.count())
            .select_from(QaPair)
            .where(
                QaPair.space == report.space,
                QaPair.doc_id.in_(docs),
                QaPair.status == PairStatus.ACTIVE.value,
            )
        ).scalar_one()
    report.window_days = 0
    report.revived = len(revived)
    report.notes.append(
        "document scope: the window, cohort and cap were not applied, "
        "nothing left the set"
    )
    logger.info(f"{report.space}: the scope was reconciled — {report.line()}")
    return report


def rotate(
    space: str,
    dated: Mapping[str, datetime | None],
    *,
    cohort: str = "",
    rebuilding: bool = False,
    settings: Settings | None = None,
    now: datetime | None = None,
    scope: Collection[str] | None = None,
) -> RotationReport:
    """Recompute which items are in the measurement now.

    The freshness window takes items out only in rolling and rebuild modes, or on
    a rebuild; the cohort and the cap apply in every mode.

    Args:
        space: The Space key
        dated: Document identifier -> its date; the window is built from them
        cohort: The cohort that stays in the measurement; earlier ones are taken out
        rebuilding: A rebuild is under way. The period then applies regardless of the
            mode: a human named it outright, and the set is obliged to keep within it
        settings: The process settings
        now: The moment to count from; None — now
        scope: A document-scoped launch's documents: only their items of
            ``cohort`` retired by a recompute come back, nothing leaves, and
            ``dated`` is not read; None — the whole set is recomputed

    Returns:
        What became of the set; with no documents read, the set is left as it is
    """
    conf = settings or get_settings()
    report = RotationReport(
        space=space, window_days=conf.document_window_days, cohort=cohort
    )
    if scope is not None:
        return _revive_scope(report, scope, conf)

    if not dated:
        # Nothing was read: a recompute would empty the measurement.
        report.notes.append(
            "no documents were read — the set was left as it is: "
            "an empty corpus is no reason to take items out of the measurement"
        )
        report.active = _count_active(space, conf)
        return report

    # In incremental mode without a rebuild the window only limits what to build
    # from; what has been built stays.
    windowed = rebuilding or conf.dataset_mode in (
        DatasetMode.ROLLING,
        DatasetMode.REBUILD,
    )
    if windowed:
        fresh, undated = fresh_ids(dated, conf, now=now)
        report.undated = undated
        if undated:
            report.notes.append(
                f"{undated} documents have no publication date or add time — the "
                f"window does not apply to them, and they stay in the set"
            )
    else:
        # A document gone from the collection does not take its items out.
        fresh = set()

    # Rejected items never come back: their failure has nothing to do with
    # time. Nor do those over the control share.
    with session_scope(conf) as session:
        rows = list(
            session.execute(
                select(QaPair).where(
                    QaPair.space == space,
                    QaPair.status.in_(
                        [PairStatus.ACTIVE.value, PairStatus.RETIRED.value]
                    ),
                    QaPair.status_reason.is_distinct_from(
                        StatusReason.CONTROL_SHARE.value
                    ),
                )
            ).scalars()
        )
        for row in rows:
            session.expunge(row)

    # Only the current cohort is in the measurement.
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
    model = conf.filter_model or ""
    keep = _pick_within_cap(
        eligible,
        conf.dataset_max_pairs,
        order=_newest_order(dated) if windowed else None,
        checked=(lambda row: web_checked(row, model)) if model else None,
    )
    report.over_cap = len(eligible) - len(keep)

    to_activate = [
        row.id
        for row in rows
        if row.id in keep and row.status == PairStatus.RETIRED.value
    ]
    retiring = [
        row
        for row in rows
        if row.id not in keep and row.status == PairStatus.ACTIVE.value
    ]
    to_retire = [row.id for row in retiring]
    # Why each one leaves: a newer cohort, the window, or the cap.
    reasons: dict[str, list[str]] = {}
    for row in retiring:
        if (row.cohort or "") != cohort:
            why = f"cohort {cohort} replaced the previous one"
        elif windowed and row.doc_id not in fresh:
            why = f"the document is outside the {conf.document_window_days}-day window"
        else:
            why = OVER_CAP_NOTE
        reasons.setdefault(why, []).append(row.id)

    with session_scope(conf) as session:
        if to_activate:
            session.execute(
                update(QaPair)
                .where(QaPair.id.in_(to_activate))
                .values(
                    status=PairStatus.ACTIVE.value,
                    status_note="back in the measurement",
                    status_reason=None,
                )
            )
        for why, ids in reasons.items():
            session.execute(
                update(QaPair)
                .where(QaPair.id.in_(ids))
                .values(
                    status=PairStatus.RETIRED.value,
                    status_reason=StatusReason.ROTATION.value,
                    status_note=why,
                )
            )
        invalidate_runs_with_pairs(session, [*to_activate, *to_retire])

    report.revived = len(to_activate)
    report.retired = len(to_retire)
    report.active = len(keep)

    logger.info(f"{space}: the set was recomputed — {report.line()}")
    return report


# The note on an item retired over the control share.
CONTROL_SHARE_NOTE = "over the control share"


@dataclass(frozen=True, slots=True)
class ControlTrim:
    """What ``trim_control_share`` did to a scope's set."""

    share: float
    # Questions the run will ask: ordinary, and control before the trim.
    ordinary: int
    control: int
    kept: int
    retired: tuple[str, ...]

    def note(self) -> str:
        return (
            f"control share {self.share:.0%}: {len(self.retired)} of "
            f"{self.control} control questions retired, {self.kept} kept "
            f"beside {self.ordinary} others"
        )


def control_allowance(ordinary: int, control: int, share: float) -> int:
    """How many control questions may stay beside ``ordinary`` others: the
    most that keep them within ``share`` of the total (rounded down), at
    least one when any is there."""
    if share <= 0 or control == 0:
        return control
    room = math.floor(share * ordinary / (1 - share) + 1e-9)
    return min(control, max(1, room))


def _spread(rows: Sequence[QaPair], keep: int, seed: str) -> list[str]:
    """``keep`` control rows taken round-robin over the articles in a seeded
    order, each article alternating the kinds, the one it starts with
    rotating from article to article."""
    by_doc: dict[str, dict[str, list[QaPair]]] = {}
    for row in sorted(rows, key=lambda r: (_created(r), r.id)):
        by_doc.setdefault(row.doc_id, {}).setdefault(row.generator, []).append(row)
    docs = sorted(by_doc)
    docs = random.Random(seed).sample(docs, len(docs))
    kinds = sorted(CONTROL_KEYS)
    lines: list[list[QaPair]] = []
    for at, doc in enumerate(docs):
        order = kinds[at % len(kinds) :] + kinds[: at % len(kinds)]
        buckets = [list(by_doc[doc].get(kind, ())) for kind in order]
        line: list[QaPair] = []
        while any(buckets):
            for bucket in buckets:
                if bucket:
                    line.append(bucket.pop(0))
        lines.append(line)
    picked: list[str] = []
    depth = 0
    while len(picked) < keep:
        for line in lines:
            if depth < len(line) and len(picked) < keep:
                picked.append(line[depth].id)
        depth += 1
    return picked


def trim_control_share(
    space: str, scope: Collection[str], settings: Settings | None = None
) -> ControlTrim | None:
    """Retire a document-scoped run's control questions over
    ``control_max_share`` of the questions it will ask.

    Counted over the scope's active questions that pass the web check gate,
    as the run asks them. Those kept are spread over the articles and the
    control kinds (``_spread``, seeded by the scope); the rest are retired
    with the reason ``control_share`` and never come back. None — the share
    is off or nothing is over it.
    """
    conf = settings or get_settings()
    share = conf.control_max_share
    if share <= 0:
        return None
    docs = sorted(set(scope))
    with session_scope(conf) as session:
        rows = list(
            session.execute(
                select(QaPair).where(
                    QaPair.space == space,
                    QaPair.doc_id.in_(docs),
                    QaPair.status == PairStatus.ACTIVE.value,
                )
            ).scalars()
        )
        for row in rows:
            session.expunge(row)
    asked = [row for row in rows if passed_filter(row, conf)]
    control = [row for row in asked if row.generator in CONTROL_KEYS]
    ordinary = len(asked) - len(control)
    keep = control_allowance(ordinary, len(control), share)
    if keep >= len(control):
        return None
    kept = set(_spread(control, keep, seed=f"{space}:{'|'.join(docs)}"))
    retired = tuple(sorted(row.id for row in control if row.id not in kept))
    with session_scope(conf) as session:
        session.execute(
            update(QaPair)
            .where(QaPair.id.in_(retired), QaPair.status == PairStatus.ACTIVE.value)
            .values(
                status=PairStatus.RETIRED.value,
                status_reason=StatusReason.CONTROL_SHARE.value,
                status_note=CONTROL_SHARE_NOTE,
            )
        )
        invalidate_runs_with_pairs(session, list(retired))
    trim = ControlTrim(
        share=share,
        ordinary=ordinary,
        control=len(control),
        kept=keep,
        retired=retired,
    )
    logger.info(f"{space}: {trim.note()}")
    return trim
