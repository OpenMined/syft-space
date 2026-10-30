"""Web search on a chat call: how it is requested from OpenRouter, how a refused
request steps down, and how an answer's search is read back for the audit."""

from __future__ import annotations

import re
import threading
from typing import Any, NamedTuple

from syft_benchmark.config import Settings
from syft_benchmark.llm import catalog
from syft_benchmark.llm.errors import LLMFatalError
from syft_benchmark.llm.providers import ProviderKind, kind_for_url

# OpenRouter's web search server tool. It replaces the deprecated ``web``
# plugin: https://openrouter.ai/docs/guides/features/server-tools/web-search
WEB_SEARCH_TOOL = "openrouter:web_search"

# The engine whose plugin always searches: OpenRouter runs Exa before the model.
EXA = "plugin"

# The usage keys that say how a call searched, as the audit keeps them.
SEARCH_KEYS = (
    "web_search",
    "web_search_via",
    "web_search_forced",
    "web_search_requests",
    "web_search_retry",
)


class SearchStep(NamedTuple):
    """One way of asking for search: the mechanism and how it is forced.

    ``required`` makes the model call a tool, and search is its only one;
    ``named`` names the tool in tool_choice, which OpenRouter maps to the
    provider's own tool and some refuse. An unforced tool is never offered: the
    model may skip it.
    """

    mechanism: str  # tool or plugin
    forcing: str = ""  # required, named, or "" for the plugin


PLUGIN_STEP = SearchStep("plugin")
# The best first; the plugin is the last step.
_TOOL_STEPS: tuple[SearchStep, ...] = (
    SearchStep("tool", "required"),
    SearchStep("tool", "named"),
    PLUGIN_STEP,
)

# A search call the model wrote as text instead of making it (seen on
# moonshotai/kimi-k2.6): the provider never ran it.
_LEAKED_CALL = re.compile(r"<\|tool_calls?_(?:section_)?begin\|>|<\|tool_call")

# (wire model, engine) -> how many steps its refusals have already cost. Kept
# for the process, so a refused step is paid for once, not on every call.
_STEPPED_DOWN: dict[tuple[str, str], int] = {}
_STEPPED_LOCK = threading.Lock()

# Causes a lesser search step cannot cure, whatever the refusal's wording.
_NOT_SEARCH = ("credit", "quota", "valid model id", "api key")


def supports_web_search(url: str) -> bool:
    """Whether the provider at this address can search the web for a call.

    Only OpenRouter. A local Ollama has no web access, and the other APIs name
    the feature differently.
    """
    return kind_for_url(url) is ProviderKind.OPENROUTER


def web_plugin(engine: str, max_results: int) -> dict[str, Any]:
    """OpenRouter's deprecated ``web`` plugin, for models that take no tools.

    ``engine`` "native" is the provider's own search, anything else Exa;
    ``max_results`` applies to Exa.
    """
    if engine == "native":
        return {"id": "web", "engine": "native"}
    return {"id": "web", "engine": "exa", "max_results": max_results}


def web_search_tool(
    engine: str, max_results: int, max_calls: int = 0
) -> dict[str, Any]:
    """The ``openrouter:web_search`` tool entry for one engine.

    "native" is the provider's own search (OpenRouter falls back to Exa where
    there is none); anything else is Exa. ``max_results`` applies to Exa only.
    ``max_calls`` (zero — none) goes as ``max_uses``, which OpenRouter forwards
    to Anthropic's native search; the request's ``max_tool_calls`` caps the rest.
    """
    if engine == "native":
        parameters: dict[str, Any] = {"engine": "native"}
    else:
        parameters = {"engine": "exa", "max_results": max_results}
    if max_calls:
        parameters["max_uses"] = max_calls
    return {"type": WEB_SEARCH_TOOL, "parameters": parameters}


def search_mechanism(model: str, conf: Settings) -> str:
    """tool or plugin: how this model is given web search.

    The server tool needs tool calling, so a model the catalogue lists without
    ``tools`` gets the plugin. An unknown model gets the tool; a refusal of it
    steps down to the plugin in chat().
    """
    entry = catalog.load(conf).get(model)
    return "plugin" if entry is not None and "tools" not in entry.supports else "tool"


def engine_for(asked: str, model: str, conf: Settings) -> str:
    """native or plugin; "auto" goes by the catalogue."""
    if asked in ("native", "plugin"):
        return asked
    return "native" if catalog.load(conf).web_search_of(model) == "native" else "plugin"


def search_steps(mechanism: str, wire: str, engine: str) -> list[SearchStep]:
    """The steps left to try, the best first."""
    if mechanism == "plugin":
        return [PLUGIN_STEP]
    with _STEPPED_LOCK:
        skipped = _STEPPED_DOWN.get((wire, engine), 0)
    return list(_TOOL_STEPS[skipped:])


def step_down(wire: str, engine: str, steps: list[SearchStep]) -> None:
    """Remember that this model refused its current step."""
    key = (wire, engine)
    skipped = len(_TOOL_STEPS) - len(steps) + 1
    with _STEPPED_LOCK:
        _STEPPED_DOWN[key] = max(_STEPPED_DOWN.get(key, 0), skipped)


def apply_search(
    body: dict[str, Any], step: SearchStep, engine: str, results: int, calls: int = 0
) -> None:
    """Put one web search step into the request body; ``calls`` caps the
    searches of the tool (zero — the provider's own limit)."""
    for key in ("tools", "tool_choice", "plugins", "max_tool_calls"):
        body.pop(key, None)
    if step.mechanism == "plugin":
        body["plugins"] = [web_plugin(engine, results)]
        return
    body["tools"] = [web_search_tool(engine, results, calls)]
    if calls:
        body["max_tool_calls"] = calls
    if step.forcing == "required":
        body["tool_choice"] = "required"
    elif step.forcing == "named":
        body["tool_choice"] = {"type": WEB_SEARCH_TOOL}


def refuses_search(error: LLMFatalError, named: str, forced: bool) -> bool:
    """A refusal about the search tool itself, which a lesser step may avoid.

    A forced tool_choice can also be refused with a bare 400 that names no
    cause (Alibaba via OpenRouter: "invalid request (400)").
    """
    text = str(error).replace(named, "").lower()
    if any(mark in text for mark in _NOT_SEARCH):
        return False
    return "tool" in text or (forced and error.status == 400)


def citations_of(message: dict[str, Any]) -> list[dict[str, str]]:
    """The ``url_citation`` annotations of an answer, as {url, title}, deduplicated."""
    out: list[dict[str, str]] = []
    seen: set[str] = set()
    for note in message.get("annotations") or []:
        if not isinstance(note, dict) or note.get("type") != "url_citation":
            continue
        cited = note.get("url_citation") or {}
        url = str(cited.get("url") or "").strip()
        if not url or url in seen:
            continue
        seen.add(url)
        out.append({"url": url, "title": str(cited.get("title") or "")})
    return out


def search_requests(usage: dict[str, Any]) -> int | None:
    """How many searches the provider reports for the call; None — not reported."""
    for key in ("server_tool_use_details", "server_tool_use"):
        found = usage.get(key)
        if isinstance(found, dict) and found.get("web_search_requests") is not None:
            try:
                return int(found["web_search_requests"])
            except (TypeError, ValueError):
                return None
    return None


def search_unused(usage: dict[str, Any]) -> bool:
    """Search was offered, and the answer shows no search and cites nothing."""
    return (
        bool(usage.get("web_search"))
        and not usage.get("citations")
        and not usage.get("web_search_requests")
    )


def leaked_call(text: str) -> bool:
    """The answer is a search call written as text, which nobody ran."""
    return bool(_LEAKED_CALL.search(text or ""))


def search_missed(usage: dict[str, Any], message: dict[str, Any]) -> str:
    """Why an answer offered search shows none: "leaked", "unused" or ""."""
    if message.get("tool_calls") or leaked_call(str(message.get("content") or "")):
        return "leaked"
    return "unused" if search_unused(usage) else ""


def unused_reason(call: dict[str, Any], answer: str = "") -> str:
    """One sentence on why a call offered web search shows no search.

    ``call`` is the audit's record of the call (web_search, web_search_via,
    web_search_forced, web_search_retry).
    """
    if leaked_call(answer):
        return "The model wrote its search call as text, so the search never ran."
    via, forced = call.get("web_search_via"), call.get("web_search_forced")
    # Stored calls that offered the tool without forcing it.
    if via == "tool" and not forced:
        return "Search was offered but not forced, and the model chose not to search."
    if via == "plugin" and call.get("web_search") == EXA:
        return "The web search ran but found no source the answer could cite."
    if via == "plugin":
        return "The provider's own search was offered, and the model did not use it."
    return "The provider reported no search for this call, and nothing was cited."


def search_trail(usage: dict[str, Any] | None, answer: str = "") -> dict[str, Any]:
    """How one answer searched: the search keys, its citations, and whether the
    search went unused (with the reason). Empty — search was not offered."""
    usage = usage or {}
    if not usage.get("web_search"):
        return {}
    trail = {key: usage[key] for key in SEARCH_KEYS if key in usage}
    trail["citations"] = list(usage.get("citations") or [])
    trail["web_search_unused"] = search_unused(usage)
    if trail["web_search_unused"]:
        trail["web_search_unused_reason"] = unused_reason(trail, answer)
    return trail
