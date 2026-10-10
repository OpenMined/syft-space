"""Parallel generation, streaming checks, backoff and the owner's word.

Generator calls run in parallel across kinds and passages, each written
question is checked while generation goes on, and both share one model limit.
A kind's budget stays exact; a stop leaves unchecked questions pending.
"""

from __future__ import annotations

import dataclasses
import threading
import time
import uuid
from collections.abc import Iterator
from typing import Any

import httpx
import pytest
from sqlalchemy import delete, select

from syft_benchmark.config import PairStatus, Settings, SpaceConfig
from syft_benchmark.db import ProcessedUnit, QaPair, Result, Run, session_scope
from syft_benchmark.generation import filter_stage, pipeline, web_check
from syft_benchmark.generation.generators import GENERATORS
from syft_benchmark.generation.pair import Pair
from syft_benchmark.generation.slots import ModelSlots
from syft_benchmark.llm import LLMError, LLMFatalError, ollama
from syft_benchmark.runs import judge as run_judge
from syft_benchmark.sources import Chunk, Document

SPACE = "pytest-wp3-speed"
OPENROUTER = "https://openrouter.ai/api/v1"
ANSWER = "Harbourton lighthouse"


def _db_ready() -> bool:
    try:
        with session_scope() as session:
            session.execute(delete(QaPair).where(QaPair.space == SPACE))
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
            session.execute(delete(Result).where(Result.space == SPACE))
            session.execute(delete(Run).where(Run.space == SPACE))
            session.execute(delete(QaPair).where(QaPair.space == SPACE))
            session.execute(delete(ProcessedUnit).where(ProcessedUnit.space == SPACE))

    wipe()
    yield
    wipe()


def _space() -> SpaceConfig:
    return SpaceConfig(key=SPACE, url="http://space:8080", endpoint="ep")


def _settings(**kwargs: Any) -> Settings:
    base: dict[str, Any] = {
        "subject_url": OPENROUTER,
        "subject_key": "sk-test",
        "allow_external_models": True,
        "external_hosts": ["openrouter.ai"],
        "document_window_days": 0,
        "pairs_per_chunk": 2,
        "max_consecutive_failures": 5,
    }
    return Settings(**{**base, **kwargs})


def _documents(count: int, chunks: int) -> list[Document]:
    return [
        Document(
            doc_id=f"doc{d}",
            title=f"Doc {d}",
            url="",
            source="",
            file_name=f"doc{d}.md",
            chunks=[
                Chunk(
                    chunk_id=f"doc{d}_{c}",
                    doc_id=f"doc{d}",
                    chunk_index=c,
                    text=f"The council restored the {ANSWER} this spring ({d}/{c}).",
                    file_name=f"doc{d}.md",
                    headings="",
                )
                for c in range(chunks)
            ],
        )
        for d in range(count)
    ]


class _Generation:
    """Stubbed generator calls: a delay each, counted in flight."""

    def __init__(
        self,
        monkeypatch: pytest.MonkeyPatch,
        documents: list[Document],
        *,
        delay: float = 0.0,
        per_unit: Any = 2,
        kinds: tuple[str, ...] = ("qa",),
    ) -> None:
        self.delay = delay
        self.calls = 0
        self.in_flight = 0
        self.peak = 0
        self.ended: list[float] = []
        self._lock = threading.Lock()
        self.per_unit = per_unit

        class _Chroma:
            def __init__(self, *_: Any) -> None: ...

            def collection_id(self, _name: str) -> str:
                return "cid"

        monkeypatch.setattr(pipeline, "ChromaClient", _Chroma)
        monkeypatch.setattr(pipeline, "load_documents", lambda *_: documents)
        monkeypatch.setattr(pipeline, "chat", self.chat)
        for key in kinds:
            spec = dataclasses.replace(GENERATORS[key], clean=self.clean)
            monkeypatch.setitem(GENERATORS, key, spec)

    def chat(self, system: str, user: str, **_: Any) -> tuple[str, dict[str, Any]]:
        with self._lock:
            self.calls += 1
            self.in_flight += 1
            self.peak = max(self.peak, self.in_flight)
        time.sleep(self.delay)
        with self._lock:
            self.in_flight -= 1
            self.ended.append(time.monotonic())
        item = f'{{"unit": "{uuid.uuid4().hex}"}}'
        return (item if "Generate 1." in user else f"[{item}]"), {}

    def clean(self, items: Any, n: int, whole: str) -> tuple[list[Pair], list[str]]:
        unit = items[0]["unit"]
        count = self.per_unit() if callable(self.per_unit) else self.per_unit
        return [
            Pair(question=f"Q{unit}-{i}?", answer=ANSWER, distractors=[], meta={})
            for i in range(count)
        ], []


class _Web:
    """Stubbed web check: the model answers, the judge says which were right."""

    def __init__(
        self,
        monkeypatch: pytest.MonkeyPatch,
        *,
        right: bool = False,
        on_call: Any = None,
    ) -> None:
        self.times: list[float] = []
        self.calls = 0
        self.right = right
        self.on_call = on_call
        self._lock = threading.Lock()
        monkeypatch.setattr(web_check, "chat", self.chat)
        monkeypatch.setattr(run_judge, "chat", self.judge)

    def chat(self, system: str, user: str, **_: Any) -> tuple[str, dict[str, Any]]:
        with self._lock:
            self.calls += 1
            self.times.append(time.monotonic())
        if self.on_call is not None:
            self.on_call()
        return f"An answer to: {user}", {}

    def judge(self, system: str, user: str, **_: Any) -> tuple[str, dict[str, Any]]:
        return f'{{"correct": {"true" if self.right else "false"}}}', {}


def _rows() -> list[QaPair]:
    with session_scope() as session:
        rows = list(
            session.execute(select(QaPair).where(QaPair.space == SPACE)).scalars()
        )
        for row in rows:
            session.expunge(row)
    return rows


# --- the shared limit --------------------------------------------------------


def test_the_limit_holds_and_urgent_waiters_go_first() -> None:
    slots = ModelSlots(2)
    order: list[str] = []
    held = threading.Event()
    release = threading.Event()

    def holder() -> None:
        with slots.hold():
            held.set()
            release.wait(5)

    def waiter(name: str, urgent: bool) -> None:
        with slots.hold(urgent=urgent):
            order.append(name)

    first = [threading.Thread(target=holder) for _ in range(2)]
    for t in first:
        t.start()
    held.wait(5)
    time.sleep(0.05)
    late = threading.Thread(target=waiter, args=("generate", False))
    late.start()
    time.sleep(0.05)
    check = threading.Thread(target=waiter, args=("check", True))
    check.start()
    time.sleep(0.05)
    release.set()
    for t in [*first, late, check]:
        t.join(5)
    assert order[0] == "check"
    assert slots.peak == 2


# --- parallel generation -----------------------------------------------------


@needs_db
def test_the_budget_is_exact_and_nothing_is_written_twice_in_parallel(
    clean: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    yields = iter([3, 1, 0, 2, 3, 3, 1, 2] * 40)
    lock = threading.Lock()

    def per_unit() -> int:
        with lock:
            return next(yields)

    gen = _Generation(
        monkeypatch,
        _documents(6, 5),
        delay=0.02,
        per_unit=per_unit,
        kinds=("qa", "mcq", "multihop_synthesis"),
    )
    conf = _settings(chunks_per_run=4, concurrency=6)

    report = pipeline.generate_for_space(
        _space(), generators=("qa", "mcq", "multihop_synthesis"), settings=conf
    )

    cap = 4 * 2
    assert report.by_generator == {"qa": cap, "mcq": cap, "multihop_synthesis": cap}
    rows = _rows()
    assert len(rows) == 3 * cap
    assert len({row.question_hash for row in rows}) == len(rows)
    assert {g: sum(r.generator == g for r in rows) for g in report.by_generator} == (
        report.by_generator
    )
    assert 1 < gen.peak <= 6


@needs_db
def test_a_build_with_checks_keeps_the_model_limit(
    clean: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    gen = _Generation(monkeypatch, _documents(5, 4), delay=0.03)
    in_flight = {"now": 0, "peak": 0}
    lock = threading.Lock()

    def counted() -> None:
        with lock:
            in_flight["now"] += 1
            in_flight["peak"] = max(in_flight["peak"], in_flight["now"] + gen.in_flight)
        time.sleep(0.03)
        with lock:
            in_flight["now"] -= 1

    _Web(monkeypatch, on_call=counted)
    conf = _settings(chunks_per_run=10, concurrency=3, filter_model="openai/gpt-5.1")

    pipeline.generate_for_space(
        _space(), generators=("qa",), settings=conf, screen=True
    )

    assert in_flight["peak"] <= 3


# --- streaming ---------------------------------------------------------------


@needs_db
def test_a_question_is_checked_before_generation_ends(
    clean: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    gen = _Generation(monkeypatch, _documents(5, 4), delay=0.1)
    web = _Web(monkeypatch)
    said: list[str] = []
    conf = _settings(chunks_per_run=10, concurrency=2, filter_model="openai/gpt-5.1")

    report = pipeline.generate_for_space(
        _space(),
        generators=("qa",),
        settings=conf,
        screen=True,
        on_progress=said.append,
    )

    assert web.times and min(web.times) < max(gen.ended)
    statuses = {row.status for row in _rows()}
    assert statuses == {PairStatus.ACTIVE.value}
    assert report.screened is not None
    assert report.screened.active == report.pairs_made == 20
    # The set is recomputed once, by the filter pass after the build.
    assert report.rotation is None
    assert said[-1] == "written 20 · checked 20 · removed 0"


@needs_db
def test_streamed_checks_are_stamped_with_the_job(
    clean: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    _Generation(monkeypatch, _documents(2, 2))
    _Web(monkeypatch)
    conf = _settings(chunks_per_run=2, concurrency=2, filter_model="openai/gpt-5.1")

    pipeline.generate_for_space(
        _space(), generators=("qa",), settings=conf, screen=True, job="gen-job"
    )

    rows = _rows()
    assert rows and {row.job_id for row in rows} == {"gen-job"}
    for row in rows:
        (entry,) = row.meta["screening"]
        assert (entry["job_id"], entry["stage"], entry["outcome"]) == (
            "gen-job",
            "web_check",
            "kept",
        )
        assert row.meta["web_check"]["job_id"] == "gen-job"


@needs_db
def test_a_stop_mid_stream_leaves_the_unchecked_pending(
    clean: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    _Generation(monkeypatch, _documents(5, 4), delay=0.05)
    stop = threading.Event()
    _Web(monkeypatch, on_call=stop.set)
    conf = _settings(chunks_per_run=10, concurrency=2, filter_model="openai/gpt-5.1")

    report = pipeline.generate_for_space(
        _space(),
        generators=("qa",),
        settings=conf,
        screen=True,
        should_stop=stop.is_set,
    )

    rows = _rows()
    pending = [row for row in rows if row.status == PairStatus.PENDING.value]
    assert pending
    assert any("stopped at the owner's request" in note for note in report.notes)
    assert report.pairs_made < 20

    # The next filter pass checks what was left.
    filter_stage.filter_pending(_space(), settings=conf)
    assert {row.status for row in _rows()} == {PairStatus.ACTIVE.value}


# --- the filter pass ---------------------------------------------------------


def _pair(pair_id: str, generator: str = "qa", **meta: Any) -> QaPair:
    return QaPair(
        id=pair_id,
        space=SPACE,
        generator=generator,
        task_type=GENERATORS[generator].task_type,
        doc_id="d1",
        question=f"Question {pair_id}: which landmark was restored?",
        answer=ANSWER,
        context=f"The council restored the {ANSWER} this spring.",
        meta=meta,
        status=PairStatus.PENDING.value,
        model="test-model",
        question_hash=uuid.uuid4().hex,
    )


def _insert(*pairs: QaPair) -> None:
    with session_scope() as session:
        for pair in pairs:
            session.add(pair)


@needs_db
def test_the_filter_pass_screens_in_parallel(
    clean: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    _insert(*(_pair(f"p{i}") for i in range(12)))
    in_flight = {"now": 0, "peak": 0}
    lock = threading.Lock()

    def slow() -> None:
        with lock:
            in_flight["now"] += 1
            in_flight["peak"] = max(in_flight["peak"], in_flight["now"])
        time.sleep(0.05)
        with lock:
            in_flight["now"] -= 1

    _Web(monkeypatch, on_call=slow)
    report = filter_stage.filter_pending(
        _space(), settings=_settings(filter_model="openai/gpt-5.1", concurrency=4)
    )
    assert report.active == 12
    assert 1 < in_flight["peak"] <= 4


@needs_db
def test_the_gate_keeps_to_the_endpoint_limit(
    clean: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    _insert(*(_pair(f"c{i}", "unanswerable_property") for i in range(8)))
    in_flight = {"now": 0, "peak": 0}
    lock = threading.Lock()

    def retrieve(_question: str) -> list[str]:
        with lock:
            in_flight["now"] += 1
            in_flight["peak"] = max(in_flight["peak"], in_flight["now"])
        time.sleep(0.05)
        with lock:
            in_flight["now"] -= 1
        return []

    report = filter_stage.filter_pending(
        _space(),
        settings=_settings(concurrency=8, endpoint_concurrency=2),
        retrieve=retrieve,
    )
    assert report.active == 8
    assert in_flight["peak"] == 2


# --- the owner's word --------------------------------------------------------


@needs_db
def test_override_status_stamps_the_owner(clean: None) -> None:
    _insert(_pair("o1", note="kept"))
    assert filter_stage.override_status("o1", PairStatus.ACTIVE)
    (row,) = _rows()
    assert row.meta["note"] == "kept"
    assert row.meta["manual_override"]["status"] == "active"
    assert row.meta["manual_override"]["at"]


@needs_db
@pytest.mark.parametrize("priority", ["manual", "filter"])
def test_a_hand_set_pair_and_the_web_check(
    clean: None, monkeypatch: pytest.MonkeyPatch, priority: str
) -> None:
    pair = _pair("h1")
    pair.status = PairStatus.ACTIVE.value
    pair.cohort = "c1"
    _insert(pair)
    filter_stage.override_status("h1", PairStatus.ACTIVE)
    web = _Web(monkeypatch, right=True)
    conf = _settings(filter_model="openai/gpt-5.1", manual_status_priority=priority)

    filter_stage.filter_pending(_space(), settings=conf, recheck_cohort="c1")

    (row,) = _rows()
    if priority == "manual":
        assert web.calls == 0
        assert row.status == PairStatus.ACTIVE.value
        assert web_check.passed_filter(row, conf)
    else:
        assert web.calls == 1
        assert row.status == PairStatus.REJECTED.value
        assert not web_check.passed_filter(row, conf)


# --- passed_filter -----------------------------------------------------------


def test_passed_filter() -> None:
    conf = _settings(filter_model="openai/gpt-5.1")

    def checked(verdict: str, **extra: Any) -> QaPair:
        record = {"model": "openai/gpt-5.1", "verdict": verdict, **extra}
        return _pair("x", web_check=record)

    assert web_check.passed_filter(checked("hallucinate"), conf)
    assert web_check.passed_filter(checked("abstain"), conf)
    assert not web_check.passed_filter(checked("correct"), conf)
    assert not web_check.passed_filter(checked("abstain", error="down"), conf)
    assert not web_check.passed_filter(_pair("x"), conf)
    other = _pair("x", web_check={"model": "other/model", "verdict": "abstain"})
    assert not web_check.passed_filter(other, conf)
    # Control questions are exempt.
    assert web_check.passed_filter(_pair("x", "unanswerable_property"), conf)
    # No web check model: nothing but control passes.
    assert not web_check.passed_filter(checked("abstain"), _settings())
    hand = _pair("x", manual_override={"status": "active", "at": "now"})
    assert not web_check.passed_filter(hand, conf)
    manual = _settings(filter_model="openai/gpt-5.1", manual_status_priority="manual")
    assert web_check.passed_filter(hand, manual)


# --- rate limits -------------------------------------------------------------


class _Replies:
    def __init__(self, *replies: tuple[int, dict[str, Any], dict[str, str]]) -> None:
        self.replies = list(replies)
        self.calls = 0

    def __call__(self, url: str, **_: Any) -> httpx.Response:
        self.calls += 1
        status, body, headers = self.replies[min(self.calls - 1, len(self.replies) - 1)]
        return httpx.Response(
            status, json=body, headers=headers, request=httpx.Request("POST", url)
        )


_OK = (200, {"choices": [{"message": {"content": "hi"}, "finish_reason": "stop"}]}, {})
_LIMITED = (429, {"error": {"message": "rate limited"}}, {"Retry-After": "7"})


def _local() -> Settings:
    return Settings(ollama_url="http://localhost:11434")


def test_a_rate_limit_is_waited_out_with_backoff(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    replies = _Replies(_LIMITED, (503, {"error": "busy"}, {}), _OK)
    waits: list[float] = []
    monkeypatch.setattr(httpx, "post", replies)
    monkeypatch.setattr(ollama.time, "sleep", waits.append)

    answer, usage = ollama.chat("s", "u", retries=0, settings=_local())

    assert answer == "hi"
    assert replies.calls == 3
    assert waits[0] >= 7  # Retry-After honoured
    assert 2 <= waits[1] <= 4  # the second step of the backoff, jittered
    assert usage["busy_retries"] == 2
    assert usage["backoff_seconds"] == pytest.approx(sum(waits), abs=0.1)


def test_rate_limit_retries_are_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    replies = _Replies(_LIMITED)
    monkeypatch.setattr(httpx, "post", replies)
    monkeypatch.setattr(ollama.time, "sleep", lambda _s: None)

    with pytest.raises(LLMError, match="rate limited"):
        ollama.chat("s", "u", settings=_local())
    assert replies.calls == ollama.BUSY_RETRIES + 1


def test_a_refusal_is_not_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    replies = _Replies((402, {"error": {"message": "insufficient credits"}}, {}))
    monkeypatch.setattr(httpx, "post", replies)
    monkeypatch.setattr(ollama.time, "sleep", lambda _s: None)

    with pytest.raises(LLMFatalError):
        ollama.chat("s", "u", settings=_local())
    assert replies.calls == 1


def test_the_backoff_grows_and_stops_at_its_cap() -> None:
    assert 1 <= ollama.backoff_delay(1) <= 2
    assert 8 <= ollama.backoff_delay(4) <= 16
    assert ollama.backoff_delay(20) <= 60
    assert ollama.backoff_delay(1, retry_after=500) == 120
    assert ollama.retry_after_of({"retry-after": "12"}) == 12
    assert ollama.retry_after_of({}) is None


# --- per-kind build stats ------------------------------------------------------


def _kind(report: Any, key: str = "qa") -> dict[str, Any]:
    return report.kinds[key].as_dict()


@needs_db
def test_a_kind_that_spends_its_budget_says_so(
    clean: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    _Generation(monkeypatch, _documents(5, 4), per_unit=3)
    conf = _settings(chunks_per_run=2, concurrency=1)

    report = pipeline.generate_for_space(_space(), generators=("qa",), settings=conf)

    assert _kind(report) == {
        "kind": "qa",
        "unit": "passage",
        "budget": 4,
        "written": 4,
        "units_available": 20,
        "units_read": 2,
        "failed_units": 0,
        "dropped": {pipeline.OVER_BUDGET: 2},
        "stopped": pipeline.BUDGET_REACHED,
        "spacy": None,
        "llm": None,
        "llm_why": None,
    }


@needs_db
def test_a_kind_that_runs_out_of_material_says_so(
    clean: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    _Generation(monkeypatch, _documents(1, 1))
    conf = _settings(chunks_per_run=10, concurrency=1)

    report = pipeline.generate_for_space(_space(), generators=("qa",), settings=conf)

    stats = _kind(report)
    assert (stats["written"], stats["units_available"], stats["units_read"]) == (
        2,
        1,
        1,
    )
    assert stats["stopped"] == pipeline.OUT_OF_MATERIAL


@needs_db
def test_a_failure_streak_and_duplicates_are_counted(
    clean: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    class _Same(_Generation):
        def clean(self, items: Any, n: int, whole: str) -> tuple[list[Pair], list[str]]:
            same = Pair(
                question="The same question?", answer=ANSWER, distractors=[], meta={}
            )
            return [same], ["empty question or answer"]

    _Same(monkeypatch, _documents(1, 3))
    conf = _settings(chunks_per_run=10, concurrency=1)
    report = pipeline.generate_for_space(_space(), generators=("qa",), settings=conf)
    stats = _kind(report)
    assert stats["written"] == 1
    assert stats["dropped"] == {pipeline.DUPLICATE: 2, "empty question or answer": 3}
    assert stats["stopped"] == pipeline.OUT_OF_MATERIAL

    def failing(*_: Any, **__: Any) -> Any:
        raise LLMError("the provider is down")

    monkeypatch.setattr(pipeline, "chat", failing)
    failed = pipeline.generate_for_space(
        _space(),
        generators=("qa",),
        settings=_settings(
            chunks_per_run=10, concurrency=1, max_consecutive_failures=2
        ),
        new_cohort=True,
    )
    stats = _kind(failed)
    assert (stats["failed_units"], stats["units_read"]) == (2, 2)
    assert stats["stopped"] == pipeline.FAILURE_STREAK


@needs_db
def test_a_cancelled_kind_says_so(clean: None, monkeypatch: pytest.MonkeyPatch) -> None:
    _Generation(monkeypatch, _documents(2, 2))
    conf = _settings(chunks_per_run=10, concurrency=1)

    report = pipeline.generate_for_space(
        _space(), generators=("qa",), settings=conf, should_stop=lambda: True
    )

    stats = _kind(report)
    assert stats["units_read"] == 0
    assert stats["stopped"] == pipeline.CANCELLED
