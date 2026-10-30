"""A further verdict on an answer already recorded, as new rows beside the old.

Deferred judging, console judging and owner overrides never mutate a stored
``Result``: each adds a ``Run`` copied from the answer's run and a ``Result``
copied from the answer, carrying the new verdict. Every reader takes the
freshest row per question, so the new one stands without anything older being
lost.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from syft_benchmark.db import Result, Run
from syft_benchmark.db.run_cache import invalidate_run

# The keys of a result's ``audit`` that record who judged it and that judge's
# model call. A new verdict on the same answer drops them: carried over, they
# would show the original judge's prompt, reply and cost on the new verdict's
# row and count that call's cost twice. Every other key describes the answer
# (what was asked, retrieval, search) and is kept.
JUDGE_AUDIT_KEYS = frozenset(
    {
        "judge_system",
        "judge_prompt",
        "judge_raw",
        "judge_call",
        "judged_without_model",
        "judged_by_owner",
        "judged_by_console",
    }
)


def answer_audit(audit: dict[str, Any] | None) -> dict[str, Any]:
    """The answer-side part of a result's audit record."""
    return {k: v for k, v in (audit or {}).items() if k not in JUDGE_AUDIT_KEYS}


# The blocks of a result's ``extra`` recorded by pressure and repeats. A new
# verdict keeps their outcome, which the figures count, and leaves the
# transcript of their rounds, with each round's answer and judge call, on the
# result that ran them: carried over, the rounds would show twice in the export
# and their cost would count twice.
_BLOCKS = ("denial", "monte_carlo")
_BLOCK_TRANSCRIPT = frozenset({"log", "judge_system"})


def answer_extra(extra: dict[str, Any] | None) -> dict[str, Any]:
    """A result's ``extra`` for a new verdict on the same answer."""
    out = dict(extra or {})
    for name in _BLOCKS:
        block = out.get(name)
        if isinstance(block, dict):
            out[name] = {k: v for k, v in block.items() if k not in _BLOCK_TRANSCRIPT}
    return out


def columns(row: Result | Run) -> dict[str, Any]:
    """A fetched row as plain values, readable after its session closes."""
    return {column.name: getattr(row, column.name) for column in row.__table__.columns}


# Set afresh on a copied run: who judges, why, and when are the new verdict's.
_RUN_FRESH = frozenset(
    {"id", "job_id", "judge_model", "note", "started_at", "finished_at"}
)


def copy_run(
    run_row: dict[str, Any],
    *,
    space: str,
    judge_model: str,
    note: str,
    job_id: str | None,
) -> Run:
    """A new run for verdicts on the answers of ``run_row``, under a new id.

    ``run_row`` is a :func:`columns` snapshot: every column describing how the
    answer was obtained (settings snapshot, profile, endpoint, the model served)
    is copied, since the verdict is on that answer, not on today's settings.
    ``job_id`` is required: a run outside the answer's job is missing from that
    job's figures.
    """
    answer = {k: v for k, v in run_row.items() if k not in _RUN_FRESH}
    return Run(
        **answer
        | {
            "id": uuid.uuid4().hex,
            "space": space,
            "job_id": job_id,
            "judge_model": judge_model,
            "note": note,
        }
    )


# Set afresh on every copy; every other column describes the answer and is
# carried over unless the new verdict replaces it.
_ROW_IDENTITY = frozenset({"id", "run_id", "created_at"})


def copy_result(
    result_row: dict[str, Any],
    *,
    run_id: str,
    verdict: str,
    reasoning: str,
    extra: dict[str, Any],
    audit: dict[str, Any],
    judge_model: str,
    judge_served_by: str = "",
) -> Result:
    """The answer of ``result_row`` with a new verdict, under a new id.

    ``result_row`` is a :func:`columns` snapshot: every answer-side column
    (text, latency, retrieval, upstream, ...) is copied as is, and the
    verdict-side ones come from the arguments.
    """
    answer = {k: v for k, v in result_row.items() if k not in _ROW_IDENTITY}
    return Result(
        **answer
        | {
            "id": uuid.uuid4().hex,
            "run_id": run_id,
            "verdict": verdict,
            "reasoning": reasoning,
            "extra": extra,
            "audit": audit,
            "judge_model": judge_model,
            "judge_served_by": judge_served_by,
        }
    )


class VerdictRuns:
    """The runs a judge's new verdicts go into: one per answer run copied.

    A verdict belongs to the launch whose answer it grades, and different arms,
    sources, blocks and models are different measurements, so one copied run
    serves every verdict on answers of the same (job, arm, source, block,
    model). Each run is written the moment it is first needed, in the caller's
    session, and every use drops that job's cached aggregate in the same
    transaction as the verdict.
    """

    def __init__(self, space: str, judge: str, note: str) -> None:
        self.space = space
        self.judge = judge
        self.note = note
        # In the order opened.
        self.run_ids: list[str] = []
        self._by_key: dict[tuple[str, ...], str] = {}

    def run_id_for(self, session: Session, run_row: dict[str, Any]) -> str:
        """The copied run for verdicts on the answers of ``run_row``."""
        job_id = run_row["job_id"]
        invalidate_run(session, job_id)
        key = (
            str(job_id or ""),
            str(run_row["context_mode"]),
            str(run_row["context_source"]),
            str(run_row["block"]),
            str(run_row["model"]),
        )
        found = self._by_key.get(key)
        if found is not None:
            return found
        run = copy_run(
            run_row,
            space=self.space,
            judge_model=self.judge,
            note=self.note,
            job_id=job_id,
        )
        session.add(run)
        # The verdict's row refers to the run: the run is inserted first.
        session.flush()
        self._by_key[key] = run.id
        self.run_ids.append(run.id)
        return run.id
