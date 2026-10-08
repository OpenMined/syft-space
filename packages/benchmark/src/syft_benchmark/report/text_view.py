"""BLEU / ROUGE / BERTScore of one run, averaged per model and condition.

Report API, "Text metrics". The scores sit on each answer in
``Result.extra["text_metrics"]``; a panel stores the same answer once per
judge, so each answer is counted once. Direct block only: the other blocks
store the answer they started from, a copy of the direct one.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from syft_benchmark.config import EvalBlock
from syft_benchmark.db import Result, Run, RunExclusion
from syft_benchmark.report.run_view import ALONE, ARM_OF
from syft_benchmark.runs.textmetrics import average


def job_text_metrics(session: Session, job_id: str) -> list[dict[str, Any]]:
    """``[{model, arm, counted, scores}]``, sorted by model, alone first."""
    excluded = set(
        session.scalars(select(RunExclusion.qa_id).where(RunExclusion.job_id == job_id))
    )
    rows = session.execute(
        select(
            Run.model,
            Run.context_mode,
            Result.qa_id,
            Result.extra["text_metrics"],
        )
        .join(Run, Run.id == Result.run_id)
        .where(
            Run.job_id == job_id,
            Run.block == EvalBlock.DIRECT.value,
            Run.context_mode.in_(list(ARM_OF)),
            Result.extra.has_key("text_metrics"),
        )
        .order_by(Result.created_at, Result.id)
    ).all()

    # (model, arm) -> qa -> scores; the latest row of an answer wins.
    answers: dict[tuple[str, str], dict[str, dict[str, Any]]] = {}
    for model, mode, qa_id, scores in rows:
        if qa_id in excluded or not isinstance(scores, dict) or not scores:
            continue
        answers.setdefault((model or "", ARM_OF[mode]), {})[qa_id] = scores

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
