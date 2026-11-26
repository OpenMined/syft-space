"""Found and shown: arm C's cut goes by the chunks that reached the prompt.

Arm C asks for ``retrieval_top_k`` chunks and puts ``context_docs`` of them
into the prompt. A source chunk found past ``context_docs`` was never seen, so
abstaining without it is not a false abstention.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from test_concurrent_passes import SPACE as STAND_SPACE
from test_concurrent_passes import _conf, _Stand

import syft_benchmark.runs.execute as execute
import syft_benchmark.runs.parallel as parallel
import syft_benchmark.scheduler as scheduler
from syft_benchmark.config import ContextMode, ContextSource, EvalBlock, Settings
from syft_benchmark.db import QaPair, Result, Run, session_scope
from syft_benchmark.report import metrics as metrics_mod
from syft_benchmark.report.metrics import summarize
from syft_benchmark.retrieval.arm_c import SHOWN_KEY, Shown, shown_in_prompt, shown_of

SPACE = "pytest-shown"
JUDGE = "judge/one"
_T0 = datetime(2026, 11, 1, 12, 0, tzinfo=UTC)

_FOUND = [{"content": f"chunk {n}"} for n in range(1, 6)]


@pytest.mark.parametrize(
    ("rank", "source", "context_docs", "shown"),
    [
        (2, ContextSource.ENDPOINT_FRAGMENTS, 3, True),
        (4, ContextSource.ENDPOINT_FRAGMENTS, 3, False),
        (4, ContextSource.ENDPOINT_BOTH, 3, False),
        (4, ContextSource.ENDPOINT_ANSWER, 3, True),
        (None, ContextSource.ENDPOINT_FRAGMENTS, 3, False),
    ],
)
def test_shown_in_prompt(
    rank: int | None, source: ContextSource, context_docs: int, shown: bool
) -> None:
    assert (
        shown_in_prompt(rank, _FOUND, source=source, context_docs=context_docs) is shown
    )


def test_an_empty_chunk_is_left_out_of_the_prompt() -> None:
    found = [{"content": "a"}, {"content": "  "}]
    assert not shown_in_prompt(
        2, found, source=ContextSource.ENDPOINT_FRAGMENTS, context_docs=5
    )


def test_shown_of_reads_the_flag_then_the_run() -> None:
    params = {"context_docs": 3, "context_source": "endpoint_fragments"}
    assert shown_of(None, None, {}, params) == Shown(None)
    assert shown_of(False, None, {}, params) == Shown(False)
    assert shown_of(True, 4, {SHOWN_KEY: True}, params) == Shown(True)
    assert shown_of(True, 4, {}, params) == Shown(False)
    assert shown_of(True, 2, {}, params) == Shown(True)
    assert shown_of(True, 4, {}, {}, "endpoint_answer") == Shown(True)
    assert shown_of(True, 4, {}, {}) == Shown(True, assumed=True)


def test_the_run_records_shown_per_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    stand = _Stand(monkeypatch, pairs=1)
    documents = [
        {
            "content": f"chunk {n}",
            "metadata": {"doc_id": "doc-1" if n == 4 else f"other-{n}"},
            "similarity_score": 0.9,
        }
        for n in range(1, 6)
    ]
    monkeypatch.setattr(
        parallel,
        "ask_endpoint",
        lambda *a, **k: {
            "answer": "",
            "documents": documents,
            "latency": 0.0,
            "failed": False,
        },
    )
    saved: list[Any] = []

    class _Session:
        def add(self, obj: Any) -> None:
            saved.append(obj)

    class _Scope:
        def __enter__(self) -> Any:
            return _Session()

        def __exit__(self, *exc: Any) -> None:
            return None

    monkeypatch.setattr(execute, "session_scope", lambda *a, **k: _Scope())
    conf = _conf(arms=[ContextMode.MODEL_WITH_CONTEXT], context_docs=3)

    scheduler.measure(STAND_SPACE, conf)

    assert stand.asked("a/m1") == 1
    (result,) = [obj for obj in saved if isinstance(obj, Result)]
    assert (result.retrieval_hit, result.retrieval_rank) == (True, 4)
    assert result.extra[SHOWN_KEY] is False


def test_grounding_checks_only_the_chunks_in_the_prompt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _Stand(monkeypatch, pairs=1)
    documents = [
        {"content": f"chunk {n}", "metadata": {"doc_id": f"d-{n}"}} for n in range(1, 6)
    ]
    monkeypatch.setattr(
        parallel,
        "ask_endpoint",
        lambda *a, **k: {
            "answer": "",
            "documents": documents,
            "latency": 0.0,
            "failed": False,
        },
    )
    checked: list[list[str]] = []

    def grounded(answer: str, fragments: list[str], **_: Any) -> tuple[bool, str]:
        checked.append(fragments)
        return True, "ok"

    monkeypatch.setattr(execute, "check_grounded", grounded)
    monkeypatch.setattr(execute, "session_scope", lambda *a, **k: _NoScope())
    conf = _conf(arms=[ContextMode.MODEL_WITH_CONTEXT], context_docs=3)

    scheduler.measure(STAND_SPACE, conf)

    assert checked
    assert all(f == ["chunk 1", "chunk 2", "chunk 3"] for f in checked)


class _NoScope:
    def __enter__(self) -> Any:
        return self

    def __exit__(self, *exc: Any) -> None:
        return None

    def add(self, obj: Any) -> None:
        return None


def test_context_docs_defaults_to_retrieval_top_k() -> None:
    fields = Settings.model_fields
    assert fields["context_docs"].default == fields["retrieval_top_k"].default


# --- the report ---------------------------------------------------------------


def _seed() -> None:
    """Four answerable questions in arm C, three runs.

    | question | run           | rank | stored shown | verdict | counts as   |
    | q1       | context_docs 3 | 1   | —            | abstain | false abst. |
    | q2       | context_docs 3 | 4   | —            | abstain | miss        |
    | q3       | context_docs 3 | 2   | False        | correct | miss        |
    | q4       | no params      | 5   | —            | correct | hit, assumed|
    """
    rows = {
        "q1": ("with-cd", 1, {}, "abstain"),
        "q2": ("with-cd", 4, {}, "abstain"),
        "q3": ("with-cd", 2, {SHOWN_KEY: False}, "correct"),
        "q4": ("bare", 5, {}, "correct"),
    }
    with session_scope() as session:
        for run_id, params in (("with-cd", {"context_docs": 3}), ("bare", {})):
            session.add(
                Run(
                    id=f"{SPACE}-{run_id}",
                    space=SPACE,
                    context_mode=ContextMode.MODEL_WITH_CONTEXT.value,
                    context_source=ContextSource.ENDPOINT_FRAGMENTS.value,
                    block=EvalBlock.DIRECT.value,
                    model="a/m1",
                    judge_model=JUDGE,
                    params=params,
                )
            )
        for qa in rows:
            session.add(
                QaPair(
                    id=f"{SPACE}-{qa}",
                    space=SPACE,
                    generator="qa",
                    question=f"question {qa}",
                    answer="a",
                    status="active",
                    model="m",
                    question_hash=f"{SPACE}-h-{qa}",
                )
            )
        session.flush()
        for n, (qa, (run_id, rank, extra, verdict)) in enumerate(rows.items()):
            session.add(
                Result(
                    id=f"{SPACE}-{qa}",
                    run_id=f"{SPACE}-{run_id}",
                    qa_id=f"{SPACE}-{qa}",
                    space=SPACE,
                    endpoint="kb",
                    answer="a",
                    verdict=verdict,
                    retrieval_hit=True,
                    retrieval_rank=rank,
                    extra=extra,
                    model="a/m1",
                    judge_model=JUDGE,
                    created_at=_T0 + timedelta(minutes=n),
                )
            )


@pytest.mark.needs_db
def test_the_cut_goes_by_shown(clean: None, monkeypatch: pytest.MonkeyPatch) -> None:
    _seed()
    conf = Settings.model_construct(judge_models=[JUDGE])
    monkeypatch.setattr(metrics_mod, "get_settings", lambda: conf)

    got = summarize(SPACE, ContextMode.MODEL_WITH_CONTEXT, model="a/m1")

    assert got is not None
    assert (got.retrieval_checked, got.retrieval_hits) == (4, 4)
    assert got.retrieval_shown == 2
    assert got.retrieval_shown_assumed == 1
    assert (got.retrieval_rate, got.retrieval_shown_rate) == (1.0, 0.5)
    # q1 abstained with the chunk in front of it; q2 never saw it.
    assert (got.hit_abstain, got.hit_correct) == (1, 1)
    assert got.false_abstain_rate == 0.5
    # q3 answered without the chunk, q2 abstained.
    assert (got.miss_answered, got.miss_abstain) == (1, 1)
    assert got.blind_answer_rate == 0.5
