"""Web search per role, the evidence it leaves, and the monte_carlo skip.

No database and no model: the request body, the resolution of a role's toggle,
the cache key and the pass plan are all decided by code that can be called
directly.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

import httpx
import pytest

from syft_benchmark.config import (
    ContextMode,
    ContextSource,
    EvalBlock,
    JobPhase,
    Settings,
    SpaceConfig,
    Verdict,
    WebSearchEngine,
)
from syft_benchmark.llm import Provider, catalog, chat, ollama
from syft_benchmark.llm.catalog import Catalog, ModelEntry
from syft_benchmark.llm.ollama import (
    LLMFatalError,
    citations_of,
    search_requests,
    search_unused,
    web_plugin,
    web_search_tool,
)
from syft_benchmark.llm.roles import web_search_for
from syft_benchmark.report import run_questions
from syft_benchmark.runs.execute import Asked, audit_record
from syft_benchmark.runs.judge import Grade
from syft_benchmark.runs.parallel import Pool, RunCache
from syft_benchmark.scheduler import _plan, measure

OPENROUTER = "https://openrouter.ai/api/v1"
NATIVE = "openai/gpt-5"
PLUGIN_ONLY = "meta-llama/llama-4"
NO_TOOLS = "gryphe/mythomax"  # takes no tool calling
COLD = "openai/o9"  # takes no temperature
LOCAL = "gemma3-4b-gpu"
TOOL = "openrouter:web_search"
NAMED = {"type": TOOL}


def _catalog() -> Catalog:
    return Catalog(
        models={
            NATIVE: ModelEntry(
                id=NATIVE,
                name=NATIVE,
                supports=["temperature", "tools"],
                web_search="native",
            ),
            PLUGIN_ONLY: ModelEntry(
                id=PLUGIN_ONLY,
                name=PLUGIN_ONLY,
                supports=["temperature", "tools"],
                web_search="plugin",
            ),
            NO_TOOLS: ModelEntry(
                id=NO_TOOLS,
                name=NO_TOOLS,
                supports=["temperature"],
                web_search="native",
            ),
            COLD: ModelEntry(id=COLD, name=COLD, supports=[], web_search="plugin"),
            LOCAL: ModelEntry(id=LOCAL, name=LOCAL, local=True, web_search="none"),
        }
    )


@pytest.fixture(autouse=True)
def known_models(monkeypatch: pytest.MonkeyPatch) -> None:
    shipped = _catalog()
    monkeypatch.setattr(catalog, "load", lambda settings=None: shipped)
    monkeypatch.setattr(ollama, "_STEPPED_DOWN", {})


def _external(**overrides: Any) -> Settings:
    body: dict[str, Any] = {
        "ollama_url": OPENROUTER,
        "llm_api_key": "sk-or-test",
        "allow_external_models": True,
        "external_hosts": ["openrouter.ai"],
    }
    body.update(overrides)
    return Settings(**body)


class _Recorder:
    """Replies with one answer and keeps every request body."""

    def __init__(self, message: dict[str, Any] | None = None) -> None:
        self.bodies: list[dict[str, Any]] = []
        self.message = message or {"content": "Paris"}

    def __call__(self, url: str, **kwargs: Any) -> httpx.Response:
        self.bodies.append(kwargs["json"])
        payload = {"choices": [{"message": self.message, "finish_reason": "stop"}]}
        return httpx.Response(200, json=payload, request=httpx.Request("POST", url))


# --- the request body ------------------------------------------------------


def test_the_plugin_shape_per_engine() -> None:
    assert web_plugin("native", 5) == {"id": "web", "engine": "native"}
    assert web_plugin("plugin", 7) == {"id": "web", "engine": "exa", "max_results": 7}


def test_the_tool_shape_per_engine() -> None:
    assert web_search_tool("native", 5) == {
        "type": TOOL,
        "parameters": {"engine": "native"},
    }
    assert web_search_tool("plugin", 7) == {
        "type": TOOL,
        "parameters": {"engine": "exa", "max_results": 7},
    }


@pytest.mark.parametrize(
    ("engine", "model", "parameters", "used"),
    [
        ("native", NATIVE, {"engine": "native"}, "native"),
        ("plugin", NATIVE, {"engine": "exa", "max_results": 5}, "plugin"),
        ("auto", NATIVE, {"engine": "native"}, "native"),
        ("auto", PLUGIN_ONLY, {"engine": "exa", "max_results": 5}, "plugin"),
        # Newer than the catalogue: the tool, and plain Exa.
        ("auto", "vendor/new-model", {"engine": "exa", "max_results": 5}, "plugin"),
    ],
)
def test_the_body_carries_the_forced_tool_for_the_engine(
    monkeypatch: pytest.MonkeyPatch,
    engine: str,
    model: str,
    parameters: dict[str, Any],
    used: str,
) -> None:
    provider = _Recorder()
    monkeypatch.setattr(httpx, "post", provider)

    _answer, usage = chat(
        "s",
        "u",
        model=model,
        settings=_external(),
        web_search=True,
        web_search_engine=engine,
    )

    body = provider.bodies[0]
    assert body["tools"] == [{"type": TOOL, "parameters": parameters}]
    assert body["tool_choice"] == "required"
    assert "plugins" not in body
    assert usage["web_search"] == used
    assert usage["web_search_via"] == "tool"
    assert usage["web_search_forced"] == "required"


@pytest.mark.parametrize(
    ("engine", "plugin", "used"),
    [
        ("auto", {"id": "web", "engine": "native"}, "native"),
        ("plugin", {"id": "web", "engine": "exa", "max_results": 5}, "plugin"),
    ],
)
def test_a_model_without_tool_calling_gets_the_plugin(
    monkeypatch: pytest.MonkeyPatch, engine: str, plugin: dict[str, Any], used: str
) -> None:
    provider = _Recorder()
    monkeypatch.setattr(httpx, "post", provider)

    _answer, usage = chat(
        "s",
        "u",
        model=NO_TOOLS,
        settings=_external(),
        web_search=True,
        web_search_engine=engine,
    )

    body = provider.bodies[0]
    assert body["plugins"] == [plugin]
    assert "tools" not in body and "tool_choice" not in body
    assert usage["web_search"] == used
    assert usage["web_search_via"] == "plugin"
    assert usage["web_search_forced"] is False


class _Refuser:
    """Refuses the first ``refusals`` requests with one error, then answers."""

    def __init__(self, refusals: int, message: str, status: int = 200) -> None:
        self.bodies: list[dict[str, Any]] = []
        self.refusals = refusals
        self.message = message
        self.status = status

    def __call__(self, url: str, **kwargs: Any) -> httpx.Response:
        self.bodies.append(dict(kwargs["json"]))
        request = httpx.Request("POST", url)
        if len(self.bodies) <= self.refusals:
            error = {"error": {"code": 400, "message": self.message}}
            return httpx.Response(self.status, json=error, request=request)
        message = {"content": "Paris"}
        payload = {"choices": [{"message": message, "finish_reason": "stop"}]}
        return httpx.Response(200, json=payload, request=request)


def _search(model: str = NATIVE) -> tuple[str, dict[str, Any]]:
    return chat("s", "u", model=model, settings=_external(), web_search=True)


def test_a_refused_forcing_steps_down_once_and_is_remembered(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    refusal = 'Server tool "openrouter:web_search" failed: invalid request (400)'
    provider = _Refuser(1, refusal)
    monkeypatch.setattr(httpx, "post", provider)

    _answer, first = _search()
    _answer, second = _search()

    required, named, again = provider.bodies
    assert required["tool_choice"] == "required"
    assert named["tool_choice"] == NAMED and named["tools"][0]["type"] == TOOL
    # Remembered: the next call does not pay for the refused step again.
    assert again["tool_choice"] == NAMED
    assert first["web_search_forced"] == second["web_search_forced"] == "named"
    assert first["web_search_via"] == second["web_search_via"] == "tool"


def test_both_forcings_refused_leave_the_tool_unforced(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The refusal a named search got on openai/gpt-4.1-nano.
    refusal = "Tool 'web_search_preview' is not supported with gpt-4.1-nano"
    provider = _Refuser(2, refusal)
    monkeypatch.setattr(httpx, "post", provider)

    _answer, usage = _search()

    assert [b.get("tool_choice") for b in provider.bodies] == ["required", NAMED, None]
    assert usage["web_search_forced"] is False
    assert usage["web_search_via"] == "tool"


def test_a_model_refusing_tools_steps_down_to_the_plugin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = _Refuser(3, "No endpoints found that support tool use", status=404)
    monkeypatch.setattr(httpx, "post", provider)

    _answer, usage = _search()

    assert [("tools" in b, "plugins" in b) for b in provider.bodies] == [
        (True, False),
        (True, False),
        (True, False),
        (False, True),
    ]
    assert usage["web_search_via"] == "plugin"
    assert usage["web_search"] == "native"


def test_a_refusal_unrelated_to_search_is_not_stepped_around(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = _Refuser(3, "Insufficient credits", status=402)
    monkeypatch.setattr(httpx, "post", provider)

    with pytest.raises(LLMFatalError):
        _search()

    assert len(provider.bodies) == 1


def test_the_plugin_has_nothing_to_step_down_to(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = _Refuser(3, "web plugin: tool failure", status=400)
    monkeypatch.setattr(httpx, "post", provider)

    with pytest.raises(LLMFatalError):
        _search(NO_TOOLS)

    assert len(provider.bodies) == 1


def test_max_results_comes_from_the_call_or_the_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = _Recorder()
    monkeypatch.setattr(httpx, "post", provider)
    conf = _external(web_search_max_results=9)

    chat(
        "s",
        "u",
        model=NATIVE,
        settings=conf,
        web_search=True,
        web_search_engine="plugin",
    )
    chat(
        "s",
        "u",
        model=NATIVE,
        settings=conf,
        web_search=True,
        web_search_engine="plugin",
        max_results=2,
    )

    found = [b["tools"][0]["parameters"]["max_results"] for b in provider.bodies]
    assert found == [9, 2]


def test_no_search_no_tool(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = _Recorder()
    monkeypatch.setattr(httpx, "post", provider)

    _answer, usage = chat("s", "u", model=NATIVE, settings=_external())

    body = provider.bodies[0]
    assert "plugins" not in body and "tools" not in body and "tool_choice" not in body
    assert usage["web_search"] is False
    assert usage["citations"] == []
    assert "web_search_via" not in usage


def test_a_local_model_never_gets_a_plugin(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = _Recorder()
    monkeypatch.setattr(httpx, "post", provider)
    conf = Settings(ollama_url="http://localhost:11434")  # type: ignore[call-arg]

    _answer, usage = chat("s", "u", model=LOCAL, settings=conf, web_search=True)

    assert "plugins" not in provider.bodies[0]
    assert "tools" not in provider.bodies[0]
    assert usage["web_search"] is False


# --- citations -------------------------------------------------------------


def test_citations_are_read_from_url_citation_annotations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cited = {"url": "https://a.example/x", "title": "A", "content": "..."}
    message = {
        "content": "Paris",
        "annotations": [
            {"type": "url_citation", "url_citation": cited},
            {"type": "url_citation", "url_citation": dict(cited)},  # repeated
            {"type": "url_citation", "url_citation": {"url": "https://b.example"}},
            {"type": "file", "file": {"name": "x"}},
            {"type": "url_citation", "url_citation": {"title": "no url"}},
        ],
    }
    monkeypatch.setattr(httpx, "post", _Recorder(message))

    _answer, usage = chat("s", "u", model=NATIVE, settings=_external(), web_search=True)

    assert usage["citations"] == [
        {"url": "https://a.example/x", "title": "A"},
        {"url": "https://b.example", "title": ""},
    ]


def test_no_annotations_no_citations() -> None:
    assert citations_of({"content": "x"}) == []
    assert citations_of({"annotations": None}) == []


def test_the_search_count_comes_from_the_usage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def counted(url: str, **kwargs: Any) -> httpx.Response:
        payload = {
            "choices": [{"message": {"content": "Paris"}, "finish_reason": "stop"}],
            "usage": {"server_tool_use_details": {"web_search_requests": 2}},
        }
        return httpx.Response(200, json=payload, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", counted)

    _answer, usage = _search()

    assert usage["web_search_requests"] == 2
    # The guide's spelling of the same count.
    assert search_requests({"server_tool_use": {"web_search_requests": 1}}) == 1
    assert search_requests({}) is None


def test_unused_search_means_no_search_and_no_citation() -> None:
    cited = [{"url": "https://a.example", "title": "A"}]
    silent = {"web_search": "native", "citations": []}

    assert search_unused(silent) is True
    assert search_unused({**silent, "web_search_requests": 0}) is True
    assert search_unused({**silent, "web_search_requests": 1}) is False
    assert search_unused({"web_search": "plugin", "citations": cited}) is False
    assert search_unused({"web_search": False, "citations": []}) is False


# --- the role's toggle -----------------------------------------------------


def test_defaults_search_only_on_their_own() -> None:
    conf = _external()

    assert web_search_for(conf, "closed_book", NATIVE) == (True, "native")
    assert web_search_for(conf, "with_context", NATIVE) == (False, "")
    assert web_search_for(conf, "generator", NATIVE) == (False, "")
    assert web_search_for(conf, "judge", NATIVE) == (False, "")
    # The web check always searches.
    assert web_search_for(conf, "filter", PLUGIN_ONLY) == (True, "plugin")


def test_each_role_follows_its_toggle() -> None:
    conf = _external(
        web_search_closed_book=False,
        web_search_with_context=True,
        web_search_generator=True,
        web_search_judge=True,
    )

    assert web_search_for(conf, "closed_book", NATIVE) == (False, "")
    assert web_search_for(conf, "with_context", NATIVE) == (True, "native")
    assert web_search_for(conf, "generator", PLUGIN_ONLY) == (True, "plugin")
    assert web_search_for(conf, "judge", NATIVE) == (True, "native")


def test_the_engine_setting_against_the_capability() -> None:
    plugin = _external(web_search_engine=WebSearchEngine.PLUGIN)
    native = _external(web_search_engine=WebSearchEngine.NATIVE)

    assert web_search_for(plugin, "closed_book", NATIVE) == (True, "plugin")
    # Native asked of a model without it: the plugin, so it still searches.
    assert web_search_for(native, "closed_book", PLUGIN_ONLY) == (True, "plugin")
    assert web_search_for(native, "closed_book", NATIVE) == (True, "native")
    # A local model has no search at all.
    assert web_search_for(native, "closed_book", LOCAL) == (False, "")


def test_an_unknown_role_is_an_error() -> None:
    with pytest.raises(KeyError):
        web_search_for(_external(), "endpoint", NATIVE)


# --- the cache key ---------------------------------------------------------


def test_search_and_its_engine_are_part_of_the_cache_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[bool, str]] = []

    def fake_chat(*args: Any, **kwargs: Any) -> tuple[str, dict[str, Any]]:
        calls.append((kwargs["web_search"], kwargs["web_search_engine"]))
        return "Paris", {}

    monkeypatch.setattr("syft_benchmark.runs.parallel.chat", fake_chat)
    conf = _external()
    subject = Provider(role="subject", url=OPENROUTER, api_key="k", model=NATIVE)
    cache = RunCache(enabled=True)

    async def go() -> list[dict[str, Any]]:
        pool = Pool(conf)
        try:
            out = []
            for searching, engine in [
                (False, "auto"),
                (True, "native"),
                (True, "plugin"),
                (True, "native"),
                (False, "native"),
            ]:
                _answer, usage = await cache.answer(
                    subject,
                    "s",
                    "q",
                    pool=pool,
                    settings=conf,
                    web_search=searching,
                    web_search_engine=engine,
                )
                out.append(usage)
            return out
        finally:
            pool.close()

    usages = asyncio.run(go())

    assert calls == [(False, "auto"), (True, "native"), (True, "plugin")]
    # The repeats were served from the cache: same search, and search off.
    assert usages[3].get("reused") is True
    assert usages[4].get("reused") is True


def test_the_search_mechanism_is_part_of_the_cache_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    mechanisms = iter(["tool", "plugin", "plugin"])

    def fake_chat(*args: Any, **kwargs: Any) -> tuple[str, dict[str, Any]]:
        calls.append(kwargs["web_search_engine"])
        return "Paris", {}

    monkeypatch.setattr("syft_benchmark.runs.parallel.chat", fake_chat)
    monkeypatch.setattr(
        "syft_benchmark.runs.parallel.search_mechanism",
        lambda model, conf: next(mechanisms),
    )
    conf = _external()
    subject = Provider(role="subject", url=OPENROUTER, api_key="k", model=NATIVE)
    cache = RunCache(enabled=True)

    async def go() -> list[dict[str, Any]]:
        pool = Pool(conf)
        try:
            out = []
            for _ in range(3):
                _answer, usage = await cache.answer(
                    subject,
                    "s",
                    "q",
                    pool=pool,
                    settings=conf,
                    web_search=True,
                    web_search_engine="native",
                )
                out.append(usage)
            return out
        finally:
            pool.close()

    usages = asyncio.run(go())

    assert calls == ["native", "native"]
    assert usages[2].get("reused") is True


# --- the audit -------------------------------------------------------------


def _asked(usage: dict[str, Any]) -> Asked:
    return Asked(
        answer="Paris",
        latency=1.0,
        system="s",
        user="q",
        retrieval={},
        context_source=ContextSource.NONE,
        usage=usage,
    )


def test_the_audit_keeps_citations_and_flags_unused_search() -> None:
    conf = _external()
    grade = Grade(Verdict.CORRECT, "ok")
    cited = [{"url": "https://a.example", "title": "A"}]

    used = audit_record(
        _asked({"web_search": "native", "citations": cited}), grade, conf
    )
    unused = audit_record(
        _asked({"web_search": "plugin", "citations": []}), grade, conf
    )
    off = audit_record(_asked({"web_search": False, "citations": []}), grade, conf)
    searched = audit_record(
        _asked(
            {
                "web_search": "native",
                "web_search_via": "tool",
                "web_search_forced": "required",
                "web_search_requests": 1,
                "citations": [],
            }
        ),
        grade,
        conf,
    )

    assert used["citations"] == cited
    assert used["web_search_unused"] is False
    assert used["call"]["web_search"] == "native"
    assert unused["citations"] == []
    assert unused["web_search_unused"] is True
    assert "citations" not in off and "web_search_unused" not in off
    # It searched and cited nothing: the search was used.
    assert searched["web_search_unused"] is False
    assert searched["call"]["web_search_via"] == "tool"
    assert searched["call"]["web_search_forced"] == "required"
    assert searched["call"]["web_search_requests"] == 1


def test_the_question_detail_passes_the_evidence_on() -> None:
    cited = [{"url": "https://a.example", "title": "A"}]
    result = SimpleNamespace(
        id="r1",
        judge_model="judge",
        answer="Paris",
        verdict="correct",
        reasoning="ok",
        retrieval_hit=None,
        retrieval_rank=None,
        extra={},
        audit={"citations": cited, "web_search_unused": False},
    )
    silent = SimpleNamespace(
        **{**vars(result), "id": "r2", "audit": {"web_search_unused": True}}
    )
    run = SimpleNamespace(
        context_mode=ContextMode.CLOSED_BOOK.value,
        block=EvalBlock.DIRECT.value,
        params={},
    )

    alone = run_questions._arm([(result, run)], "alone", ["judge"])  # type: ignore[list-item]
    flagged = run_questions._arm([(silent, run)], "alone", ["judge"])  # type: ignore[list-item]

    assert alone is not None and flagged is not None
    assert alone["citations"] == cited
    assert alone["web_search_unused"] is False
    assert flagged["citations"] == []
    assert flagged["web_search_unused"] is True


# --- the monte_carlo skip --------------------------------------------------

SPACE = SpaceConfig(key="pytest-space", url="http://localhost:0", endpoint="kb")


class _Watcher:
    def __init__(self) -> None:
        self.planned_passes = 0
        self.started: list[tuple[str, str, str]] = []

    def planned(self, passes: int) -> None:
        self.planned_passes = passes

    def phase(self, phase: JobPhase, message: str = "") -> None: ...

    def pass_started(self, index: int, arm: str, block: str, model: str) -> None:
        self.started.append((arm, block, model))

    def pass_done(self, index: int, label: str) -> None: ...

    def watcher(self, label: str) -> Any:
        return None

    def stop_requested(self) -> bool:
        return False


def _providers(*models: str) -> list[Provider]:
    return [
        Provider(role="subject", url=OPENROUTER, api_key="k", model=m) for m in models
    ]


def test_a_model_without_temperature_gets_no_monte_carlo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asked: list[tuple[str, str, str]] = []
    monkeypatch.setattr(
        "syft_benchmark.scheduler.subject_providers",
        lambda conf: _providers(NATIVE, COLD),
    )
    monkeypatch.setattr(
        "syft_benchmark.scheduler.judge_providers", lambda conf: _providers(LOCAL)
    )
    monkeypatch.setattr("syft_benchmark.scheduler.check_perimeter", lambda conf: None)

    def fake_run_pass(space: Any, mode: Any, **kwargs: Any) -> list[Any]:
        asked.append((mode.value, kwargs["block"].value, kwargs["subject"].model))
        return []

    monkeypatch.setattr("syft_benchmark.scheduler.run_pass", fake_run_pass)
    conf = Settings(
        arms=[ContextMode.CLOSED_BOOK, ContextMode.MODEL_WITH_CONTEXT],
        blocks=[EvalBlock.DIRECT, EvalBlock.MONTE_CARLO],
        generate_in_cycle=False,
    )
    watcher = _Watcher()

    done = measure(SPACE, conf, observer=watcher)

    assert (ContextMode.CLOSED_BOOK.value, "monte_carlo", COLD) not in asked
    assert sum(1 for _arm, block, _m in asked if block == "monte_carlo") == 2
    assert len(asked) == 6
    # The plan counts only the passes that run, so the bar ends at its total.
    assert watcher.planned_passes == len(watcher.started) == done.passes == 6
    assert done.failures == []
    assert done.notes == [f"{COLD}: no temperature, Monte Carlo skipped"]


def test_the_plan_does_not_count_a_skipped_block() -> None:
    conf = Settings(
        arms=[ContextMode.CLOSED_BOOK],
        blocks=[EvalBlock.DIRECT, EvalBlock.DENIAL_LOOP, EvalBlock.MONTE_CARLO],
    )

    assert _plan(conf, _providers(NATIVE, COLD)) == 5
    assert _plan(conf, _providers(NATIVE)) == 3


# --- the settings ------------------------------------------------------------


def test_the_form_describes_the_web_search_fields() -> None:
    from syft_benchmark.control.formfields import describe
    from syft_benchmark.control.schemas import Instrument

    fields = {f["name"]: f for f in describe(Instrument)}

    assert fields["web_search_engine"]["choices"] == ["auto", "native", "plugin"]
    assert fields["web_search_engine"]["group"] == "arms"
    assert fields["web_search_closed_book"]["type"] == "boolean"
    assert fields["web_search_generator"]["group"] == "dataset"
    assert fields["web_search_judge"]["group"] == "judging"
    assert (
        fields["web_search_max_results"]["minimum"],
        fields["web_search_max_results"]["maximum"],
    ) == (1, 20)
    assert fields["filter_judge_model"]["catalog"] == "models"
    assert fields["filter_judge_model"]["group"] == "filter"


def test_an_instrument_layer_sets_the_web_search_fields() -> None:
    from syft_benchmark.control.compose import merge
    from syft_benchmark.control.schemas import Instrument

    layer = Instrument(
        web_search_engine=WebSearchEngine.PLUGIN,
        web_search_with_context=True,
        web_search_max_results=3,
        filter_judge_model="anthropic/claude-opus-5",
    )
    merged = merge(Settings(), layer)

    assert merged.web_search_engine is WebSearchEngine.PLUGIN
    assert merged.web_search_with_context is True
    assert merged.web_search_closed_book is True
    assert merged.web_search_max_results == 3
    assert merged.filter_judge_model == "anthropic/claude-opus-5"
    with pytest.raises(ValueError):
        Instrument(web_search_max_results=21)
    with pytest.raises(ValueError):
        Instrument(filter_judge_model="a, b")


def test_defaults_hand_out_the_web_search_fields() -> None:
    from syft_benchmark.control.app import _effective_defaults

    instrument = _effective_defaults(Settings()).get("instrument")
    shown = instrument.model_dump(mode="json")  # type: ignore[union-attr]

    assert shown["web_search_engine"] == "auto"
    assert shown["web_search_closed_book"] is True
    assert shown["web_search_with_context"] is False
    assert shown["web_search_generator"] is False
    assert shown["web_search_judge"] is False
    assert shown["web_search_max_results"] == 5
    assert shown["filter_judge_model"] is None


@pytest.mark.parametrize(("toggle", "engine"), [(False, None), (True, "native")])
def test_the_control_gate_follows_the_judge_toggle(
    monkeypatch: pytest.MonkeyPatch, toggle: bool, engine: str | None
) -> None:
    from syft_benchmark.generation.control import gate_unanswerable

    provider = _Recorder({"content": '{"answered": false}'})
    monkeypatch.setattr(httpx, "post", provider)
    judge = Provider(role="judge", url=OPENROUTER, api_key="k", model=NATIVE)

    gate_unanswerable(
        "q",
        lambda question: ["a fragment"],
        settings=_external(web_search_judge=toggle),
        judge=judge,
    )

    sent = provider.bodies[0].get("tools")
    assert (sent[0]["parameters"]["engine"] if sent else None) == engine
