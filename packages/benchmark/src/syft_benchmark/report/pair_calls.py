"""The writer and entity-check calls behind generated pairs, for any pair of a call.

A call's texts sit on the first pair stored from it (``recorded``); its other
pairs carry only the call id. Both calls are made for one unit by the build
that writes its pairs, so the pair carrying a call's texts is in the same
target, job and unit (``chunk_id``) as every pair naming it. A writer call
whose texts are on no pair is read from the writer-call log (``WriterCall``),
which keeps the calls that dropped drafts or failed.
"""

from __future__ import annotations

from collections.abc import Collection, Sequence
from typing import Any, Protocol

from sqlalchemy import ColumnElement, or_, select
from sqlalchemy.orm import Session

from syft_benchmark.db.models import QaPair, WriterCall
from syft_benchmark.generation import entities, recorded
from syft_benchmark.generation.pairs import PairView
from syft_benchmark.report.writing_view import system_prompts

Calls = dict[str, dict[str, Any]]


class WrittenPair(recorded.RecordedPair, Protocol):
    """A pair, with the job and unit whose build wrote it and made its calls."""

    job_id: str | None
    chunk_id: str


def call_id(pair: recorded.RecordedPair, key: str) -> str:
    """The id of the call recorded under ``meta[key]``; empty when none is."""
    record = (pair.meta or {}).get(key)
    return str(record.get("call") or "") if isinstance(record, dict) else ""


def _missing(
    pairs: Sequence[recorded.RecordedPair], key: str, found: Calls
) -> list[str]:
    """The call ids under ``meta[key]`` of ``pairs`` that ``found`` lacks."""
    return sorted({call_id(p, key) for p in pairs} - set(found) - {""})


def _carriers(
    session: Session,
    target: str,
    pairs: Sequence[WrittenPair],
    key: str,
    calls: Sequence[str],
) -> list[QaPair]:
    """The pairs of ``target`` whose ``meta[key]`` names one of ``calls``,
    looked up only in the jobs and units of the ``pairs`` naming them.

    The unit scope runs on the ``(space, chunk_id)`` index, so the JSON test
    reads only those units' pairs, never the whole table, and never every
    jobless pair of the target.
    """
    if not calls:
        return []
    wanted = set(calls)
    naming = [p for p in pairs if call_id(p, key) in wanted]
    jobs = {p.job_id for p in naming}
    scope: list[ColumnElement[bool]] = []
    if named := sorted(j for j in jobs if j):
        scope.append(QaPair.job_id.in_(named))
    if None in jobs:
        scope.append(QaPair.job_id.is_(None))
    units = sorted({p.chunk_id for p in naming})
    column = QaPair.meta[key]["call"].astext
    return list(
        session.scalars(
            select(QaPair).where(
                QaPair.space == target,
                QaPair.chunk_id.in_(units),
                or_(*scope),
                column.in_(calls),
            )
        ).all()
    )


def writer_calls(session: Session, target: str, pairs: Sequence[WrittenPair]) -> Calls:
    """The writer calls behind ``pairs`` of ``target`` whose texts are kept
    anywhere, by call id, as ``recorded.writer_calls`` gives them: on a pair of
    the call, else in the writer-call log of the pairs' jobs."""
    calls = recorded.writer_calls(pairs)
    missing = _missing(pairs, recorded.WRITER, calls)
    carriers = _carriers(session, target, pairs, recorded.WRITER, missing)
    calls.update(recorded.writer_calls(carriers))
    jobs = {p.job_id for p in pairs if p.job_id}
    calls.update(_logged(session, _missing(pairs, recorded.WRITER, calls), jobs))
    return calls


def check_calls(session: Session, target: str, pairs: Sequence[WrittenPair]) -> Calls:
    """The entity-check calls behind ``pairs`` of ``target`` that some pair
    carries the texts of, by call id, as ``recorded.check_calls`` gives them."""
    calls = recorded.check_calls(pairs, entities.META)
    missing = _missing(pairs, entities.META, calls)
    carriers = _carriers(session, target, pairs, entities.META, missing)
    calls.update(recorded.check_calls(carriers, entities.META))
    return calls


def _logged(session: Session, calls: Collection[str], jobs: Collection[str]) -> Calls:
    """The calls among ``calls`` in the writer-call log of ``jobs``, in the
    shape of ``recorded.writer_calls``, the passage put back into ``user``."""
    if not calls or not jobs:
        return {}
    rows = session.scalars(
        select(WriterCall).where(
            WriterCall.job_id.in_(sorted(jobs)), WriterCall.call.in_(sorted(calls))
        )
    ).all()
    systems = system_prompts(session, rows)
    return {
        row.call: {
            "model": row.model,
            "system": systems[row.id],
            "user": row.user.replace(recorded.PASSAGE_MARK, row.passage),
            "reply": row.reply,
            "passage": row.passage,
            "cost_usd": row.cost_usd,
            "latency_s": row.latency_s,
        }
        for row in rows
    }


def _shown(call_id: str, texts: dict[str, Any], passage: str) -> dict[str, Any]:
    """One call as a reader sees it (``RecordedCall``)."""
    return {
        "call": call_id,
        "model": str(texts.get("model") or ""),
        "system": str(texts.get("system") or ""),
        "user": str(texts.get("user") or ""),
        "reply": str(texts.get("reply") or ""),
        "passage": passage,
        "cost_usd": texts.get("cost_usd"),
        "latency_s": texts.get("latency_s"),
    }


def pair_calls(
    session: Session, target: str, pairs: Sequence[PairView]
) -> dict[str, dict[str, dict[str, Any] | None]]:
    """Per pair id of ``target``, its ``writer_call`` and ``entity_call``
    (``RunPairResponse``).

    A writer call whose texts are kept nowhere keeps its id, with the pair's
    own context as the passage; a pair with no call recorded gets None.
    """
    written = writer_calls(session, target, pairs)
    checked = check_calls(session, target, pairs)
    out: dict[str, dict[str, dict[str, Any] | None]] = {}
    for pair in pairs:
        writer_id = call_id(pair, recorded.WRITER)
        check_id = call_id(pair, entities.META)
        texts = written.get(writer_id, {})
        out[pair.id] = {
            "writer_call": (
                _shown(writer_id, texts, str(texts.get("passage") or pair.context))
                if writer_id
                else None
            ),
            "entity_call": (
                _shown(check_id, checked[check_id], "") if check_id in checked else None
            ),
        }
    return out
