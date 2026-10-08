"""Judge temperature and reasoning effort, per catalogue capability, and latency_s.

No database and no model: the request body is recorded at httpx.post.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from syft_benchmark.config import JudgeReasoningEffort, Settings, Verdict
from syft_benchmark.control.app import _effective_defaults
from syft_benchmark.control.compose import merge
from syft_benchmark.control.formfields import describe
from syft_benchmark.control.schemas import Instrument
from syft_benchmark.generation import control as control_set
from syft_benchmark.llm import catalog, chat, ollama
from syft_benchmark.llm.catalog import Catalog, ModelEntry
from syft_benchmark.runs import judge as judge_module

OPENROUTER = "https://openrouter.ai/api/v1"
FULL = "google/gemini-3.1-pro-preview"  # temperature and reasoning
COLD = "openai/gpt-5.1"  # reasoning, no temperature
PLAIN = "openai/gpt-4.1"  # temperature, no reasoning
BARE = "x/none"  # neither
UNKNOWN = "newco/model-9"  # not in the catalogue
LOCAL = "gemma3-4b-gpu"


def _catalog() -> Catalog:
    def entry(model: str, supports: list[str], **extra: Any) -> ModelEntry:
        return ModelEntry(id=model, name=model, supports=supports, **extra)

    return Catalog(
        models={
            FULL: entry(FULL, ["reasoning", "temperature"]),
            COLD: entry(COLD, ["reasoning"]),
            PLAIN: entry(PLAIN, ["temperature"]),
            BARE: entry(BARE, []),
            LOCAL: entry(LOCAL, [], local=True),
        }
    )


@pytest.fixture(autouse=True)
def known_models(monkeypatch: pytest.MonkeyPatch) -> None:
    shipped = _catalog()
    monkeypatch.setattr(catalog, "load", lambda settings=None: shipped)
    monkeypatch.setattr(ollama, "_EFFORT_STEPPED", {})
    monkeypatch.setattr(ollama, "_NO_TEMPERATURE", set())


def _external(**overrides: Any) -> Settings:
    body: dict[str, Any] = {
        "ollama_url": OPENROUTER,
        "llm_api_key": "sk-or-test",
        "allow_external_models": True,
        "external_hosts": ["openrouter.ai"],
    }
    body.update(overrides)
    return Settings(**body)


class _Provider:
    """Refuses the first ``refusals`` requests with ``message``, then answers."""

    def __init__(self, refusals: int = 0, message: str = "") -> None:
        self.bodies: list[dict[str, Any]] = []
        self.refusals = refusals
        self.message = message

    def __call__(self, url: str, **kwargs: Any) -> httpx.Response:
        self.bodies.append(dict(kwargs["json"]))
        request = httpx.Request("POST", url)
        if len(self.bodies) <= self.refusals:
            error = {"error": {"code": 400, "message": self.message}}
            return httpx.Response(400, json=error, request=request)
        payload = {
            "choices": [
                {"message": {"content": '{"correct": true}'}, "finish_reason": "stop"}
            ]
        }
        return httpx.Response(200, json=payload, request=request)


def _judge(
    monkeypatch: pytest.MonkeyPatch, model: str, conf: Settings | None = None
) -> tuple[dict[str, Any], dict[str, Any]]:
    provider = _Provider()
    monkeypatch.setattr(httpx, "post", provider)
    _raw, usage = chat(
        "s", "u", model=model, settings=conf or _external(), judging=True
    )
    return provider.bodies[0], usage


# --- latency ---------------------------------------------------------------


def test_every_call_reports_its_latency(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(httpx, "post", _Provider())
    _raw, usage = chat("s", "u", model=PLAIN, settings=_external())
    assert isinstance(usage["latency_s"], float) and usage["latency_s"] >= 0.0


def test_latency_spans_the_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    ticks = [100.0]

    def clock() -> float:
        value = ticks[-1]
        ticks.append(107.5)
        return value

    monkeypatch.setattr(ollama.time, "monotonic", clock)
    monkeypatch.setattr(ollama.time, "sleep", lambda _s: None)
    provider = _Provider()
    calls = {"n": 0}

    def flaky(url: str, **kwargs: Any) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            raise httpx.ConnectError("down")
        return provider(url, **kwargs)

    monkeypatch.setattr(httpx, "post", flaky)
    _raw, usage = chat("s", "u", model=PLAIN, settings=_external())
    assert usage["latency_s"] == 7.5


# --- the request body per capability ------------------------------------------


def test_a_judge_gets_temperature_and_low_effort_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    body, usage = _judge(monkeypatch, FULL)
    assert body["temperature"] == 0.0
    assert body["reasoning"] == {"effort": "low", "exclude": True}
    assert usage["temperature"] == 0.0 and usage["reasoning_effort"] == "low"


def test_no_temperature_for_a_model_that_takes_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    body, usage = _judge(monkeypatch, COLD)
    assert "temperature" not in body
    assert body["reasoning"] == {"effort": "low", "exclude": True}
    assert usage["temperature"] is None


def test_no_reasoning_for_a_model_that_does_not_reason(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    body, usage = _judge(monkeypatch, PLAIN)
    assert body["temperature"] == 0.0 and "reasoning" not in body
    assert usage["reasoning_effort"] is False
    bare, _usage = _judge(monkeypatch, BARE)
    assert "temperature" not in bare and "reasoning" not in bare


def test_an_unknown_model_gets_both(monkeypatch: pytest.MonkeyPatch) -> None:
    body, _usage = _judge(monkeypatch, UNKNOWN)
    assert body["temperature"] == 0.0 and body["reasoning"]["effort"] == "low"


def test_a_local_model_gets_no_reasoning(monkeypatch: pytest.MonkeyPatch) -> None:
    body, _usage = _judge(
        monkeypatch, LOCAL, Settings(ollama_url="http://ollama:11434")
    )
    assert body["temperature"] == 0.0 and "reasoning" not in body


def test_model_defaults_send_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    conf = _external(judge_temperature=None, judge_reasoning_effort="default")
    body, _usage = _judge(monkeypatch, FULL, conf)
    assert "temperature" not in body and "reasoning" not in body


def test_the_settings_carry_to_the_body(monkeypatch: pytest.MonkeyPatch) -> None:
    conf = _external(judge_temperature=0.4, judge_reasoning_effort="none")
    body, _usage = _judge(monkeypatch, FULL, conf)
    assert body["temperature"] == 0.4
    assert body["reasoning"] == {"effort": "none", "exclude": True}


def test_a_tested_model_call_is_untouched(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = _Provider()
    monkeypatch.setattr(httpx, "post", provider)
    _raw, usage = chat("s", "u", model=COLD, settings=_external(), temperature=0.7)
    assert provider.bodies[0]["temperature"] == 0.7
    assert "reasoning" not in provider.bodies[0] and "reasoning_effort" not in usage


# --- refusals step down ------------------------------------------------------


def test_mandatory_reasoning_steps_none_up_to_low_and_remembers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The refusal google/gemini-3.1-pro-preview gives effort "none".
    refusal = "Reasoning is mandatory for this endpoint and cannot be disabled."
    provider = _Provider(refusals=1, message=refusal)
    monkeypatch.setattr(httpx, "post", provider)
    conf = _external(judge_reasoning_effort="none")

    chat("s", "u", model=FULL, settings=conf, judging=True)
    chat("s", "u", model=FULL, settings=conf, judging=True)

    efforts = [b["reasoning"]["effort"] for b in provider.bodies]
    assert efforts == ["none", "low", "low"]


def test_a_refused_effort_is_dropped(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = _Provider(refusals=1, message="reasoning effort 'high' not supported")
    monkeypatch.setattr(httpx, "post", provider)
    conf = _external(judge_reasoning_effort="high")

    _raw, usage = chat("s", "u", model=FULL, settings=conf, judging=True)

    assert "reasoning" not in provider.bodies[1]
    assert usage["reasoning_effort"] is False


def test_a_refused_temperature_is_dropped_and_remembered(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = _Provider(refusals=1, message="temperature is not supported")
    monkeypatch.setattr(httpx, "post", provider)

    chat("s", "u", model=PLAIN, settings=_external(), judging=True)
    chat("s", "u", model=PLAIN, settings=_external(), judging=True)

    assert ["temperature" in b for b in provider.bodies] == [True, False, False]


def test_an_unrelated_refusal_is_not_stepped_around(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = _Provider(refusals=5, message="Insufficient credits")
    monkeypatch.setattr(httpx, "post", provider)
    with pytest.raises(ollama.LLMFatalError):
        chat("s", "u", model=FULL, settings=_external(), judging=True)
    assert len(provider.bodies) == 1


# --- the settings ------------------------------------------------------------


def test_the_defaults() -> None:
    conf = Settings()
    assert conf.judge_temperature == 0.0
    assert conf.judge_reasoning_effort is JudgeReasoningEffort.LOW
    params = conf.measurement_params()
    assert params["judge_temperature"] == 0.0
    assert params["judge_reasoning_effort"] == "low"


def test_model_default_temperature_through_a_layer() -> None:
    assert Settings(judge_temperature="default").judge_temperature is None
    conf = merge(Settings(), Instrument(judge_temperature="default"))
    assert conf.judge_temperature is None
    conf = merge(Settings(), Instrument(judge_temperature=0.3))
    assert conf.judge_temperature == 0.3
    # null on a layer inherits.
    assert merge(Settings(), Instrument()).judge_temperature == 0.0
    with pytest.raises(ValueError):
        Instrument(judge_temperature=3.0)
    with pytest.raises(ValueError):
        Instrument(judge_reasoning_effort="extreme")


def test_the_form_offers_both_under_judging() -> None:
    fields = {f["name"]: f for f in describe(Instrument)}
    temperature = fields["judge_temperature"]
    assert temperature["group"] == "judging" and temperature["type"] == "number"
    assert temperature["special"] == ["default"]
    assert temperature["minimum"] == 0.0 and temperature["maximum"] == 2.0
    effort = fields["judge_reasoning_effort"]
    assert effort["group"] == "judging"
    assert effort["choices"] == ["none", "minimal", "low", "medium", "high", "default"]


def test_defaults_show_the_judge_settings() -> None:
    shown = _effective_defaults(Settings())["instrument"]
    assert shown.judge_temperature == 0.0
    assert shown.judge_reasoning_effort is JudgeReasoningEffort.LOW
    shown = _effective_defaults(Settings(judge_temperature=None))["instrument"]
    assert shown.judge_temperature == "default"


# --- the judge call sites ----------------------------------------------------


def _capture(monkeypatch: pytest.MonkeyPatch, module: Any, raw: str) -> list[Any]:
    seen: list[Any] = []

    def fake_chat(system: str, user: str, **kwargs: Any) -> tuple[str, dict[str, Any]]:
        seen.append((system, kwargs))
        return raw, {}

    monkeypatch.setattr(module, "chat", fake_chat)
    return seen


def test_the_judge_prompt_accepts_a_differently_worded_answer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw = '{"correct": true, "confidence": 0.9, "reasoning": "same in substance"}'
    seen = _capture(monkeypatch, judge_module, raw)

    grade = judge_module.grade(
        "Capital of France?",
        "Paris",
        "The French capital is Paris.",
        settings=Settings(),
    )

    assert grade.verdict is Verdict.CORRECT
    system, kwargs = seen[0]
    assert "right in substance" in system and "worded" in system
    assert kwargs["judging"] is True and "temperature" not in kwargs


def test_every_judge_call_site_is_tuned(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = _capture(monkeypatch, judge_module, '{"covered": [true], "grounded": true}')
    judge_module.grade_key_facts(
        "Paris is the capital.", ["Paris"], settings=Settings()
    )
    judge_module.check_grounded("Paris", ["Paris is the capital."], settings=Settings())
    gate = _capture(monkeypatch, control_set, '{"answered": false}')
    control_set.gate_unanswerable("Q?", lambda _q: ["fragment"], settings=Settings())

    for _system, kwargs in [*seen, *gate]:
        assert kwargs["judging"] is True and "temperature" not in kwargs
