"""Stage 2: deciding which generated pairs are fit to measure with.

Every candidate generation writes lands as ``pending``, whatever its answer or
its question turn out to be worth. This module screens those pending rows as
its own pass over what is already in the database, so the owner can see the
raw output of generation before anything is screened, and can re-run screening
on its own schedule.

Three checks, all reading the persisted row rather than a fresh candidate:

  * **grounding** (``validate.py``) — does the gold answer rest on the chunk.
    Lexical, deterministic, needs nothing but the row itself (``context`` is
    the chunk, truncated the same way it always was; ``meta["claims"]``, where
    present, is what a reworded item's answer must follow from instead).
  * **the control gate** (``control.py``) — for a question built with no
    answer in the corpus, does live retrieval in fact answer it anyway. This
    one is NOT a replay of a stored verdict: it queries retrieval again, right
    now, because "there is no answer" is only ever true relative to an index
    at a moment, and the index may have grown since generation ran.
  * **the web check** (``web_check.py``) — for a grounded answerable pair,
    when ``filter_model`` is set: does a model with web search and its own
    training, and none of the publisher's data, answer it correctly. If so it
    is rejected as ``web_answerable``. A failed check leaves the pair pending
    with a note, for the next pass.

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

import threading
from collections.abc import Callable, Collection
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, cast

from loguru import logger
from sqlalchemy import CursorResult, select, update
from sqlalchemy import cast as sa_cast
from sqlalchemy.dialects.postgresql import JSONB

from syft_benchmark.config import (
    DatasetMode,
    PairStatus,
    Settings,
    SpaceConfig,
    StatusReason,
    get_settings,
)
from syft_benchmark.db import QaPair, session_scope
from syft_benchmark.db.run_cache import invalidate_runs_with_pairs
from syft_benchmark.generation import cohort as cohorts
from syft_benchmark.generation import decisions
from syft_benchmark.generation.control import Retriever, gate_unanswerable
from syft_benchmark.generation.generators import GENERATORS, Generator
from syft_benchmark.generation.rotation import OVER_CAP_NOTE, RotationReport
from syft_benchmark.generation.slots import (
    Latch,
    ModelSlots,
    endpoint_limit,
    limited,
    model_slots,
)
from syft_benchmark.generation.validate import review_answer, review_claims
from syft_benchmark.generation.web_check import (
    CONTROL_NOTE,
    WEB_ANSWERABLE,
    WebChecker,
    WebCheckSummary,
    WebVerdict,
    exclusion,
    filter_model,
    skips_manual,
    web_checked,
)
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
    # Of the rejected: answered correctly by the web check model.
    web_answerable: int = 0
    notes: list[str] = field(default_factory=list)
    rotation: RotationReport | None = None
    # None — the web check is off or had nothing to check.
    web: WebCheckSummary | None = None

    def absorb(self, other: FilterSummary) -> None:
        """Add another pass's counts and notes to this one."""
        self.checked += other.checked
        self.active += other.active
        self.rejected += other.rejected
        self.web_answerable += other.web_answerable
        self.notes += [note for note in other.notes if note not in self.notes]
        if other.web is None:
            return
        if self.web is None:
            self.web = other.web
            return
        for name in ("checked", "removed", "kept", "failed", "rechecked"):
            setattr(self.web, name, getattr(self.web, name) + getattr(other.web, name))
        self.web.own_training_only |= other.web.own_training_only
        self.web.notes += [n for n in other.web.notes if n not in self.web.notes]

    def line(self) -> str:
        line = (
            f"checked {self.checked} — {self.active} active, "
            f"{self.rejected} rejected"
        )
        if self.web is not None:
            line += f"; {self.web.line()}"
        return line


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


class Screening:
    """Screens pairs one at a time, from any number of threads.

    The unit of work for both the filter pass and the streaming checks during
    a build: ``screen`` takes one pending pair from grounding (or the control
    gate) through the web check to its verdict; ``recheck`` puts one pair
    already in the set to the web check. Model calls take a slot from
    ``slots`` (urgent: checks go before waiting generator calls); retrieval
    for the control gate is limited by ``endpoint_concurrency``.

    A pair stays pending when the owner stops the pass before it is checked,
    when its web check fails, or when the web check has stopped: the next pass
    checks it.
    """

    def __init__(
        self,
        space: str,
        conf: Settings,
        *,
        retrieve: Retriever | None = None,
        should_stop: Callable[[], bool] | None = None,
        slots: ModelSlots | None = None,
        on_verdict: Callable[[], None] | None = None,
        job_id: str = "",
    ) -> None:
        self.conf = conf
        # Every decision is stamped with this job (meta.screening); empty — none.
        self.job_id = job_id
        self.on_verdict = on_verdict
        self.report = FilterSummary(space=space)
        # The control gate's judge (Judge 1). The web check picks its own.
        judges = judge_providers(conf)
        self.judge = judges[0] if judges else None
        self.retrieve = limited(retrieve, endpoint_limit(conf))
        self.slots = slots or model_slots(conf)
        self.should_stop = Latch(should_stop)
        self.web_on = bool(filter_model(conf))
        self.web = WebChecker(conf) if self.web_on else None
        # Whether any pair reached the web check (the summary is reported then).
        self.web_used = False
        self.rechecked = 0
        self._lock = threading.Lock()

    # --- verdicts ------------------------------------------------------------
    def _decision(
        self,
        row: QaPair,
        stage: str,
        outcome: str,
        note: str,
        reason: StatusReason | None = None,
        web: Any = None,
    ) -> dict[str, Any]:
        """The ``meta.screening`` update for one decision; empty without a job."""
        if not self.job_id:
            return {}
        return decisions.stamped(
            row.meta,
            decisions.record(
                job_id=self.job_id,
                stage=stage,
                outcome=outcome,
                note=note,
                reason=reason.value if reason else None,
                web=web if isinstance(web, dict) else None,
            ),
        )

    def _web_meta(self, verdict: WebVerdict) -> dict[str, Any]:
        """The verdict's meta, its web check record stamped with the job."""
        web = verdict.meta.get("web_check")
        if not self.job_id or not isinstance(web, dict):
            return dict(verdict.meta)
        return {**verdict.meta, "web_check": {**web, "job_id": self.job_id}}

    def _write(
        self,
        row: QaPair,
        status: PairStatus,
        reason: StatusReason | None,
        note: str,
        meta: dict[str, Any],
        stage: str = decisions.GROUNDING,
    ) -> None:
        outcome = decisions.KEPT if status is PairStatus.ACTIVE else decisions.REMOVED
        web = meta.get("web_check") if stage == decisions.WEB_CHECK else None
        meta = {**meta, **self._decision(row, stage, outcome, note, reason, web)}
        with session_scope(self.conf) as session:
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
        with self._lock:
            self.report.checked += 1
            if status is PairStatus.ACTIVE:
                self.report.active += 1
            else:
                self.report.rejected += 1
            if reason is StatusReason.WEB_ANSWERABLE:
                self.report.web_answerable += 1
        if self.on_verdict is not None:
            self.on_verdict()

    def _web_note(
        self, row: QaPair, verdict: WebVerdict, outcome: str
    ) -> dict[str, Any]:
        """The pair's meta with the web check record and its stamp."""
        web = self._web_meta(verdict)
        stamp = self._decision(
            row, decisions.WEB_CHECK, outcome, verdict.note, web=web.get("web_check")
        )
        return {**row.meta, **web, **stamp}

    def _note_pending(self, row: QaPair, verdict: WebVerdict) -> None:
        meta = self._web_note(row, verdict, decisions.FAILED)
        with session_scope(self.conf) as session:
            session.execute(
                update(QaPair)
                .where(QaPair.id == row.id, QaPair.status == PairStatus.PENDING.value)
                .values(status_note=verdict.note, meta=meta)
            )

    def _note_in_set(self, row: QaPair, verdict: WebVerdict) -> None:
        # Status and note stay; the set cap reads the verdict from meta.
        outcome = decisions.FAILED if verdict.answerable is None else decisions.KEPT
        meta = self._web_note(row, verdict, outcome)
        with session_scope(self.conf) as session:
            session.execute(
                update(QaPair)
                .where(QaPair.id == row.id, QaPair.status == row.status)
                .values(meta=meta)
            )

    def stopped(self) -> bool:
        """Whether the owner has called the pass off. Said once, in the notes."""
        if not self.should_stop():
            return False
        with self._lock:
            note = "filtering was stopped at the owner's request"
            if note not in self.report.notes:
                self.report.notes.append(note)
        return True

    def _web_verdict(self, row: QaPair) -> WebVerdict | None:
        assert self.web is not None
        with self._lock:
            self.web_used = True
        if self.stopped():
            return None
        with self.slots.hold(urgent=True):
            return self.web.check(row)

    # --- the units of work ---------------------------------------------------
    def screen(self, row: QaPair) -> None:
        """One pending pair, from grounding to its verdict."""
        if self.stopped():
            return
        spec = GENERATORS.get(row.generator)
        if spec is None:
            # The generator that made this pair no longer exists: there is
            # nothing left to re-check it against.
            self._write(
                row,
                PairStatus.REJECTED,
                StatusReason.OTHER,
                f"generator {row.generator!r} is no longer known",
                {},
            )
            return

        if spec.is_control:
            with self.slots.hold(urgent=True):
                status, reason, note, meta = _screen_pair(
                    row, spec, self.retrieve, self.conf, self.judge
                )
            if self.web_on:
                meta = {**meta, "web_check": {"skipped": CONTROL_NOTE}}
            self._write(row, status, reason, note, meta, decisions.CONTROL)
            return

        status, reason, note, meta = _screen_pair(
            row, spec, self.retrieve, self.conf, self.judge
        )
        if not self.web_on or status is not PairStatus.ACTIVE:
            self._write(row, status, reason, note, meta)
            return
        excluded = exclusion(row)
        if excluded:
            # The run could not grade it either.
            self._write(
                row,
                PairStatus.REJECTED,
                StatusReason.OTHER,
                excluded,
                {**meta, "web_check": {"skipped": excluded}},
                decisions.WEB_CHECK,
            )
            return
        if skips_manual(row, self.conf):
            self._write(row, PairStatus.ACTIVE, None, note, meta)
            return

        verdict = self._web_verdict(row)
        if verdict is None:
            return
        if verdict.answerable is None:
            self._note_pending(row, verdict)
        elif verdict.answerable:
            self._write(
                row,
                PairStatus.REJECTED,
                StatusReason.WEB_ANSWERABLE,
                WEB_ANSWERABLE,
                {**meta, **self._web_meta(verdict)},
                decisions.WEB_CHECK,
            )
        else:
            self._write(
                row,
                PairStatus.ACTIVE,
                None,
                note,
                {**meta, **self._web_meta(verdict)},
                decisions.WEB_CHECK,
            )

    def recheck(self, row: QaPair) -> None:
        """One pair already in the set, put to the web check."""
        if self.web is None or skips_manual(row, self.conf):
            return
        verdict = self._web_verdict(row)
        if verdict is None:
            return
        with self._lock:
            self.rechecked += 1
        if verdict.answerable:
            self._write(
                row,
                PairStatus.REJECTED,
                StatusReason.WEB_ANSWERABLE,
                WEB_ANSWERABLE,
                self._web_meta(verdict),
                decisions.WEB_CHECK,
            )
        else:
            self._note_in_set(row, verdict)

    def summary(self) -> FilterSummary:
        """The report, with the web check's summary when it ran."""
        if self.web is not None and self.web_used:
            self.web.summary.rechecked = self.rechecked
            self.report.web = self.web.summary
            for note in self.web.summary.notes:
                if note not in self.report.notes:
                    self.report.notes.append(note)
        return self.report


def _pending_rows(
    space: str,
    conf: Settings,
    generator: str | None,
    cohort: str | None,
    limit: int | None,
) -> list[QaPair]:
    with session_scope(conf) as session:
        query = select(QaPair).where(
            QaPair.space == space,
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
    return rows


def _run_all(work: Callable[[QaPair], None], rows: list[QaPair], width: int) -> None:
    """``work`` over the rows, ``width`` at a time; the first error is raised."""
    if not rows:
        return
    with ThreadPoolExecutor(max_workers=width, thread_name_prefix="screen") as pool:
        for future in [pool.submit(work, row) for row in rows]:
            future.result()


def filter_pending(
    space: SpaceConfig,
    *,
    generator: str | None = None,
    cohort: str | None = None,
    limit: int | None = None,
    settings: Settings | None = None,
    retrieve: Retriever | None = None,
    should_stop: Callable[[], bool] | None = None,
    recheck_cohort: str | None = None,
    recheck_docs: Collection[str] | None = None,
    job_id: str = "",
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
        recheck_cohort: With the web check on, also check this cohort's pairs
            already in the set (active, or held back by the cap) that have no
            verdict from the current ``filter_model``; None — none of them
        recheck_docs: Limit those to pairs from these documents (the window);
            None — no limit
        job_id: The job every decision is stamped with; empty — none

    Returns:
        A summary of what was screened and how it came out

    Pairs are screened ``concurrency`` at a time. A grounded non-control pair
    goes through the web check (``web_check.py``) before it is made active,
    when ``filter_model`` is set. A pair whose web check failed stays pending
    with a note; one not reached stays pending as it was. Both are checked on
    the next pass. A pair already in the set that the web model answers is
    rejected the same way; one it does not keeps its status, and the set cap
    decides.
    """
    conf = settings or get_settings()
    screening = Screening(
        space.key, conf, retrieve=retrieve, should_stop=should_stop, job_id=job_id
    )
    width = max(1, conf.concurrency)
    rows = _pending_rows(space.key, conf, generator, cohort, limit)
    if conf.dataset_mode is DatasetMode.REBUILD and cohort is None:
        # A rebuild measures only the current cohort: an older cohort's pending
        # leftover screened active would be retired at once, its checks paid
        # for nothing. It stays pending.
        current = cohorts.current(space.key, conf)
        left = sum(1 for row in rows if (row.cohort or "") != current)
        if left:
            rows = [row for row in rows if (row.cohort or "") == current]
            screening.report.notes.append(
                f"{left} pending from older cohorts not screened"
            )
    _run_all(screening.screen, rows, width)

    if screening.web_on and recheck_cohort is not None and not screening.stopped():
        recheck = _unchecked_in_set(
            space.key, conf, recheck_cohort, generator, recheck_docs
        )
        _run_all(screening.recheck, recheck, width)

    report = screening.summary()
    logger.info(f"{space.key}: filtering — {report.line()}")
    return report


def _unchecked_in_set(
    space: str,
    conf: Settings,
    cohort: str,
    generator: str | None,
    docs: Collection[str] | None,
) -> list[QaPair]:
    """This cohort's pairs in the set, or held back by the cap, not yet checked
    by the current web check model. Active ones first, the newest first."""
    model = filter_model(conf)
    with session_scope(conf) as session:
        query = select(QaPair).where(
            QaPair.space == space,
            QaPair.cohort == cohort,
            (QaPair.status == PairStatus.ACTIVE.value)
            | (
                (QaPair.status == PairStatus.RETIRED.value)
                & (QaPair.status_note == OVER_CAP_NOTE)
            ),
        )
        if generator:
            query = query.where(QaPair.generator == generator)
        rows = list(session.execute(query).scalars())
        for row in rows:
            session.expunge(row)
    rows = [
        row
        for row in rows
        if row.generator in GENERATORS
        and not exclusion(row)
        and not web_checked(row, model)
        and not skips_manual(row, conf)
        and (docs is None or row.doc_id in docs)
    ]
    rows.sort(
        key=lambda row: (
            row.status != PairStatus.ACTIVE.value,
            -row.created_at.timestamp(),
            row.id,
        )
    )
    return rows


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

    A non-active status is recorded with the reason ``owner``. Every change
    stamps ``meta.manual_override`` = {status, at}: under
    ``manual_status_priority`` "manual" the web check leaves such a pair alone.

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
    stamp = {
        "status": status.value,
        "at": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    with session_scope(conf) as session:
        query = update(QaPair).where(QaPair.id == pair_id)
        if target_key is not None:
            query = query.where(QaPair.space == target_key)
        reason = None if status in _IN_PLAY else StatusReason.OWNER.value
        result = cast(
            "CursorResult[Any]",
            session.execute(
                query.values(
                    status=status.value,
                    status_note=note,
                    status_reason=reason,
                    meta=QaPair.meta.op("||")(
                        sa_cast({"manual_override": stamp}, JSONB)
                    ),
                )
            ),
        )
        if result.rowcount == 0:
            return False
        invalidate_runs_with_pairs(session, [pair_id])
        return True
