"""Run cost: per-call usage.cost, the job meter across threads, the key's spend."""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import httpx
import pytest

from syft_benchmark.config import Settings
from syft_benchmark.llm import chat, cost
from syft_benchmark.llm.openrouter import openrouter_spend

ROUTER = "https://openrouter.ai/api/v1"


def _reply(content: str, price: float | None, finish: str = "stop") -> dict[str, Any]:
    usage: dict[str, Any] = {"completion_tokens": 7}
    if price is not None:
        usage["cost"] = price
    return {
        "choices": [{"message": {"content": content}, "finish_reason": finish}],
        "usage": usage,
    }


def _post(*payloads: dict[str, Any]) -> Any:
    replies = list(payloads)
    lock = threading.Lock()

    def post(url: str, **_kwargs: Any) -> httpx.Response:
        with lock:
            payload = replies.pop(0) if len(replies) > 1 else replies[0]
        return httpx.Response(200, json=payload, request=httpx.Request("POST", url))

    return post


def _local() -> Settings:
    return Settings(ollama_url="http://localhost:11434")  # type: ignore[call-arg]


def _router(**extra: Any) -> Settings:
    return Settings(  # type: ignore[call-arg]
        ollama_url=ROUTER,
        llm_api_key="sk-shared",
        allow_external_models=True,
        external_hosts=["openrouter.ai"],
        generator_model="openai/gpt-5-mini",
        **extra,
    )


def test_cost_usd_sums_every_priced_attempt(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        httpx, "post", _post(_reply("", 0.001, "length"), _reply("ok", 0.002))
    )
    with cost.cost_meter() as meter:
        _, usage = chat("s", "u", max_tokens=10, settings=_local())
    assert usage["cost_usd"] == pytest.approx(0.003)
    assert meter.total_usd == pytest.approx(0.003)
    assert meter.priced_calls == 2


def test_cost_usd_is_none_when_not_priced(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(httpx, "post", _post(_reply("ok", None)))
    with cost.cost_meter() as meter:
        _, usage = chat("s", "u", settings=_local())
    assert usage["cost_usd"] is None
    assert meter.total_usd == 0.0
    assert meter.unpriced_calls == 1


def test_no_meter_no_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(httpx, "post", _post(_reply("ok", 0.5)))
    assert cost.current() is None
    _, usage = chat("s", "u", settings=_local())
    assert usage["cost_usd"] == 0.5


def test_meter_reaches_plain_pool_workers_when_one_is_open(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(httpx, "post", _post(_reply("ok", 0.25)))
    with cost.cost_meter(job_id=7) as meter:
        assert cost.meter_for(7) is meter
        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(lambda _: chat("s", "u", settings=_local()), range(40)))
    assert meter.total_usd == pytest.approx(10.0)
    assert meter.priced_calls == 40
    assert cost.meter_for(7) is None


def test_pool_kwargs_and_bind_keep_two_meters_apart() -> None:
    with cost.cost_meter(job_id="a") as first:
        with ThreadPoolExecutor(max_workers=4, **cost.pool_kwargs()) as pool:
            list(pool.map(lambda _: cost.charge(1.0), range(10)))
        bound = cost.bind(lambda: cost.charge(0.5))
        with cost.cost_meter(job_id="b") as second:
            # Two meters open: a worker without context charges nowhere.
            with ThreadPoolExecutor(max_workers=2) as pool:
                list(pool.map(lambda _: cost.charge(100.0), range(4)))
            with ThreadPoolExecutor(max_workers=4, **cost.pool_kwargs()) as pool:
                list(pool.map(lambda _: cost.charge(2.0), range(5)))
            worker = threading.Thread(target=bound)
            worker.start()
            worker.join()
            cost.charge(3.0)
        assert second.total_usd == pytest.approx(13.0)
    assert first.total_usd == pytest.approx(10.5)


def _key_get(usage: Any, seen: list[str]) -> Any:
    def get(url: str, **kwargs: Any) -> httpx.Response:
        seen.append(f"{url} {kwargs['headers']['Authorization']}")
        body = {"data": {"label": "x", "limit": 400, "usage": usage, "usage_daily": 0}}
        return httpx.Response(200, json=body, request=httpx.Request("GET", url))

    return get


def test_spend_reads_the_key_record(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[str] = []
    monkeypatch.setattr(httpx, "get", _key_get(117.65, seen))
    assert openrouter_spend(_router()) == pytest.approx(117.65)
    assert seen == ["https://openrouter.ai/api/v1/key Bearer sk-shared"]


def test_spend_sums_distinct_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[str] = []
    monkeypatch.setattr(httpx, "get", _key_get(2.0, seen))
    assert openrouter_spend(_router(judge_key="sk-judge")) == pytest.approx(4.0)
    assert len(seen) == 2


def test_spend_none_when_not_openrouter(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(*_a: Any, **_k: Any) -> None:
        raise AssertionError("no call expected")

    monkeypatch.setattr(httpx, "get", fail)
    assert openrouter_spend(_local()) is None


def test_spend_none_when_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(httpx, "get", _key_get(None, []))
    assert openrouter_spend(_router()) is None

    def refuse(url: str, **_k: Any) -> httpx.Response:
        return httpx.Response(401, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "get", refuse)
    assert openrouter_spend(_router()) is None
