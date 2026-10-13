"""Manual answers from a chat: each verdict is counted under its own name."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from sqlalchemy import delete

from syft_benchmark.config import PairStatus, Verdict
from syft_benchmark.db.models import QaPair, Result, Run
from syft_benchmark.db.session import session_scope
from syft_benchmark.runs import console
from syft_benchmark.runs.judge import Grade

KEY = "pytest-import-answers"
VERDICTS = {
    "a1a1a1": Verdict.CORRECT,
    "b2b2b2": Verdict.HALLUCINATE,
    "c3c3c3": Verdict.TECHNICAL,
    "d4d4d4": Verdict.WEB_SOURCED,
    "e5e5e5": Verdict.ABSTAIN,
}


def _db_ready() -> bool:
    try:
        with session_scope() as session:
            session.execute(delete(QaPair).where(QaPair.space == KEY))
        return True
    except Exception:  # noqa: BLE001 - the database may simply not be at hand
        return False


needs_db = pytest.mark.skipif(
    not _db_ready(), reason="the benchmark database is unavailable"
)


@pytest.fixture
def pairs() -> Any:
    def wipe() -> None:
        with session_scope() as session:
            session.execute(delete(Result).where(Result.space == KEY))
            session.execute(delete(Run).where(Run.space == KEY))
            session.execute(delete(QaPair).where(QaPair.space == KEY))

    wipe()
    with session_scope() as session:
        for pair_id in VERDICTS:
            session.add(
                QaPair(
                    id=pair_id,
                    space=KEY,
                    generator="qa",
                    question="q",
                    answer="a",
                    context="a fragment",
                    status=PairStatus.ACTIVE.value,
                    model="m",
                    question_hash=pair_id,
                )
            )
    yield
    wipe()


@needs_db
def test_failures_and_web_answers_are_not_counted_as_hallucinations(
    pairs: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    judge = SimpleNamespace(model="judge")
    monkeypatch.setattr(console, "judge_provider", lambda conf: judge)

    def grade_item(item: Any, answer: str, **kwargs: Any) -> Grade:
        return Grade(VERDICTS[answer], "")

    monkeypatch.setattr(console, "grade_item", grade_item)
    source = tmp_path / "answers.txt"
    source.write_text(
        "\n".join(f"{pair_id}: {pair_id}" for pair_id in VERDICTS), encoding="utf-8"
    )

    report = console.import_answers(KEY, source, "console/chat")

    assert (
        report.correct,
        report.hallucinate,
        report.technical,
        report.web_sourced,
        report.abstain,
    ) == (1, 1, 1, 1, 1)
