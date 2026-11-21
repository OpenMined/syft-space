"""A search error the Space reports is a technical failure, not a miss.

The Space answers 200 on a failed dataset search (a dimension mismatch after an
embedding-model change, say) and names the cause in ``search_error``. Read as
"no fragments", it would count as a retrieval miss and an abstention would look
like correct behaviour.
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
import pytest
from test_concurrent_passes import SPACE, _conf, _Stand

import syft_benchmark.runs.endpoint as run_endpoint
import syft_benchmark.runs.execute as execute
import syft_benchmark.runs.parallel as parallel
import syft_benchmark.scheduler as scheduler
from syft_benchmark.config import ContextMode, ContextSource, Settings, SpaceConfig
from syft_benchmark.db.models import Result
from syft_benchmark.llm import Provider
from syft_benchmark.runs import Pool, RunCache
from syft_benchmark.runs.execute import aask_once
from syft_benchmark.runs.judge import ERROR_PREFIX, is_error

from fakes import FakePair

MISMATCH = "ValueError: Collection expecting embedding with dimension of 384, got 1024"

SEARCH_FAILED = {
    "answer": f"{ERROR_PREFIX} the endpoint search failed: {MISMATCH}",
    "documents": [],
    "latency": 0.1,
    "failed": True,
}


def _space_replies(monkeypatch: pytest.MonkeyPatch, body: dict[str, Any]) -> None:
    def post(url: str, **_: Any) -> httpx.Response:
        return httpx.Response(200, json=body, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", post)


def _ask_endpoint() -> dict[str, Any]:
    return run_endpoint.ask_endpoint(
        SpaceConfig(key="docs", url="http://node.local", endpoint="kb"),
        "What port?",
        settings=Settings(),
    )


# --- reading the response -----------------------------------------------------


def test_a_search_error_is_a_failed_call(monkeypatch: pytest.MonkeyPatch) -> None:
    _space_replies(
        monkeypatch,
        {
            "summary": {"message": {"content": "I don't know."}},
            "references": {"documents": [], "provider_info": {}},
            "search_error": MISMATCH,
        },
    )

    outcome = _ask_endpoint()

    assert outcome["failed"] is True
    assert outcome["documents"] == []
    assert is_error(outcome["answer"])
    assert MISMATCH in outcome["answer"]


def test_an_empty_search_without_error_is_not_a_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _space_replies(
        monkeypatch,
        {
            "summary": {"message": {"content": "I don't know."}},
            "references": {"documents": [], "provider_info": {}},
            "search_error": None,
        },
    )

    outcome = _ask_endpoint()

    assert outcome["failed"] is False
    assert outcome["answer"] == "I don't know."


def test_the_gate_retriever_raises_on_a_search_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The archive check / control-question gate: not checked, not "nothing found"."""
    _space_replies(
        monkeypatch,
        {"references": {"documents": []}, "search_error": MISMATCH},
    )
    retrieve = run_endpoint.endpoint_retriever(
        SpaceConfig(key="docs", url="http://node.local", endpoint="kb"), Settings()
    )

    with pytest.raises(run_endpoint.EndpointFailed, match="dimension of 384"):
        retrieve("What port?")


# --- arm C --------------------------------------------------------------------


def test_arm_c_records_a_failed_search_as_a_technical_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model: list[str] = []

    def chat(*_a: Any, **_k: Any) -> Any:
        model.append("asked")
        return "Port 5442.", {}

    monkeypatch.setattr(parallel, "ask_endpoint", lambda *a, **k: dict(SEARCH_FAILED))
    monkeypatch.setattr(parallel, "chat", chat)
    conf = Settings()

    async def go() -> Any:
        pool = Pool(conf)
        try:
            return await aask_once(
                FakePair(),  # type: ignore[arg-type]
                ContextMode.MODEL_WITH_CONTEXT,
                space=SpaceConfig(key="docs", url="http://node.local", endpoint="kb"),
                settings=conf,
                subject=Provider(
                    role="subject", url="http://localhost:11434", api_key="", model="m"
                ),
                source=ContextSource.ENDPOINT_FRAGMENTS,
                pool=pool,
                cache=RunCache(),
            )
        finally:
            pool.close()

    asked = asyncio.run(go())

    assert model == [], "the model was asked without the material"
    assert asked.call_failed and asked.endpoint_failed
    assert is_error(asked.answer) and MISMATCH in asked.answer
    # Neither hit nor miss: out of the retrieval ranks.
    assert asked.retrieval["retrieval_hit"] is None
    assert asked.retrieval["retrieval_rank"] is None


def test_a_failed_search_reaches_the_job_failures_not_the_misses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stand = _Stand(monkeypatch, pairs=3)
    monkeypatch.setattr(parallel, "ask_endpoint", lambda *a, **k: dict(SEARCH_FAILED))
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
    conf = _conf(arms=[ContextMode.MODEL_WITH_CONTEXT], max_consecutive_failures=0)

    out = scheduler.measure(SPACE, conf)

    # No answerer call was made: there was nothing to answer from.
    assert stand.asked("a/m1") == 0
    results = [obj for obj in saved if isinstance(obj, Result)]
    assert len(results) == 3
    for result in results:
        assert result.verdict == "technical"
        assert MISMATCH in result.answer
        assert result.retrieval_hit is None and result.retrieval_rank is None
    (line,) = [f for f in out.failures if "endpoint failed" in f]
    assert "3 questions" in line and MISMATCH in line
    assert ERROR_PREFIX not in line
