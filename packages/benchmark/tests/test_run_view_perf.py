"""Timing of the results read API on a run of realistic size.

1 000 questions x 5 models x 3 judges x 2 arms, plus pressure and repeat rows.
Skipped with ``BENCH_QUICK=1``: seeding takes a while.
"""

from __future__ import annotations

import json
import os
import statistics
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, text

from syft_benchmark.config import JobState, PairStatus, get_settings
from syft_benchmark.control.app import create_app
from syft_benchmark.control.schemas import TargetSpec
from syft_benchmark.db import Job, QaPair, Result, Run, Target, session_scope

TOKEN = "test-run-view-perf-token"
KEY = "pytest-run-view-perf"
AUTH = {"Authorization": f"Bearer {TOKEN}"}
JOB = "rv-perf-job"
QUESTIONS = 1000
MODELS = [f"vendor{n}/model-{n}" for n in range(5)]
JUDGES = ["judge/a", "judge/b", "judge/c"]
GENERATORS = ["qa", "numbers", "names", "dates", "multihop", "unanswerable_property"]
VERDICTS = ["correct", "correct", "abstain", "hallucinate", "correct", "technical"]


def _db_ready() -> bool:
    try:
        with session_scope() as session:
            session.execute(delete(QaPair).where(QaPair.space == KEY))
        return True
    except Exception:  # noqa: BLE001 - the database may simply not be at hand
        return False


pytestmark = [
    pytest.mark.skipif(
        os.environ.get("BENCH_QUICK") == "1", reason="BENCH_QUICK=1: slow to seed"
    ),
    pytest.mark.skipif(not _db_ready(), reason="the benchmark database is unavailable"),
]


def _wipe() -> None:
    with session_scope() as session:
        session.execute(delete(Result).where(Result.space == KEY))
        session.execute(delete(Run).where(Run.space == KEY))
        session.execute(delete(QaPair).where(QaPair.space == KEY))
        session.execute(delete(Job).where(Job.target == KEY))
        session.execute(delete(Target).where(Target.key == KEY))


def _seed() -> None:
    t0 = datetime(2026, 9, 1, tzinfo=UTC)
    pairs = [
        {
            "id": f"perf-q{n}",
            "space": KEY,
            "generator": GENERATORS[n % len(GENERATORS)],
            "document_title": f"Article {n // 3}",
            "file_name": f"article-{n // 3}.md",
            "doc_id": f"doc-{n // 3}",
            "question": f"What happened in story {n}?",
            "answer": f"Event {n}",
            "context": f"Story {n} paragraph. " * 20,
            "status": PairStatus.ACTIVE.value,
            "model": "gen/model",
            "question_hash": f"perf-q{n}",
            "job_id": JOB,
            "distractors": [],
            "meta": {},
        }
        for n in range(QUESTIONS)
    ]
    runs: list[dict[str, Any]] = []
    results: list[dict[str, Any]] = []
    docs = [
        {"file_name": f"article-{d}.md", "score": 0.5, "content": "text " * 40}
        for d in range(3)
    ]

    def run(model: str, mode: str, block: str, judge: str) -> str:
        run_id = f"perf-run-{len(runs)}"
        runs.append(
            {
                "id": run_id,
                "space": KEY,
                "job_id": JOB,
                "context_mode": mode,
                "block": block,
                "model": model,
                "judge_model": judge,
                "params": {"context_docs": 3, "denial_rounds": 3},
            }
        )
        return run_id

    clock = 0
    for m, model in enumerate(MODELS):
        for mode in ("closed_book", "model_with_context"):
            for j, judge in enumerate(JUDGES):
                run_id = run(model, mode, "direct", judge)
                for n in range(QUESTIONS):
                    clock += 1
                    results.append(
                        {
                            "id": f"perf-r{len(results)}",
                            "run_id": run_id,
                            "qa_id": f"perf-q{n}",
                            "space": KEY,
                            "answer": f"Answer {n} from {model}",
                            "verdict": VERDICTS[(n + m + j) % len(VERDICTS)],
                            "judge_model": judge,
                            "model": model,
                            "retrieval_hit": (
                                n % 4 != 0 if mode == "model_with_context" else None
                            ),
                            "retrieval_rank": 1 if n % 4 else None,
                            "retrieved": docs if mode == "model_with_context" else [],
                            "extra": {},
                            "audit": {},
                            "created_at": t0 + timedelta(milliseconds=clock),
                        }
                    )
        for block in ("denial_loop", "monte_carlo"):
            run_id = run(model, "model_with_context", block, JUDGES[0])
            for n in range(QUESTIONS):
                clock += 1
                extra = (
                    {
                        "denial": {
                            "rounds": 3,
                            "flipped": n % 3 == 0,
                            "flip_round": 2 if n % 3 == 0 else None,
                            "limit": 3,
                            "log": [{"round": r, "reply": "x" * 200} for r in range(3)],
                        }
                    }
                    if block == "denial_loop"
                    else {
                        "monte_carlo": {
                            "trials": 4,
                            "accuracy": 0.75,
                            "consistency": 0.75,
                            "by_temperature": {"0.1": 1.0, "0.9": 0.5},
                            "log": [{"t": 0.1, "answer": "y" * 200}] * 4,
                        }
                    }
                )
                results.append(
                    {
                        "id": f"perf-r{len(results)}",
                        "run_id": run_id,
                        "qa_id": f"perf-q{n}",
                        "space": KEY,
                        "answer": "an answer",
                        "verdict": "correct",
                        "judge_model": JUDGES[0],
                        "model": model,
                        "retrieved": [],
                        "extra": extra,
                        "audit": {},
                        "created_at": t0 + timedelta(milliseconds=clock),
                    }
                )

    with session_scope() as session:
        session.add(
            Job(
                id=JOB,
                target=KEY,
                state=JobState.SUCCEEDED.value,
                created_at=t0,
                finished_at=t0 + timedelta(hours=3),
            )
        )
        session.flush()
        raw = session.connection().connection.driver_connection
        assert raw is not None
        for name, table, rows in (
            ("qa_pairs", QaPair.__table__, pairs),
            ("runs", Run.__table__, runs),
            ("results", Result.__table__, results),
        ):
            columns = [
                c
                for c in table.columns
                if c.name in rows[0] or c.server_default is None
            ]
            names = ", ".join(c.name for c in columns)
            with raw.cursor().copy(f"COPY {name} ({names}) FROM STDIN") as copy:
                for row in rows:
                    copy.write_row([_value(c, row) for c in columns])
        # A live database keeps statistics; a bulk load does not have them yet.
        session.execute(text("ANALYZE qa_pairs; ANALYZE runs; ANALYZE results"))


def _value(column: Any, row: dict[str, Any]) -> Any:
    """The row's value for a COPY, the column's Python default when absent."""
    if column.name in row:
        value = row[column.name]
    elif column.default is None:
        value = None
    elif column.default.is_callable:
        value = column.default.arg(None)
    else:
        value = column.default.arg
    return json.dumps(value) if isinstance(value, dict | list) else value


def _timed(call: Callable[[], Any], times: int = 5) -> float:
    spent = []
    for _ in range(times):
        started = time.perf_counter()
        response = call()
        spent.append(time.perf_counter() - started)
        assert response.status_code == 200, response.text
    return statistics.median(spent)


def test_the_read_api_is_fast_on_a_full_run() -> None:
    _wipe()
    try:
        started = time.perf_counter()
        _seed()
        seeded = time.perf_counter() - started

        client = TestClient(
            create_app(get_settings().model_copy(update={"control_token": TOKEN}))
        )
        body = TargetSpec(key=KEY, url="http://space.invalid").model_dump(mode="json")
        assert client.put(f"/targets/{KEY}", json=body, headers=AUTH).status_code == 200
        token = client.post(f"/targets/{KEY}/session", headers=AUTH).json()["token"]
        auth = {"Authorization": f"Bearer {token}"}

        base = f"/console/report/runs/{JOB}"
        started = time.perf_counter()
        cold = client.get(base, headers=auth)
        cold_s = time.perf_counter() - started
        assert cold.status_code == 200, cold.text
        report = cold.json()
        trick = sum(
            1
            for n in range(QUESTIONS)
            if GENERATORS[n % len(GENERATORS)] == "unanswerable_property"
        )
        assert report["run"]["questions"] == QUESTIONS - trick
        assert len(report["models"]) == len(MODELS)

        model = MODELS[0]
        timings = {
            "runs list": _timed(
                lambda: client.get("/console/report/runs", headers=auth)
            ),
            "report": _timed(lambda: client.get(base, headers=auth)),
            "questions page": _timed(
                lambda: client.get(
                    f"{base}/questions",
                    params={"model": model, "group": "fixed", "offset": 50},
                    headers=auth,
                )
            ),
            "questions search": _timed(
                lambda: client.get(
                    f"{base}/questions",
                    params={"model": model, "q": "story 12"},
                    headers=auth,
                )
            ),
            "detail": _timed(
                lambda: client.get(
                    f"{base}/questions/perf-q500", params={"model": model}, headers=auth
                )
            ),
            "fragments": _timed(
                lambda: client.get(
                    f"{base}/questions/perf-q500/fragments",
                    params={"model": model},
                    headers=auth,
                )
            ),
        }
        print(
            f"\nseeded in {seeded:.1f}s; first computation {cold_s * 1000:.0f} ms; "
            + "; ".join(f"{k} {v * 1000:.0f} ms" for k, v in timings.items())
        )
        assert cold_s < 5.0
        assert timings["runs list"] < 0.3
        assert timings["report"] < 0.5
        assert timings["questions page"] < 0.3
        assert timings["questions search"] < 0.3
        assert timings["detail"] < 0.3
        assert timings["fragments"] < 0.3
    finally:
        _wipe()
