"""Stage 2: deciding which generated pairs are fit to measure with.

Every candidate generation writes lands as ``pending``, whatever its answer or
its question turn out to be worth. This module screens those pending rows as
its own pass over what is already in the database, so the owner can see the
raw output of generation before anything is screened, and can re-run screening
on its own schedule.

Two checks, both reading the persisted row rather than a fresh candidate:

  * **grounding** (``validate.py``) — does the gold answer rest on the chunk.
    Lexical, deterministic, needs nothing but the row itself (``context`` is
    the chunk, truncated the same way it always was; ``meta["claims"]``, where
    present, is what a reworded item's answer must follow from instead).
  * **the control gate** (``control.py``) — for a question built with no
    answer in the corpus, does live retrieval in fact answer it anyway. This
    one is NOT a replay of a stored verdict: it queries retrieval again, right
    now, because "there is no answer" is only ever true relative to an index
    at a moment, and the index may have grown since generation ran.

Only ``pending`` pairs are ever touched automatically — an ``active`` or
``rejected`` verdict, once made, stands until a person overturns it through
``override_status``. Re-running this on the same pending pairs twice gives the
same answer for grounding and, because retrieval may have changed, not
necessarily the same answer for the gate; neither run ever moves a pair that
already has a verdict.

This module never reads the corpus (invariant 1: only ``sources`` and the
handful of modules listed in ``test_invariants.py`` may). It decides
grounding purely off what is already stored, and the control gate through an
injected ``retrieve`` callable — the same seam ``generation/control.py`` uses.
What it does NOT do is reconcile the freshness window, the cohort or the set
cap for pairs it just turned active: that needs the document dates, which
means reading the corpus, which means it belongs to ``pipeline.py``'s
``filter_and_rotate`` instead of here. A pair filtered on its own settles
into the window at the next generation pass, the same as it always has.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, cast

from loguru import logger
from sqlalchemy import CursorResult, select, update

from syft_benchmark.config import (
    PairStatus,
    Settings,
    SpaceConfig,
    StatusReason,
    get_settings,
)
from syft_benchmark.db import QaPair, session_scope
from syft_benchmark.db.run_cache import invalidate_runs_with_pairs
from syft_benchmark.generation.control import Retriever, gate_unanswerable
from syft_benchmark.generation.generators import GENERATORS, Generator
from syft_benchmark.generation.rotation import RotationReport
from syft_benchmark.generation.validate import review_answer, review_claims
from syft_benchmark.llm import Provider, judge_providers

# Statuses that carry no status_reason.
_IN_PLAY = frozenset({PairStatus.PENDING, PairStatus.ACTIVE})


@dataclass(slots=True)
class FilterSummary:
    """What came out of one filtering pass.

    ``rotation`` is left for the caller to fill in: deciding it needs the
    document dates, which means reading the corpus, which this module never
    does (see the module docstring). ``pipeline.filter_and_rotate`` is what
    sets it.
    """

    space: str
    checked: int = 0
    active: int = 0
    rejected: int = 0
    notes: list[str] = field(default_factory=list)
    rotation: RotationReport | None = None

    def line(self) -> str:
        return (
            f"checked {self.checked} — {self.active} active, "
            f"{self.rejected} rejected"
        )


def _screen_pair(
    row: QaPair,
    generator: Generator,
    gate: Retriever | None,
    conf: Settings,
    judge: Provider | None,
) -> tuple[PairStatus, StatusReason | None, str, dict[str, Any]]:
    """The verdict on one pending pair, why, and what to fold into its ``meta``.

    Reads the persisted ``context``/``meta`` rather than a fresh candidate's
    fragment and claims — see the module docstring for why.
    """
    if not generator.is_control:
        claims = row.meta.get("claims")
        verdict = (
            review_claims([str(c) for c in claims], row.context, conf)
            if claims
            else review_answer(row.answer, row.context, conf)
        )
        if verdict.grounded:
            return PairStatus.ACTIVE, None, verdict.note, {}
        return PairStatus.REJECTED, StatusReason.GROUNDING, verdict.note, {}

    if gate is None:
        # An unchecked negative is an unfounded accusation of fabrication, same
        # as at generation time: kept as rejected rather than left pending
        # forever, and it stays material for tuning the prompt.
        return (
            PairStatus.REJECTED,
            StatusReason.RETRIEVAL_GATE,
            "control question not checked: retrieval is unavailable",
            {"gate": "not checked"},
        )

    outcome = gate_unanswerable(row.question, gate, settings=conf, judge=judge)
    return (
        PairStatus.ACTIVE if outcome.clear else PairStatus.REJECTED,
        None if outcome.clear else StatusReason.RETRIEVAL_GATE,
        outcome.note,
        {
            "gate": outcome.note,
            "gate_checked": outcome.checked,
            "gate_fragments": outcome.fragments,
        },
    )


def filter_pending(
    space: SpaceConfig,
    *,
    generator: str | None = None,
    cohort: str | None = None,
    limit: int | None = None,
    settings: Settings | None = None,
    retrieve: Retriever | None = None,
    should_stop: Callable[[], bool] | None = None,
) -> FilterSummary:
    """Screen this node's pending pairs, deciding active or rejected.

    Args:
        space: The node under test
        generator: Screen only this generator's pairs; None — every generator
        cohort: Screen only this cohort; None — every cohort
        limit: How many pending pairs to screen; None — all of them
        settings: The process settings
        retrieve: What to check control questions with; None — the control
            set is rejected outright, same as at generation time without one
        should_stop: Asked before every pair whether the owner has called the
            pass off

    Returns:
        A summary of what was screened and how it came out
    """
    conf = settings or get_settings()
    report = FilterSummary(space=space.key)

    # Built once and reused across every control-type pair: it is a Provider
    # object, not a call, so there is nothing to save by deferring it further.
    judges = judge_providers(conf)
    judge = judges[0] if judges else None

    with session_scope(conf) as session:
        query = select(QaPair).where(
            QaPair.space == space.key,
            QaPair.status == PairStatus.PENDING.value,
        )
        if generator:
            query = query.where(QaPair.generator == generator)
        if cohort:
            query = query.where(QaPair.cohort == cohort)
        if limit:
            query = query.limit(limit)
        rows = list(session.execute(query).scalars())
        for row in rows:
            session.expunge(row)

    for row in rows:
        if should_stop is not None and should_stop():
            report.notes.append("filtering was stopped at the owner's request")
            break

        spec = GENERATORS.get(row.generator)
        if spec is None:
            # The generator that made this pair no longer exists: there is
            # nothing left to re-check it against.
            status: PairStatus = PairStatus.REJECTED
            reason: StatusReason | None = StatusReason.OTHER
            note: str = f"generator {row.generator!r} is no longer known"
            meta: dict[str, Any] = {}
        else:
            status, reason, note, meta = _screen_pair(row, spec, retrieve, conf, judge)

        with session_scope(conf) as session:
            session.execute(
                update(QaPair)
                .where(QaPair.id == row.id)
                .values(
                    status=status.value,
                    status_note=note,
                    status_reason=reason.value if reason else None,
                    meta={**row.meta, **meta},
                )
            )
            invalidate_runs_with_pairs(session, [row.id])

        report.checked += 1
        if status is PairStatus.ACTIVE:
            report.active += 1
        else:
            report.rejected += 1

    logger.info(f"{space.key}: filtering — {report.line()}")
    return report


def override_status(
    pair_id: str,
    status: PairStatus,
    *,
    note: str = "",
    target_key: str | None = None,
    settings: Settings | None = None,
) -> bool:
    """Set one pair's status by hand, whatever it is now.

    Automatic filtering only ever touches ``pending`` pairs — a verdict, once
    made, stands on its own until a person looks at it and overturns it. This
    is that override: the owner reviewing the filter's output may judge a
    rejection too strict, or an active pair not good enough, and this is the
    one place that can say so regardless of the pair's current status.

    A non-active status is recorded with the reason ``owner``.

    Args:
        pair_id: The pair to change
        status: The status to set
        note: Why, for the record
        target_key: If given, a pair belonging to a different target is left
            untouched and this returns False — a session token minted for
            one target must not change another's by guessing an id
        settings: The process settings

    Returns:
        Whether a row was actually changed
    """
    conf = settings or get_settings()
    with session_scope(conf) as session:
        query = update(QaPair).where(QaPair.id == pair_id)
        if target_key is not None:
            query = query.where(QaPair.space == target_key)
        reason = None if status in _IN_PLAY else StatusReason.OWNER.value
        result = cast(
            "CursorResult[Any]",
            session.execute(
                query.values(
                    status=status.value, status_note=note, status_reason=reason
                )
            ),
        )
        if result.rowcount == 0:
            return False
        invalidate_runs_with_pairs(session, [pair_id])
        return True
