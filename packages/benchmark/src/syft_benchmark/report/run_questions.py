"""One run's questions: the paged list, one question in full, its passages.

The list is filtered and paged over the question index cached in the run's
aggregate (``run_view``); only the rows of the page are read from the pairs.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from syft_benchmark.config import EvalBlock
from syft_benchmark.db.models import Job, QaPair, Result, Run, RunExclusion
from syft_benchmark.report import run_view
from syft_benchmark.report.run_view import ALONE, ARM_OF, GROUPS, OUTCOMES, WITH

MAX_PAGE = 100
EXCLUDED_FILTERS = ("include", "only", "hide")


class UnknownModel(LookupError):
    """The model did not answer in this run."""


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _row(entry: dict[str, Any], model: str, pair: QaPair) -> dict[str, Any]:
    alone, with_, group, overridden = entry["models"].get(
        model, [None, None, None, False]
    )
    return {
        "n": entry["n"],
        "qa_id": entry["qa_id"],
        "generator": entry["generator"],
        "document_title": pair.document_title or "",
        "file_name": pair.file_name or "",
        "question": pair.question,
        "gold_answer": pair.answer,
        "status": pair.status,
        "verdict_alone": alone,
        "verdict_with": with_,
        "group": group,
        "overridden": bool(overridden),
        "excluded": bool(entry["excluded"]),
    }


def _models(run: dict[str, Any]) -> list[str]:
    return [m["model"] for m in run.get("models") or []]


def list_questions(
    session: Session,
    job: Job,
    *,
    model: str,
    group: str | None = None,
    generator: str | None = None,
    q: str | None = None,
    excluded: str = "include",
    limit: int = 25,
    offset: int = 0,
    configured: run_view.Panel = (),
) -> dict[str, Any]:
    """A page of the run's questions for one model, with counts per group.

    Raises:
        UnknownModel: the model did not answer in this run
    """
    index, run = run_view.aggregate_parts(
        session, job, "questions", "run", configured=configured
    )
    if model not in _models(run):
        raise UnknownModel(model)

    entries = [e for e in index if model in e["models"]]
    if generator:
        entries = [e for e in entries if e["generator"] == generator]
    if excluded == "only":
        entries = [e for e in entries if e["excluded"]]
    elif excluded == "hide":
        entries = [e for e in entries if not e["excluded"]]
    if q and q.strip() and entries:
        pattern = f"%{_escape(q.strip())}%"
        matched = set(
            session.execute(
                select(QaPair.id).where(
                    QaPair.space == job.target,
                    or_(
                        QaPair.question.ilike(pattern, escape="\\"),
                        QaPair.answer.ilike(pattern, escape="\\"),
                        QaPair.document_title.ilike(pattern, escape="\\"),
                    ),
                )
            ).scalars()
        )
        entries = [e for e in entries if e["qa_id"] in matched]

    counts = {"all": len(entries), **dict.fromkeys(GROUPS, 0)}
    for entry in entries:
        g = entry["models"][model][2]
        if g:
            counts[g] += 1
    if group:
        entries = [e for e in entries if e["models"][model][2] == group]

    size = max(1, min(limit, MAX_PAGE))
    page = entries[max(0, offset) : max(0, offset) + size]
    pairs = (
        {
            pair.id: pair
            for pair in session.execute(
                select(QaPair).where(QaPair.id.in_([e["qa_id"] for e in page]))
            ).scalars()
        }
        if page
        else {}
    )
    return {
        "items": [
            _row(e, model, pairs[e["qa_id"]]) for e in page if e["qa_id"] in pairs
        ],
        "total": len(entries),
        "counts": counts,
    }


def _answer_rows(
    session: Session, job: Job, model: str, qa_id: str
) -> list[tuple[Result, Run]]:
    return [
        (result, run)
        for result, run in session.execute(
            select(Result, Run)
            .join(Run, Run.id == Result.run_id)
            .where(
                Result.space == job.target,
                Result.qa_id == qa_id,
                Run.job_id == job.id,
                Run.model == model,
                Run.context_mode.in_(list(ARM_OF)),
            )
            .order_by(Result.created_at, Result.id)
        ).tuples()
    ]


def _context_docs(run: Run) -> int | None:
    value = (run.params or {}).get("context_docs")
    return int(value) if isinstance(value, int) else None


def _denial(extra: Any) -> dict[str, Any] | None:
    block = extra.get("denial") if isinstance(extra, dict) else None
    if not isinstance(block, dict):
        return None
    flip = block.get("flip_round")
    return {
        "rounds": int(block.get("rounds") or 0),
        "flipped": bool(block.get("flipped")),
        "flip_round": int(flip) if flip is not None else None,
        "limit": int(block.get("limit") or 0),
    }


def _repeats(extra: Any) -> dict[str, Any] | None:
    block = extra.get("monte_carlo") if isinstance(extra, dict) else None
    if not isinstance(block, dict) or not block.get("trials"):
        return None
    trials = int(block.get("trials") or 0)
    temperatures = block.get("by_temperature")
    return {
        "trials": trials,
        "right": round(float(block.get("accuracy") or 0.0) * trials),
        "consistency": float(block.get("consistency") or 0.0),
        "by_temperature": {
            str(k): float(v)
            for k, v in (temperatures.items() if isinstance(temperatures, dict) else ())
        },
    }


def _arm(
    rows: list[tuple[Result, Run]], arm: str, panel: Sequence[str]
) -> dict[str, Any] | None:
    by_block: dict[str, list[Result]] = defaultdict(list)
    run_of: dict[str, Run] = {}
    for result, run in rows:
        if ARM_OF[run.context_mode] == arm:
            by_block[run.block].append(result)
            run_of[result.id] = run
    picked = run_view.pick(by_block.get(EvalBlock.DIRECT.value, []), panel)
    counted = picked.counted
    if counted is None:
        return None
    base = picked.judged or counted
    override = picked.override

    def block_extra(block: str) -> Any:
        chosen = run_view.pick(by_block.get(block, []), panel).counted
        return chosen.extra if chosen is not None else None

    return {
        "answer": counted.answer,
        "verdict": run_view.verdict_of(counted.verdict, counted.answer),
        "reasoning": counted.reasoning,
        "result_id": base.id,
        "override": (
            {
                "id": override.id,
                "verdict": override.verdict,
                "reasoning": override.reasoning,
                "created_at": override.created_at.isoformat(),
            }
            if override is not None
            else None
        ),
        "retrieval": (
            {
                "hit": counted.retrieval_hit,
                "rank": counted.retrieval_rank,
                "context_docs": _context_docs(run_of[counted.id]),
            }
            if arm == WITH
            else None
        ),
        "denial": _denial(block_extra(EvalBlock.DENIAL_LOOP.value)),
        "repeats": _repeats(block_extra(EvalBlock.MONTE_CARLO.value)),
    }


def _judges(
    rows: list[tuple[Result, Run]], judges: Sequence[str]
) -> tuple[list[dict[str, Any]], bool | None]:
    latest: dict[tuple[str, str], str] = {}
    for result, run in rows:
        if run.block == EvalBlock.DIRECT.value and result.judge_model in judges:
            latest[(result.judge_model, ARM_OF[run.context_mode])] = (
                run_view.verdict_of(result.verdict, result.answer)
            )
    out = [
        {
            "model": judge,
            "primary": n == 0,
            "alone": latest.get((judge, ALONE)),
            "with": latest.get((judge, WITH)),
        }
        for n, judge in enumerate(judges)
    ]
    verdicts: list[bool] = []
    for arm in (ALONE, WITH):
        graded = [latest[(j, arm)] for j in judges if latest.get((j, arm)) in OUTCOMES]
        if len(graded) >= 2:
            verdicts.append(len(set(graded)) == 1)
    return out, (all(verdicts) if verdicts else None)


def question_detail(
    session: Session,
    job: Job,
    qa_id: str,
    *,
    model: str | None = None,
    configured: run_view.Panel = (),
) -> dict[str, Any] | None:
    """One question of the run in full; None — it did not take part.

    Raises:
        UnknownModel: the model did not answer in this run
    """
    index, run, judges = run_view.aggregate_parts(
        session, job, "questions", "run", "judges", configured=configured
    )
    models = _models(run)
    model = model or (models[0] if models else None)
    if model is None or model not in models:
        raise UnknownModel(model or "")
    pair = session.get(QaPair, qa_id)
    if pair is None:
        return None
    rows = _answer_rows(session, job, model, qa_id)
    entry = next((e for e in index if e["qa_id"] == qa_id), None)
    if entry is None:
        if not rows and not run_view.took_part(session, job.id, qa_id):
            return None
        entry = _entry_of(rows, pair, judges)
    exclusion = session.get(RunExclusion, (job.id, qa_id))
    panel = [*judges, ""]
    judge_rows, agreed = _judges(rows, judges)
    return {
        "question": _row(entry, model, pair),
        "context": pair.context,
        "arms": {ALONE: _arm(rows, ALONE, panel), WITH: _arm(rows, WITH, panel)},
        "judges": judge_rows,
        "judges_agreed": agreed,
        "exclusion": (
            {"reason": exclusion.reason, "created_at": exclusion.created_at.isoformat()}
            if exclusion is not None
            else None
        ),
    }


def _entry_of(
    rows: list[tuple[Result, Run]], pair: QaPair, judges: Sequence[str]
) -> dict[str, Any]:
    """An index entry for a question the index leaves out (a trick question)."""
    panel = [*judges, ""]
    verdicts: dict[str, str | None] = {}
    overridden = False
    for arm in (ALONE, WITH):
        direct = [
            r
            for r, run in rows
            if ARM_OF[run.context_mode] == arm and run.block == EvalBlock.DIRECT.value
        ]
        picked = run_view.pick(direct, panel)
        verdicts[arm] = (
            run_view.verdict_of(picked.counted.verdict, picked.counted.answer)
            if picked.counted is not None
            else None
        )
        overridden = overridden or picked.override is not None
    model = rows[0][1].model if rows else ""
    return {
        "qa_id": pair.id,
        "n": 0,
        "generator": pair.generator,
        "title": pair.document_title,
        "excluded": False,
        "models": {
            model: [
                verdicts[ALONE],
                verdicts[WITH],
                run_view.group_of(verdicts[ALONE], verdicts[WITH]),
                overridden,
            ]
        },
    }


def fragments(
    session: Session,
    job: Job,
    qa_id: str,
    *,
    model: str | None = None,
    configured: run_view.Panel = (),
) -> list[dict[str, Any]] | None:
    """The passages sent with the with-data answer; None — not in this run.

    Raises:
        UnknownModel: the model did not answer in this run
    """
    run, judges = run_view.aggregate_parts(
        session, job, "run", "judges", configured=configured
    )
    models = _models(run)
    model = model or (models[0] if models else None)
    if model is None or model not in models:
        raise UnknownModel(model or "")
    pair = session.get(QaPair, qa_id)
    if pair is None:
        return None
    rows = [
        (result, run_row)
        for result, run_row in _answer_rows(session, job, model, qa_id)
        if run_row.block == EvalBlock.DIRECT.value
        and ARM_OF[run_row.context_mode] == WITH
    ]
    if not rows:
        return None if not run_view.took_part(session, job.id, qa_id) else []
    picked = run_view.pick([r for r, _ in rows], [*judges, ""])
    counted = picked.judged or picked.counted
    assert counted is not None
    run_row = next(run for result, run in rows if result.id == counted.id)
    docs = [d for d in (counted.retrieved or []) if isinstance(d, dict)]
    limit = _context_docs(run_row)
    if limit:
        docs = docs[:limit]
    names = {str(d.get("file_name") or "") for d in docs} - {""}
    titles: dict[str, str] = {}
    if names:
        titles = {
            name: title
            for name, title in session.execute(
                select(QaPair.file_name, QaPair.document_title)
                .where(QaPair.space == pair.space, QaPair.file_name.in_(names))
                .distinct()
            ).tuples()
            if title
        }
    if pair.file_name and pair.document_title:
        titles[pair.file_name] = pair.document_title
    return [
        {
            "file_name": str(doc.get("file_name") or ""),
            "document_title": titles.get(str(doc.get("file_name") or ""), ""),
            "score": float(doc.get("score") or 0.0),
            "content": str(doc.get("content") or ""),
            "is_source": counted.retrieval_rank == position,
        }
        for position, doc in enumerate(docs, start=1)
    ]
