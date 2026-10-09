"""Round 7: the job's cost by role, its start and finish, and the full texts
of every model call kept for the export."""

from __future__ import annotations

import asyncio
import dataclasses
import threading
import uuid
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from syft_benchmark.config import (
    ContextMode,
    ContextSource,
    JobState,
    PairStatus,
    Settings,
    SpaceConfig,
    Verdict,
    get_settings,
)
from syft_benchmark.control.app import create_app
from syft_benchmark.control.schemas import TargetSpec
from syft_benchmark.db import (
    Job,
    ProcessedUnit,
    QaPair,
    Result,
    Run,
    Target,
    session_scope,
)
from syft_benchmark.generation import (
    control,
    decisions,
    filter_stage,
    pipeline,
    recorded,
    web_check,
)
from syft_benchmark.generation.generators import GENERATORS
from syft_benchmark.generation.pair import Pair
from syft_benchmark.llm import chat, cost
from syft_benchmark.report import run_view
from syft_benchmark.runs import execute
from syft_benchmark.runs import judge as run_judge
from syft_benchmark.runs.judge import Grade
from syft_benchmark.sources import Chunk, Document

KEY = "pytest-wp3-round7"
TOKEN = "test-round7-token"
AUTH = {"Authorization": f"Bearer {TOKEN}"}
OPENROUTER = "https://openrouter.ai/api/v1"
JOB = "r7-job"


def _settings(**kwargs: Any) -> Settings:
    base: dict[str, Any] = {
        "subject_url": OPENROUTER,
        "subject_key": "sk-test",
        "allow_external_models": True,
        "external_hosts": ["openrouter.ai"],
        "max_consecutive_failures": 0,
        "concurrency": 1,
        "document_window_days": 0,
    }
    return Settings(**{**base, **kwargs})


class _Calls:
    """A fake chat() that answers in turn and notes the role each call is
    charged to (``cost.role_of``, as chat() itself does)."""

    def __init__(self, *replies: str, usage: dict[str, Any] | None = None) -> None:
        self.replies = list(replies)
        self.usage = usage or {}
        self.roles: list[str | None] = []
        self.prompts: list[tuple[str, str]] = []
        self._lock = threading.Lock()

    def __call__(
        self, system: str, user: str, **kwargs: Any
    ) -> tuple[str, dict[str, Any]]:
        with self._lock:
            self.roles.append(cost.role_of(kwargs.get("role")))
            self.prompts.append((system, user))
            reply = self.replies.pop(0) if len(self.replies) > 1 else self.replies[0]
        return reply, dict(self.usage)


# --- the meter --------------------------------------------------------------


def test_the_meter_splits_the_cost_by_role_across_threads() -> None:
    with cost.cost_meter() as meter:

        def work(role: str | None) -> None:
            for _ in range(50):
                cost.charge(0.01, role)

        roles = [*cost.ROLES, None] * 4
        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(work, roles))

    by_role = meter.by_role
    assert set(by_role) == set(cost.ROLES)
    for role in cost.ROLES:
        assert by_role[role] == pytest.approx(2.0)
    # Untagged calls count in the total only.
    assert meter.total_usd == pytest.approx(10.0)
    assert sum(by_role.values()) == pytest.approx(8.0)


def test_acting_as_overrides_the_tag_in_its_thread_only() -> None:
    seen: list[str | None] = []
    with cost.acting_as(cost.WEB_CHECK):
        seen.append(cost.role_of(cost.JUDGES))
        with ThreadPoolExecutor(max_workers=1) as pool:
            seen.append(pool.submit(cost.role_of, cost.JUDGES).result())
    seen.append(cost.role_of(cost.JUDGES))
    assert seen == [cost.WEB_CHECK, cost.JUDGES, cost.JUDGES]


def test_chat_charges_its_role_from_pools_and_async_passes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def post(url: str, **_: Any) -> httpx.Response:
        body = {
            "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
            "usage": {"cost": 0.5},
        }
        return httpx.Response(200, json=body, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", post)
    conf = Settings(ollama_url="http://localhost:11434")  # type: ignore[call-arg]

    def ask(role: str | None) -> None:
        chat("s", "u", settings=conf, role=role)

    async def passes() -> None:
        loop = asyncio.get_running_loop()
        with ThreadPoolExecutor(max_workers=4) as pool:
            await asyncio.gather(
                *(
                    loop.run_in_executor(pool, ask, role)
                    for role in (cost.SUBJECTS, cost.SUBJECTS, cost.JUDGES)
                )
            )

    with cost.cost_meter() as meter:
        asyncio.run(passes())
        ask(cost.WRITER)
        ask(None)  # the access check: not in by_role

    assert meter.by_role == {
        cost.WRITER: 0.5,
        cost.WEB_CHECK: 0.0,
        cost.SUBJECTS: 1.0,
        cost.JUDGES: 0.5,
    }
    assert meter.total_usd == pytest.approx(2.5)


# --- the call sites' tags ------------------------------------------------------


def test_answers_are_subjects_and_grades_are_judges(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    answering = _Calls("Harbourton", usage={"cost_usd": 0.01, "latency_s": 1.0})
    judging = _Calls('{"correct": true, "reasoning": "same"}')
    monkeypatch.setattr(execute, "chat", answering)
    monkeypatch.setattr(run_judge, "chat", judging)
    pair = QaPair(id="x", question="Which lighthouse?", answer="Harbourton")
    conf = _settings()

    asked = execute.ask_once(
        pair,
        ContextMode.CLOSED_BOOK,
        space=SpaceConfig(key=KEY, url="http://space", endpoint="ep"),
        settings=conf,
        subject=None,
        source=ContextSource.NONE,
    )
    verdict = run_judge.grade(pair.question, pair.answer, asked.answer, settings=conf)

    assert answering.roles == [cost.SUBJECTS]
    assert judging.roles == [cost.JUDGES]
    assert verdict.verdict is Verdict.CORRECT


def test_the_web_check_charges_its_model_and_its_judge_to_web_check(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    long_answer = "Harbourton lighthouse. " * 300
    web = _Calls(long_answer, usage={"cost_usd": 0.02, "latency_s": 3.21})
    judge = _Calls(
        '{"correct": true, "reasoning": "it names it"}',
        usage={"cost_usd": 0.004, "latency_s": 0.5},
    )
    monkeypatch.setattr(web_check, "chat", web)
    monkeypatch.setattr(run_judge, "chat", judge)
    conf = _settings(filter_model="openai/gpt-5.1")
    row = QaPair(
        id="w",
        generator="qa",
        task_type=GENERATORS["qa"].task_type,
        question="Which lighthouse was restored?",
        answer="Harbourton lighthouse",
        meta={},
    )
    checker = web_check.WebChecker(conf)
    verdict = checker.check(row)

    assert verdict is not None and verdict.answerable is True
    assert web.roles == [cost.WEB_CHECK]
    assert judge.roles == [cost.WEB_CHECK]
    record = verdict.meta["web_check"]
    assert record["answer"] == long_answer.strip() or record["answer"] == long_answer
    assert record["system"] == web.prompts[0][0]
    assert record["user"] == row.question
    assert (record["cost_usd"], record["latency_s"]) == (0.02, 3.21)
    assert record["judge_prompt"] == judge.prompts[0][1]
    assert record["judge_system"] == judge.prompts[0][0]
    assert record["judge_reply"].startswith('{"correct": true')
    assert (record["judge_cost_usd"], record["judge_latency_s"]) == (0.004, 0.5)

    short = web_check.lean(record)
    assert len(short["answer"]) == 2000
    assert not set(web_check.FULL_KEYS) & set(short)


def test_the_control_gate_is_web_check_and_keeps_its_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gate = _Calls(
        '{"answered": false, "where": ""}', usage={"cost_usd": 0.003, "latency_s": 2}
    )
    monkeypatch.setattr(control, "chat", gate)

    outcome = control.gate_unanswerable(
        "What colour is the lighthouse door?",
        lambda _q: ["The lighthouse was restored."],
        settings=_settings(),
    )

    assert outcome.clear is True
    assert gate.roles == [cost.WEB_CHECK]
    assert outcome.call["user"] == gate.prompts[0][1]
    assert "The lighthouse was restored." in outcome.call["user"]
    assert outcome.call["system"] == gate.prompts[0][0]
    assert outcome.call["reply"].startswith('{"answered": false')
    assert (outcome.call["cost_usd"], outcome.call["latency_s"]) == (0.003, 2.0)


def test_the_writer_is_writer_and_its_call_is_recorded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    writer = _Calls(
        '[{"question": "Q?", "answer": "A"}]',
        usage={"cost_usd": 0.05, "latency_s": 4.0},
    )
    monkeypatch.setattr(pipeline, "chat", writer)
    chunk = Chunk(
        chunk_id="c1",
        doc_id="d1",
        chunk_index=0,
        text="The council restored the Harbourton lighthouse.",
        file_name="d.md",
        headings="",
    )
    doc = Document(
        doc_id="d1", title="D", url="", source="", file_name="d.md", chunks=[chunk]
    )
    call: dict[str, Any] = {}

    pipeline._run_llm_generator(
        GENERATORS["qa"],
        doc,
        chunk,
        _settings(),
        pipeline.generator_provider(_settings()),
        record=call,
    )

    assert writer.roles == [cost.WRITER]
    assert (call["system"], call["user"]) == writer.prompts[0]
    assert call["reply"] == '[{"question": "Q?", "answer": "A"}]'
    assert call["passage"] == chunk.text
    assert (call["cost_usd"], call["latency_s"]) == (0.05, 4.0)


# --- the writer's record ------------------------------------------------------


def test_the_writer_texts_are_stored_once_per_call() -> None:
    passage = "The council restored the Harbourton lighthouse."
    call = recorded.new_call(
        model="gen/m",
        system="SYSTEM",
        user=f'Document: D\n\nFragment:\n"""\n{passage}\n"""\n\nGenerate 2.',
        reply="[...]",
        passage=passage,
        usage={"cost_usd": 0.01, "latency_s": 1.5},
    )
    first = recorded.writer_meta(call, passage)
    second = recorded.writer_meta(call, passage)

    assert second == {"call": call["call"]}
    assert recorded.PASSAGE_MARK in first["user"]
    assert passage not in first["user"]
    # The passage is the pair's context: not stored again.
    assert "passage" not in first

    pairs = [
        SimpleNamespace(meta={"writer": first}, context=passage),
        SimpleNamespace(meta={"writer": second}, context=passage),
    ]
    calls = recorded.writer_calls(pairs)
    assert set(calls) == {call["call"]}
    assert calls[call["call"]]["user"] == call["user"]
    assert calls[call["call"]]["passage"] == passage
    assert recorded.writer_call(pairs[1], calls) == calls[call["call"]]


def test_a_passage_unlike_the_context_is_kept() -> None:
    text = "Long document text. " * 10
    call = recorded.new_call(
        model="gen/m",
        system="S",
        user=f"Text:\n{text}\nGenerate 1.",
        reply="{}",
        passage=text,
        usage={},
    )
    first = recorded.writer_meta(call, text[:50])
    assert first["passage"] == text
    pair = SimpleNamespace(meta={"writer": first}, context=text[:50])
    assert recorded.writer_calls([pair])[call["call"]]["user"] == call["user"]


# --- answers -------------------------------------------------------------------


def test_the_answer_audit_keeps_whole_prompts_and_the_calls() -> None:
    conf = _settings(audit_max_chars=1000)
    asked = execute.Asked(
        answer="a",
        latency=1.0,
        system="S" * 3000,
        user="U" * 30000,
        retrieval={},
        context_source=ContextSource.NONE,
        context="C" * 3000,
        usage={"cost_usd": 0.07, "finish_reason": "stop"},
    )
    verdict = Grade(
        Verdict.CORRECT,
        "ok",
        judge_system="J" * 3000,
        judge_user="P" * 3000,
        judge_raw="R" * 3000,
        cost_usd=0.002,
        latency_s=0.8,
    )

    record = execute.audit_record(asked, verdict, conf)

    assert len(record["responder_system"]) == 3000
    assert len(record["responder_prompt"]) == 30000
    assert len(record["judge_system"]) == 3000
    assert len(record["judge_prompt"]) == 3000
    assert len(record["judge_raw"]) == 3000
    assert len(record["context"]) == 1000
    assert record["call"]["cost_usd"] == 0.07
    assert record["judge_call"] == {"cost_usd": 0.002, "latency_s": 0.8}


# --- the database ---------------------------------------------------------------


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
def clean() -> Iterator[None]:
    def wipe() -> None:
        with session_scope() as session:
            session.execute(delete(Result).where(Result.space == KEY))
            session.execute(delete(Run).where(Run.space == KEY))
            session.execute(delete(QaPair).where(QaPair.space == KEY))
            session.execute(delete(ProcessedUnit).where(ProcessedUnit.space == KEY))
            session.execute(delete(Job).where(Job.target == KEY))
            session.execute(delete(Target).where(Target.key == KEY))

    wipe()
    yield
    wipe()


def _space() -> SpaceConfig:
    return SpaceConfig(key=KEY, url="http://space:8080", endpoint="ep")


def _rows() -> list[QaPair]:
    with session_scope() as session:
        rows = list(
            session.execute(
                select(QaPair).where(QaPair.space == KEY).order_by(QaPair.created_at)
            ).scalars()
        )
        for row in rows:
            session.expunge(row)
    return rows


@needs_db
def test_generated_pairs_carry_their_writer_call(
    clean: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    documents = [
        Document(
            doc_id=f"doc{d}",
            title=f"Doc {d}",
            url="",
            source="",
            file_name=f"doc{d}.md",
            chunks=[
                Chunk(
                    chunk_id=f"doc{d}_0",
                    doc_id=f"doc{d}",
                    chunk_index=0,
                    text=f"The council restored the Harbourton lighthouse ({d}).",
                    file_name=f"doc{d}.md",
                    headings="",
                )
            ],
        )
        for d in range(2)
    ]

    class _Chroma:
        def __init__(self, *_: Any) -> None: ...

        def collection_id(self, _name: str) -> str:
            return "cid"

    def clean_items(items: Any, n: int, whole: str) -> tuple[list[Pair], list[str]]:
        return [
            Pair(question=f"Q{uuid.uuid4().hex}?", answer="A", distractors=[], meta={})
            for _ in range(2)
        ], []

    writer = _Calls('[{"x": 1}]', usage={"cost_usd": 0.01, "latency_s": 1.0})
    monkeypatch.setattr(pipeline, "ChromaClient", _Chroma)
    monkeypatch.setattr(pipeline, "load_documents", lambda *_: documents)
    monkeypatch.setattr(pipeline, "chat", writer)
    monkeypatch.setitem(
        GENERATORS, "qa", dataclasses.replace(GENERATORS["qa"], clean=clean_items)
    )

    pipeline.generate_for_space(
        _space(), generators=("qa",), settings=_settings(pairs_per_chunk=2), job=JOB
    )

    rows = _rows()
    assert len(rows) == 4
    by_call: dict[str, list[QaPair]] = {}
    for row in rows:
        by_call.setdefault(row.meta["writer"]["call"], []).append(row)
    assert len(by_call) == 2
    for siblings in by_call.values():
        assert sum("system" in r.meta["writer"] for r in siblings) == 1
    calls = recorded.writer_calls(rows)
    assert sorted(c["user"] for c in calls.values()) == sorted(
        user for _, user in writer.prompts
    )
    for row in rows:
        found = recorded.writer_call(row, calls)
        assert found is not None
        assert found["passage"] == row.context
        assert found["reply"] == '[{"x": 1}]'


def _pair(pair_id: str, generator: str = "qa", **extra: Any) -> QaPair:
    return QaPair(
        id=pair_id,
        space=KEY,
        generator=generator,
        task_type=GENERATORS[generator].task_type,
        doc_id="d1",
        question=f"Question {pair_id}: which landmark was restored?",
        answer="Harbourton lighthouse",
        context="The council restored the Harbourton lighthouse this spring.",
        status=PairStatus.PENDING.value,
        model="gen/model",
        question_hash=uuid.uuid4().hex,
        **extra,
    )


def _add(*rows: Any) -> None:
    with session_scope() as session:
        for row in rows:
            session.add(row)
            session.flush()


def _meta(pair_id: str) -> dict[str, Any]:
    with session_scope() as session:
        row = session.get(QaPair, pair_id)
        assert row is not None
        return dict(row.meta)


@needs_db
def test_filter_decisions_keep_the_full_texts_once(
    clean: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    _add(_pair("p-web"), _pair("p-control", "unanswerable_property"))
    long_answer = "x" * 5000
    monkeypatch.setattr(web_check, "chat", _Calls(long_answer))
    monkeypatch.setattr(run_judge, "chat", _Calls('{"correct": false}'))
    gate = _Calls('{"answered": false}')
    monkeypatch.setattr(control, "chat", gate)

    filter_stage.filter_pending(
        _space(),
        settings=_settings(filter_model="openai/gpt-5.1"),
        retrieve=lambda _q: ["An unrelated fragment."],
        job_id=JOB,
    )

    meta = _meta("p-web")
    entry = decisions.of_job(meta, JOB)
    assert entry is not None and entry["stage"] == "web_check"
    assert entry["web"]["answer"] == long_answer
    assert entry["web"]["user"] == "Question p-web: which landmark was restored?"
    assert entry["web"]["judge_reply"] == '{"correct": false}'
    # The pair's current record stays short.
    assert len(meta["web_check"]["answer"]) == 2000
    assert "judge_prompt" not in meta["web_check"]

    meta = _meta("p-control")
    entry = decisions.of_job(meta, JOB)
    assert entry is not None and entry["stage"] == "control"
    assert entry["gate"]["user"] == gate.prompts[0][1]
    assert entry["gate"]["reply"] == '{"answered": false}'
    assert filter_stage.GATE_CALL not in meta
    assert "gate" in meta  # the gate note, as before


# --- job times and the stored cost ---------------------------------------------


@pytest.fixture
def client() -> TestClient:
    conf = get_settings().model_copy(update={"control_token": TOKEN})
    return TestClient(create_app(conf))


def _console(client: TestClient) -> dict[str, str]:
    body = TargetSpec(key=KEY, url="http://space.invalid").model_dump(mode="json")
    assert client.put(f"/targets/{KEY}", json=body, headers=AUTH).status_code == 200
    minted = client.post(f"/targets/{KEY}/session", headers=AUTH)
    assert minted.status_code == 200, minted.text
    return {"Authorization": f"Bearer {minted.json()['token']}"}


def test_job_times_use_started_at() -> None:
    created = datetime(2026, 10, 9, 5, 0, tzinfo=UTC)
    job = Job(
        id="t",
        created_at=created,
        started_at=created + timedelta(minutes=10),
        finished_at=created + timedelta(minutes=64),
    )
    times = run_view.job_times(job)
    assert times["duration_s"] == 54 * 60
    assert times["started_at"] == (created + timedelta(minutes=10)).isoformat()
    queued = run_view.job_times(Job(id="q", created_at=created))
    assert queued == {"started_at": None, "finished_at": None, "duration_s": None}


@needs_db
def test_a_job_keeps_its_cost_by_role_and_its_times(
    client: TestClient, clean: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from syft_benchmark.control import jobs

    auth = _console(client)
    reads = iter([10.0, 10.5])
    monkeypatch.setattr(jobs, "openrouter_spend", lambda conf: next(reads))

    def judging(*_: Any, **__: Any) -> Any:
        cost.charge(0.2, cost.JUDGES)
        cost.charge(0.05, cost.WEB_CHECK)
        cost.charge(0.01)
        return SimpleNamespace(line=lambda: "", notes=[])

    monkeypatch.setattr(jobs, "judge_pending", judging)
    _add(Job(id=JOB, target=KEY, kind="judge", state="queued", params={}))
    _add(_pair("p-1", job_id=JOB))

    jobs.execute(JOB)

    with session_scope() as session:
        row = session.get(Job, JOB)
        assert row is not None and row.state == JobState.SUCCEEDED.value
        assert row.started_at is not None and row.finished_at is not None
        took = (row.finished_at - row.started_at).total_seconds()
        stored = row.params[run_view.COST]
        timing = row.params[run_view.TIMING]
    assert stored["total_usd"] == pytest.approx(0.25)
    assert stored["by_role"] == {
        "writer": 0.0,
        "web_check": 0.05,
        "subjects": 0.0,
        "judges": 0.2,
    }
    assert stored["usd_calls"] == pytest.approx(0.26)
    assert stored["usd"] == pytest.approx(0.5)
    assert timing["total_s"] == pytest.approx(took, abs=0.01)

    report = client.get(f"/console/report/runs/{JOB}", headers=auth).json()
    assert report["method"]["cost"]["by_role"]["judges"] == 0.2
    assert report["method"]["cost"]["total_usd"] == pytest.approx(0.25)
    assert report["run"]["started_at"] is not None
    assert report["run"]["finished_at"] is not None
    assert report["run"]["duration_s"] == pytest.approx(took, abs=0.01)
    listed = client.get("/console/report/runs", headers=auth).json()["items"]
    assert [item["duration_s"] for item in listed] == [report["run"]["duration_s"]]
