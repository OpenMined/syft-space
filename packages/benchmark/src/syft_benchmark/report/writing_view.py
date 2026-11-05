"""A job's writer calls that threw drafts away or failed (``WriterCall``).

A call is stored once, its drops keyed by kind; it is served as one item per
kind, so a kind's page reads only its own drafts.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from sqlalchemy import case, func, select, tuple_
from sqlalchemy.orm import Session

from syft_benchmark.db.models import WriterCall
from syft_benchmark.generation.generators import GENERATORS
from syft_benchmark.report.job_params import iso

MAX_PAGE = 200


def system_prompts(session: Session, rows: Sequence[WriterCall]) -> dict[str, str]:
    """Each row's system prompt, by row id, in one query for the rows that
    leave it to an earlier row of their job (``WriterCall.system``)."""
    wanted = {(row.job_id, row.system_digest) for row in rows if not row.system}
    found: dict[tuple[str, str], str] = {}
    if wanted:
        found = {
            (job_id, signed): text
            for job_id, signed, text in session.execute(
                select(
                    WriterCall.job_id,
                    WriterCall.system_digest,
                    func.min(WriterCall.system),
                )
                .where(
                    tuple_(WriterCall.job_id, WriterCall.system_digest).in_(
                        sorted(wanted)
                    ),
                    WriterCall.system != "",
                )
                .group_by(WriterCall.job_id, WriterCall.system_digest)
            ).tuples()
        }
    return {
        row.id: row.system or found.get((row.job_id, row.system_digest), "")
        for row in rows
    }


def job_writing(
    session: Session,
    job_id: str,
    *,
    generator: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    """The job's kept writer calls per kind, in registry order, then time, paged."""
    calls = select(
        WriterCall.id.label("id"),
        func.jsonb_object_keys(WriterCall.dropped).label("kind"),
    ).where(WriterCall.job_id == job_id)
    if generator:
        calls = calls.where(WriterCall.dropped.has_key(generator))
    per_kind = calls.subquery()
    where = [per_kind.c.kind == generator] if generator else []
    total = session.execute(
        select(func.count()).select_from(per_kind).where(*where)
    ).scalar_one()
    registry = case(
        {key: i for i, key in enumerate(GENERATORS)},
        value=per_kind.c.kind,
        else_=len(GENERATORS),
    )
    page = max(1, min(limit, MAX_PAGE))
    rows = session.execute(
        select(WriterCall, per_kind.c.kind)
        .join(per_kind, per_kind.c.id == WriterCall.id)
        .where(*where)
        .order_by(registry, per_kind.c.kind, WriterCall.created_at, WriterCall.id)
        .limit(page)
        .offset(offset)
    ).all()
    systems = system_prompts(session, [row for row, _ in rows])
    return {
        "items": [
            {
                "call": row.call,
                "generator": kind,
                "model": row.model,
                "at": iso(row.created_at),
                "document_title": row.document_title,
                "file_name": row.file_name,
                "passage": row.passage,
                "system": systems.get(row.id, ""),
                "user": row.user,
                "reply": row.reply,
                "cost_usd": row.cost_usd,
                "latency_s": row.latency_s,
                "error": row.error,
                "dropped": list((row.dropped or {}).get(kind) or []),
            }
            for row, kind in rows
        ],
        "total": total,
    }
