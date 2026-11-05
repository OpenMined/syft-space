"""BLEU / ROUGE / BERTScore of one run, averaged per model and condition.

Report API, "Text metrics". The scores sit on each answer in
``Result.extra["text_metrics"]``; a panel stores the same answer once per
judge, so each answer is counted once. Direct block only: the other blocks
store the answer they started from, a copy of the direct one. Over several
jobs (a combined run) an answer asked in more than one counts from the first.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from syft_benchmark.config import EvalBlock
from syft_benchmark.db import Result, Run
from syft_benchmark.report.run_view import ALONE, ARM_OF
from syft_benchmark.runs.textmetrics import average


def job_text_metrics(session: Session, job_ids: Sequence[str]) -> list[dict[str, Any]]:
    """``[{model, arm, counted, scores}]`` of the jobs (in time order), sorted
    by model, alone first."""
    ids = list(job_ids)
    rows = session.execute(
        select(
            Run.job_id,
            Run.model,
            Run.context_mode,
            Result.qa_id,
            Result.extra["text_metrics"],
        )
        .join(Run, Run.id == Result.run_id)
        .where(
            Run.job_id.in_(ids),
            Run.block == EvalBlock.DIRECT.value,
            Run.context_mode.in_(list(ARM_OF)),
            Result.extra.has_key("text_metrics"),
        )
        .order_by(Result.created_at, Result.id)
    ).all()

    # job -> (model, arm) -> qa -> scores; the latest row of an answer wins.
    per_job: dict[str, dict[tuple[str, str], dict[str, dict[str, Any]]]] = {}
    for job, model, mode, qa_id, scores in rows:
        if not isinstance(scores, dict) or not scores:
            continue
        found = per_job.setdefault(job, {})
        found.setdefault((model or "", ARM_OF[mode]), {})[qa_id] = scores
    answers: dict[tuple[str, str], dict[str, dict[str, Any]]] = {}
    for job in ids:
        for key, by_qa in per_job.get(job, {}).items():
            merged = answers.setdefault(key, {})
            for qa_id, scores in by_qa.items():
                merged.setdefault(qa_id, scores)

    return [
        {
            "model": model,
            "arm": arm,
            "counted": len(by_qa),
            "scores": average(list(by_qa.values())),
        }
        for (model, arm), by_qa in sorted(
            answers.items(), key=lambda item: (item[0][0], item[0][1] != ALONE)
        )
    ]
