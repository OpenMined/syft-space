"""The archive check: an ordinary question must be answerable from the archive.

After grounding and before the web check, live retrieval is searched for a
fragment stating the gold answer. Not found: rejected as ``not_answerable``
and the web check is never asked. A failed check leaves the pair pending;
without a retriever the check is skipped. Control items keep their own gate.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from typing import Any

import pytest
from sqlalchemy import delete, select

from syft_benchmark.config import PairStatus, Settings, SpaceConfig, StatusReason
from syft_benchmark.db import QaPair, session_scope
from syft_benchmark.generation import control, decisions, filter_stage, web_check
from syft_benchmark.generation.generators import GENERATORS
from syft_benchmark.llm import LLMError
from syft_benchmark.runs import endpoint as run_endpoint
from syft_benchmark.runs import judge as run_judge

SPACE = "pytest-archive-check"
JOB = "pytest-archive-check-job"
OPENROUTER = "https://openrouter.ai/api/v1"
FOUND = "Harbourton council restored the lighthouse in March."


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
            session.execute(delete(QaPair).where(QaPair.space == SPACE))

    wipe()
    yield
    wipe()


def _space() -> SpaceConfig:
    return SpaceConfig(key=SPACE, url="http://space:8080", endpoint="ep")


def _settings(**kwargs: Any) -> Settings:
    base: dict[str, Any] = {
        "filter_model": "openai/gpt-5.1",
        "subject_url": OPENROUTER,
        "subject_key": "sk-test",
        "judge_url": OPENROUTER,
        "judge_key": "sk-test",
        "judge_model": "anthropic/claude-opus-5",
        "judge_models": ["anthropic/claude-opus-5"],
        "allow_external_models": True,
        "external_hosts": ["openrouter.ai"],
        "max_consecutive_failures": 0,
        "concurrency": 2,
    }
    return Settings(**{**base, **kwargs})


def _pair(
    pair_id: str,
    question: str,
    answer: str = "Harbourton council",
    generator: str = "qa",
    **meta: Any,
) -> QaPair:
    return QaPair(
        id=pair_id,
        space=SPACE,
        generator=generator,
        task_type=GENERATORS[generator].task_type,
        doc_id="d1",
        question=question,
        answer=answer,
        context=f"Only in the archive. {answer}. {FOUND}",
        meta={"grading": GENERATORS[generator].grading, **meta},
        status=PairStatus.PENDING.value,
        model="gen/model",
        question_hash=uuid.uuid4().hex,
    )


def _add(*rows: QaPair) -> None:
    with session_scope() as session:
        session.add_all(rows)


def _rows() -> dict[str, QaPair]:
    with session_scope() as session:
        rows = list(
            session.execute(select(QaPair).where(QaPair.space == SPACE)).scalars()
        )
        for row in rows:
            session.expunge(row)
    return {row.id: row for row in rows}


ANSWERABLE = "Who restored the lighthouse?"
NONSENSE = "Fill in the blank: he's still worth ______."


def _archive(question: str) -> list[str]:
    """Live retrieval: the lighthouse is in the archive, nothing else is."""
    return [FOUND] if "lighthouse" in question else []


class _Models:
    """The gate's judge, the web check model and its judge, stubbed."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.gate: list[tuple[str, str]] = []
        self.web: list[str] = []
        self.gate_down = False
        monkeypatch.setattr(control, "chat", self.gate_chat)
        monkeypatch.setattr(web_check, "chat", self.web_chat)
        monkeypatch.setattr(
            run_judge, "chat", lambda *_a, **_k: ('{"correct": false}', {})
        )

    def gate_chat(self, system: str, user: str, **_: Any) -> tuple[str, dict[str, Any]]:
        self.gate.append((system, user))
        if self.gate_down:
            raise LLMError("the judge is down")
        found = FOUND in user
        reply = f'{{"answered": {str(found).lower()}, "where": "restored"}}'
        return reply, {"cost_usd": 0.001, "latency_s": 1.0}

    def web_chat(self, _system: str, user: str, **_: Any) -> tuple[str, dict[str, Any]]:
        self.web.append(user)
        return "I don't know", {}


@needs_db
def test_an_answerable_question_goes_on_to_the_web_check(
    clean: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    _add(_pair("ok", ANSWERABLE))
    models = _Models(monkeypatch)

    report = filter_stage.filter_pending(
        _space(), settings=_settings(), retrieve=_archive, job_id=JOB
    )

    row = _rows()["ok"]
    assert row.status == PairStatus.ACTIVE.value
    assert models.web == [ANSWERABLE]
    system, user = models.gate[0]
    assert system == control._ANSWERABLE_SYSTEM
    assert "Expected answer:\nHarbourton council" in user
    assert row.meta["gate"].startswith("answer found in the archive")
    assert row.meta["gate_checked"] is True
    entry = decisions.of_job(row.meta, JOB)
    assert entry is not None and entry["stage"] == decisions.WEB_CHECK
    assert entry["gate"]["user"] == user
    assert entry["gate"]["cost_usd"] == 0.001
    assert filter_stage.GATE_CALL not in row.meta
    assert report.active == 1


@needs_db
def test_a_question_the_archive_cannot_answer_never_reaches_the_web_check(
    clean: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    _add(_pair("nonsense", NONSENSE, answer="$40 million"))
    models = _Models(monkeypatch)

    report = filter_stage.filter_pending(
        _space(), settings=_settings(), retrieve=_archive, job_id=JOB
    )

    row = _rows()["nonsense"]
    assert row.status == PairStatus.REJECTED.value
    assert row.status_reason == StatusReason.NOT_ANSWERABLE.value
    assert row.status_note == filter_stage.NOT_ANSWERABLE_NOTE
    assert models.web == []
    # Nothing came back: no judge call either.
    assert models.gate == []
    entry = decisions.of_job(row.meta, JOB)
    assert entry is not None
    assert (entry["stage"], entry["outcome"]) == (decisions.CONTROL, decisions.REMOVED)
    assert entry["reason"] == StatusReason.NOT_ANSWERABLE.value
    assert report.rejected == 1


@needs_db
def test_a_judge_that_finds_no_answer_rejects_the_question(
    clean: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    _add(_pair("off", "Who repainted the lighthouse?", answer="The keeper"))
    models = _Models(monkeypatch)

    filter_stage.filter_pending(
        _space(),
        settings=_settings(),
        retrieve=lambda _q: ["The lighthouse stands on the cliff."],
    )

    row = _rows()["off"]
    assert row.status_reason == StatusReason.NOT_ANSWERABLE.value
    assert len(models.gate) == 1 and models.web == []


@needs_db
@pytest.mark.parametrize("broken", ["retrieval", "judge"])
def test_a_failed_archive_check_leaves_the_pair_pending(
    clean: None, monkeypatch: pytest.MonkeyPatch, broken: str
) -> None:
    _add(_pair("ok", ANSWERABLE))
    models = _Models(monkeypatch)
    models.gate_down = broken == "judge"

    def down(_question: str) -> list[str]:
        raise ConnectionError("the endpoint is rebooting")

    report = filter_stage.filter_pending(
        _space(),
        settings=_settings(),
        retrieve=down if broken == "retrieval" else _archive,
        job_id=JOB,
    )

    row = _rows()["ok"]
    assert row.status == PairStatus.PENDING.value
    assert row.status_note.startswith(filter_stage.ARCHIVE_RETRY)
    assert row.meta["gate_checked"] is False
    assert models.web == []
    entry = decisions.of_job(row.meta, JOB)
    assert entry is not None
    assert (entry["stage"], entry["outcome"]) == (decisions.CONTROL, decisions.FAILED)
    assert report.archive_failed == 1 and report.checked == 0
    assert "archive check failed for 1" in report.line()

    # The next pass checks it again.
    models.gate_down = False
    filter_stage.filter_pending(_space(), settings=_settings(), retrieve=_archive)
    assert _rows()["ok"].status == PairStatus.ACTIVE.value
    assert models.web == [ANSWERABLE]


@needs_db
def test_without_a_retriever_the_archive_check_is_skipped(
    clean: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    _add(_pair("ok", ANSWERABLE), _pair("nonsense", NONSENSE, answer="$40 million"))
    models = _Models(monkeypatch)

    filter_stage.filter_pending(_space(), settings=_settings(), job_id=JOB)

    rows = _rows()
    for row in rows.values():
        assert row.status == PairStatus.ACTIVE.value
        assert row.meta["gate"] == filter_stage.ARCHIVE_UNCHECKED
    assert models.gate == []
    assert sorted(models.web) == sorted([ANSWERABLE, NONSENSE])


@needs_db
def test_control_items_keep_their_own_gate(
    clean: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    _add(
        _pair(
            "missing",
            "What colour is the keeper's car?",
            answer="",
            generator="unanswerable_property",
        )
    )
    models = _Models(monkeypatch)
    # The behaviour judge reads the web model's "I don't know" as a decline.
    monkeypatch.setattr(
        run_judge, "chat", lambda *_a, **_k: ('{"behavior": "declined"}', {})
    )

    filter_stage.filter_pending(_space(), settings=_settings(), retrieve=_archive)

    row = _rows()["missing"]
    assert row.status == PairStatus.ACTIVE.value
    assert row.meta["gate"] == "retrieval returned nothing"
    # No archive check; the trick question goes on to the web check.
    assert all(system != control._ANSWERABLE_SYSTEM for system, _ in models.gate)
    assert models.web == ["What colour is the keeper's car?"]
    assert row.meta["web_check"]["behavior"] == "declined"


# --- what the gate's judge is given -------------------------------------------


def _screen(row: QaPair, retrieve: Any) -> tuple[Any, ...]:
    return filter_stage._screen_pair(
        row, GENERATORS[row.generator], retrieve, _settings(), None
    )


def test_two_truths_one_lie_puts_the_lie_as_the_premise(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prompts: list[str] = []

    def judge(_system: str, user: str, **_: Any) -> tuple[str, dict[str, Any]]:
        prompts.append(user)
        return '{"answered": true, "where": "in March"}', {}

    monkeypatch.setattr(control, "chat", judge)
    truths = ["Harbourton council restored the lighthouse.", "It reopened in March."]
    row = _pair(
        "ttil",
        "One of the following three statements is FALSE.\n  A) ...\n  B) ...",
        answer="B) It reopened in June.",
        generator="two_truths_one_lie",
        claims=truths,
        source_detail="reopened in March",
    )
    row.context = " ".join(truths)

    status, reason, _, meta = _screen(row, lambda _q: [FOUND])

    assert (status, reason) == (PairStatus.ACTIVE, None)
    assert "False premise:\nIt reopened in June." in prompts[0]
    assert "Expected answer:\nreopened in March" in prompts[0]
    assert f"- {truths[0]}" in prompts[0]
    assert meta["gate"].startswith("correction found in the archive")


def test_hop_facts_are_given_to_the_judge(monkeypatch: pytest.MonkeyPatch) -> None:
    prompts: list[str] = []

    def judge(_system: str, user: str, **_: Any) -> tuple[str, dict[str, Any]]:
        prompts.append(user)
        return '{"answered": true}', {}

    monkeypatch.setattr(control, "chat", judge)
    row = _pair("hop", ANSWERABLE, hop_facts=["Harbourton council restored it."])

    status, _, _, _ = _screen(row, _archive)

    assert status is PairStatus.ACTIVE
    assert "- Harbourton council restored it." in prompts[0]


ORDINARY = sorted(key for key, spec in GENERATORS.items() if not spec.is_control)


@pytest.mark.parametrize("kind", ORDINARY)
def test_every_ordinary_kind_goes_through_the_archive_check(
    monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    asked: list[str] = []

    def gate(question: str, *_a: Any, **_k: Any) -> control.Gate:
        asked.append(question)
        return control.Gate(False, "answer not found in the archive (0 chunks)")

    monkeypatch.setattr(filter_stage, "gate_answerable", gate)
    row = _pair(kind, NONSENSE, generator=kind)

    status, reason, note, _ = _screen(row, lambda _q: [])

    assert asked == [NONSENSE]
    assert (status, reason, note) == (
        PairStatus.REJECTED,
        StatusReason.NOT_ANSWERABLE,
        filter_stage.NOT_ANSWERABLE_NOTE,
    )


def test_a_multiple_choice_answer_goes_in_without_its_letter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prompts: list[str] = []

    def judge(_system: str, user: str, **_: Any) -> tuple[str, dict[str, Any]]:
        prompts.append(user)
        return '{"answered": true}', {}

    monkeypatch.setattr(control, "chat", judge)
    row = _pair("mcq", ANSWERABLE, answer="B) Harbourton council", generator="mcq")

    _screen(row, _archive)

    assert "Expected answer:\nHarbourton council\n" in prompts[0]


# --- a failed endpoint is not an empty retrieval ------------------------------

HTTP_502 = {
    "answer": f"{run_judge.ERROR_PREFIX} HTTP 502: Bad Gateway",
    "documents": [],
    "latency": 0.1,
    "failed": True,
}
NOTHING_FOUND = {"answer": "x", "documents": [], "latency": 0.1, "failed": False}


def _endpoint(
    monkeypatch: pytest.MonkeyPatch, outcome: dict[str, Any]
) -> control.Retriever:
    """The real endpoint retriever over a stubbed endpoint call."""
    monkeypatch.setattr(run_endpoint, "ask_endpoint", lambda *_a, **_k: outcome)
    return run_endpoint.endpoint_retriever(_space(), _settings())


def test_the_retriever_raises_on_a_failed_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    retrieve = _endpoint(monkeypatch, HTTP_502)

    with pytest.raises(run_endpoint.EndpointFailed, match="HTTP 502") as err:
        retrieve(ANSWERABLE)
    assert run_judge.ERROR_PREFIX not in str(err.value)


def test_a_failed_endpoint_leaves_an_ordinary_pair_unchecked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    models = _Models(monkeypatch)

    status, reason, note, meta = _screen(
        _pair("ok", ANSWERABLE), _endpoint(monkeypatch, HTTP_502)
    )

    assert (status, reason) == (PairStatus.PENDING, None)
    assert note.startswith(filter_stage.ARCHIVE_RETRY)
    assert "HTTP 502" in note
    assert meta["gate_checked"] is False
    assert models.gate == []


def test_a_failed_endpoint_never_admits_a_control_pair(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    models = _Models(monkeypatch)
    row = _pair(
        "missing", "What colour is the keeper's car?", "", "unanswerable_property"
    )

    status, _, note, meta = _screen(row, _endpoint(monkeypatch, HTTP_502))

    assert status is not PairStatus.ACTIVE
    assert "HTTP 502" in note
    assert meta["gate_checked"] is False
    assert models.gate == []


def test_an_empty_retrieval_keeps_its_verdicts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    models = _Models(monkeypatch)
    retrieve = _endpoint(monkeypatch, NOTHING_FOUND)

    status, reason, _, meta = _screen(_pair("ok", ANSWERABLE), retrieve)
    assert (status, reason) == (PairStatus.REJECTED, StatusReason.NOT_ANSWERABLE)
    assert meta["gate_checked"] is True

    row = _pair(
        "missing", "What colour is the keeper's car?", "", "unanswerable_property"
    )
    status, _, note, meta = _screen(row, retrieve)
    assert status is PairStatus.ACTIVE
    assert note == "retrieval returned nothing"
    assert meta["gate_checked"] is True
    assert models.gate == []
