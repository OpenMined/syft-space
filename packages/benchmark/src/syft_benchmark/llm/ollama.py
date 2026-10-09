"""A client for the local LLM (Ollama).

Ported from `OMSyft/scripts/qa_llm.py`. Ollama serves an OpenAI-compatible API
on /v1, and it is the same model that serves the Space's endpoints: the dataset
is built by "our own" LLM, and neither a chunk of the corpus nor a single
question goes outwards.

This is also the one place where invariant 2 is enforced: before every call the
address is checked for membership of the perimeter. The check lives in the
client rather than in the callers, because there will be many callers and
forgetting the check once is enough.

A 4B model in 4-bit quantisation regularly wraps its answer in ```json, adds
explanations or breaks off in the middle of an array, so parsing is forgiving:
we pull out the first balanced JSON rather than relying on json.loads over the
whole text.
"""

from __future__ import annotations

import contextlib
import json
import random
import threading
import time
from email.utils import parsedate_to_datetime
from typing import TYPE_CHECKING, Any

import httpx

from syft_benchmark.config import Settings, check_model_host, get_settings
from syft_benchmark.llm import catalog, cost
from syft_benchmark.llm.providers import ProviderKind, kind_for_url

if TYPE_CHECKING:
    from syft_benchmark.llm.roles import Provider


class LLMError(RuntimeError):
    """The LLM did not answer, or answered with unparseable text."""


class LLMFatalError(LLMError):
    """A refusal a retry does not cure: the key, access, the model name, credits.

    Ported from LiveTruth's P2 taxonomy. Without it three different refusals
    were caught by one ``except`` and went into a retry: the run spun its wheels
    and paid for every pointless attempt. On an external provider with a
    900-second timeout a wrong key would have cost forty-five minutes of waiting
    instead of an instant hint about what to check.
    """


class LLMTruncatedError(LLMError):
    """The answer hit the token cap and brought back nothing usable."""


class LLMBusyError(LLMError):
    """A rate limit or an overload: the same call later is likely to pass."""

    def __init__(self, detail: str, retry_after: float | None = None) -> None:
        super().__init__(detail)
        self.retry_after = retry_after


# The codes with nothing to retry: it is the request, the key or the money.
_FATAL_STATUS = frozenset({400, 401, 402, 403, 404, 405, 422})

# Signs of a spent balance in the response body. OpenRouter hands them back
# both with HTTP 200 and with 402 — as text, not as a code.
_FATAL_BODY = (
    "insufficient credits",
    "insufficient_quota",
    "access denied by security policy",
    "no endpoints found",
    "not a valid model id",
)


# Replies that mean "busy, come back later": a rate limit or an overload.
_BUSY_STATUS = frozenset({429, 500, 502, 503, 504, 529})

# How many busy replies one call waits out, apart from ``retries``, and the
# waits: exponential from the base, with jitter, never past the cap. A
# Retry-After from the provider is honoured up to its own cap.
BUSY_RETRIES = 5
_BACKOFF_BASE = 2.0
_BACKOFF_CAP = 60.0
_RETRY_AFTER_CAP = 120.0


def _classify(status: int, detail: str, retry_after: float | None = None) -> LLMError:
    """A provider's refusal — fatal, busy, or worth retrying."""
    lowered = detail.lower()
    if status in _FATAL_STATUS or any(mark in lowered for mark in _FATAL_BODY):
        return LLMFatalError(detail)
    if status in _BUSY_STATUS:
        return LLMBusyError(detail, retry_after)
    return LLMError(detail)


def retry_after_of(headers: httpx.Headers | dict[str, str] | None) -> float | None:
    """The Retry-After header in seconds (a number or an HTTP date); None — absent."""
    if not headers:
        return None
    raw = str(headers.get("retry-after") or headers.get("Retry-After") or "").strip()
    if not raw:
        return None
    try:
        return max(0.0, float(raw))
    except ValueError:
        pass
    try:
        when = parsedate_to_datetime(raw)
    except (TypeError, ValueError):
        return None
    return max(0.0, when.timestamp() - time.time())


def backoff_delay(attempt: int, retry_after: float | None = None) -> float:
    """Seconds to wait before busy retry number ``attempt`` (from 1)."""
    ceiling = min(_BACKOFF_CAP, _BACKOFF_BASE * 2 ** (attempt - 1))
    delay = random.uniform(ceiling / 2, ceiling)  # noqa: S311 - jitter, not crypto
    if retry_after is not None:
        delay = max(delay, min(retry_after, _RETRY_AFTER_CAP))
    return delay


def _headers_for(api_key: str, app_name: str) -> dict[str, str]:
    """Headers for one role's own key."""
    if not api_key:
        return {}
    return {
        "Authorization": f"Bearer {api_key}",
        # OpenRouter shows this in its console; optional, but it lets the
        # benchmark's runs be told apart from the rest of the traffic.
        "X-Title": app_name,
    }


def _headers(conf: Settings) -> dict[str, str]:
    """Headers for the shared key, when no role is given.

    A local Ollama needs no key and is not sent one. An external provider
    (OpenRouter and the like) answers 401 without a key — but it can only be
    reached through an explicitly lifted perimeter ban, see check_model_host.
    """
    return _headers_for(conf.llm_api_key, conf.llm_app_name)


def _api_root(url: str) -> str:
    """Ollama's root without /v1.

    The settings hold the base address; the API lives on /v1.
    """
    return url.rstrip("/").removesuffix("/v1")


def supports_web_search(url: str) -> bool:
    """Whether the provider at this address can search the web for a call.

    Only OpenRouter. A local Ollama has no web access, and the other APIs name
    the feature differently.
    """
    return kind_for_url(url) is ProviderKind.OPENROUTER


# OpenRouter's web search server tool. It replaces the deprecated ``web``
# plugin: https://openrouter.ai/docs/guides/features/server-tools/web-search
WEB_SEARCH_TOOL = "openrouter:web_search"


def web_plugin(engine: str, max_results: int) -> dict[str, Any]:
    """OpenRouter's deprecated ``web`` plugin, for models that take no tools.

    ``engine`` "native" is the provider's own search, anything else Exa;
    ``max_results`` applies to Exa.
    """
    if engine == "native":
        return {"id": "web", "engine": "native"}
    return {"id": "web", "engine": "exa", "max_results": max_results}


def web_search_tool(engine: str, max_results: int) -> dict[str, Any]:
    """The ``openrouter:web_search`` tool entry for one engine.

    "native" is the provider's own search (OpenRouter falls back to Exa where
    there is none); anything else is Exa. ``max_results`` applies to Exa only.
    """
    if engine == "native":
        parameters: dict[str, Any] = {"engine": "native"}
    else:
        parameters = {"engine": "exa", "max_results": max_results}
    return {"type": WEB_SEARCH_TOOL, "parameters": parameters}


def search_mechanism(model: str, conf: Settings) -> str:
    """tool or plugin: how this model is given web search.

    The server tool needs tool calling, so a model the catalogue lists without
    ``tools`` gets the plugin. An unknown model gets the tool; a refusal of it
    steps down to the plugin in chat().
    """
    entry = catalog.load(conf).get(model)
    return "plugin" if entry is not None and "tools" not in entry.supports else "tool"


# One step of web search: (mechanism, forcing). "required" makes the model call
# a tool, and search is its only one; "named" names the tool in tool_choice,
# which OpenRouter maps to the provider's own tool and some refuse; "" leaves
# the choice to the model.
_Step = tuple[str, str]
_TOOL_STEPS: tuple[_Step, ...] = (
    ("tool", "required"),
    ("tool", "named"),
    ("tool", ""),
    ("plugin", ""),
)
_PLUGIN_STEPS: tuple[_Step, ...] = (("plugin", ""),)

# (wire model, engine) -> how many steps its refusals have already cost. Kept
# for the process, so a refused step is paid for once, not on every call.
_STEPPED_DOWN: dict[tuple[str, str], int] = {}
_STEPPED_LOCK = threading.Lock()


def _search_steps(mechanism: str, wire: str, engine: str) -> list[_Step]:
    """The steps left to try, the best first."""
    if mechanism == "plugin":
        return list(_PLUGIN_STEPS)
    with _STEPPED_LOCK:
        skipped = _STEPPED_DOWN.get((wire, engine), 0)
    return list(_TOOL_STEPS[skipped:])


def _step_down(wire: str, engine: str, steps: list[_Step]) -> None:
    """Remember that this model refused its current step."""
    key = (wire, engine)
    skipped = len(_TOOL_STEPS) - len(steps) + 1
    with _STEPPED_LOCK:
        _STEPPED_DOWN[key] = max(_STEPPED_DOWN.get(key, 0), skipped)


def _apply_search(body: dict[str, Any], step: _Step, engine: str, results: int) -> None:
    """Put one web search step into the request body."""
    for key in ("tools", "tool_choice", "plugins"):
        body.pop(key, None)
    mechanism, forcing = step
    if mechanism == "plugin":
        body["plugins"] = [web_plugin(engine, results)]
        return
    body["tools"] = [web_search_tool(engine, results)]
    if forcing == "required":
        body["tool_choice"] = "required"
    elif forcing == "named":
        body["tool_choice"] = {"type": WEB_SEARCH_TOOL}


def _refuses_search(error: LLMFatalError, named: str) -> bool:
    """A refusal about the search tool itself, which a lesser step may avoid."""
    text = str(error).replace(named, "").lower()
    return "tool" in text and "credit" not in text and "quota" not in text


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


def _engine_for(asked: str, model: str, conf: Settings) -> str:
    """native or plugin; "auto" goes by the catalogue."""
    if asked in ("native", "plugin"):
        return asked
    return "native" if catalog.load(conf).web_search_of(model) == "native" else "plugin"


# Judge tuning: https://openrouter.ai/docs/guides/best-practices/reasoning-tokens
# A refused effort steps down: "none" and "minimal" to "low" (some models reason
# by force), any other to the model's own default ("").
_EFFORT_FALLBACK = {"none": "low", "minimal": "low"}
# (wire model, asked effort) -> the effort its refusals left; "" sends none.
_EFFORT_STEPPED: dict[tuple[str, str], str] = {}
# Wire models that refused a temperature.
_NO_TEMPERATURE: set[str] = set()
_TUNING_LOCK = threading.Lock()


def judge_tuning(model: str, base_url: str, conf: Settings) -> dict[str, Any]:
    """The temperature and ``reasoning`` a judge call carries; absent — not sent.

    Temperature goes only to a model the catalogue says takes one (unknown — it
    does). Reasoning goes only to OpenRouter, and only to a model the catalogue
    lists with ``reasoning`` (unknown — sent, a refusal steps it down).
    """
    entry = catalog.load(conf).get(model)
    wire = catalog.load(conf).native(model, kind_for_url(base_url))
    out: dict[str, Any] = {}
    with _TUNING_LOCK:
        no_temperature = wire in _NO_TEMPERATURE
        asked = conf.judge_reasoning_effort.value
        effort = _EFFORT_STEPPED.get((wire, asked), asked)
    if (
        conf.judge_temperature is not None
        and catalog.load(conf).takes_temperature(model)
        and not no_temperature
    ):
        out["temperature"] = conf.judge_temperature
    reasons = entry is None or (not entry.local and "reasoning" in entry.supports)
    if (
        effort not in ("", "default")
        and reasons
        and kind_for_url(base_url) is ProviderKind.OPENROUTER
    ):
        out["reasoning"] = {"effort": effort, "exclude": True}
    return out


def _refuses_tuning(
    error: LLMFatalError, named: str, body: dict[str, Any], wire: str, asked: str
) -> bool:
    """A refusal of the judge's reasoning or temperature: step it down in ``body``."""
    text = str(error).replace(named, "").lower()
    reasoning = body.get("reasoning")
    if isinstance(reasoning, dict) and any(
        word in text for word in ("reasoning", "effort", "thinking")
    ):
        lower = _EFFORT_FALLBACK.get(str(reasoning.get("effort")), "")
        with _TUNING_LOCK:
            _EFFORT_STEPPED[(wire, asked)] = lower
        if lower:
            body["reasoning"] = {**reasoning, "effort": lower}
        else:
            body.pop("reasoning")
        return True
    if "temperature" in body and "temperature" in text:
        with _TUNING_LOCK:
            _NO_TEMPERATURE.add(wire)
        body.pop("temperature")
        return True
    return False


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


def chat(
    system_prompt: str,
    user_prompt: str,
    *,
    model: str | None = None,
    temperature: float | None = None,
    max_tokens: int = 700,
    retries: int = 2,
    settings: Settings | None = None,
    provider: Provider | None = None,
    messages: list[dict[str, str]] | None = None,
    web_search: bool = False,
    web_search_engine: str = "auto",
    max_results: int | None = None,
    judging: bool = False,
    role: str | None = None,
) -> tuple[str, dict[str, Any]]:
    """A single call to the chat endpoint.

    Args:
        system_prompt: The system role
        user_prompt: The request
        model: The model; defaults to the generator from the settings
        temperature: The temperature; defaults to the settings
        max_tokens: The answer cap to start from. An answer cut off at it is
            asked for again with the cap doubled, up to the shared answer
            ceiling: a reasoning model's appetite is not knowable in advance,
            and max_tokens bounds rather than orders
        retries: How many times to retry after a network error or an empty
            answer. Raising the cap is not one of these: a cut-off is not a
            failure to retry but a budget to widen
        settings: Process settings
        provider: The role the call is made on behalf of; None — the shared settings
        messages: A ready-made exchange instead of a system/user pair. denial_loop
            needs it: pressure only means something as a continuation of the same
            dialogue
        web_search: Let the model search the web. Only OpenRouter offers it:
            the ``openrouter:web_search`` tool, forced by tool_choice
            "required", then by naming it, then unforced, then the ``web`` plugin,
            stepping down
            when the provider refuses a step (and straight to the plugin for a
            model without tool calling). Elsewhere the call goes without it and
            usage says ``web_search: False``
        web_search_engine: "native", "plugin" (Exa) or "auto" (native when the
            catalogue says the model has it, else Exa)
        max_results: Results per search for Exa; None — the settings
        judging: A judge call: ``judge_temperature`` and
            ``judge_reasoning_effort`` replace ``temperature``, sent only where
            the catalogue says the model takes them (see judge_tuning); a
            provider's refusal of either steps it down
        role: Who the call is made for, for the job's cost by role
            (``cost.ROLES``); ``cost.acting_as`` overrides it

    Returns:
        The answer text and usage, extended with cost_usd (USD the provider
        charged over all attempts; None — not priced), finish_reason, web_search
        (the engine used, or False), citations ([{url, title}]), latency_s
        (wall seconds of the whole call, retries included) and, when
        searching, web_search_via (tool or plugin), web_search_forced
        ("required", "named" or False) and
        web_search_requests (the provider's count, or None)

    Raises:
        ExternalCallBlocked: the model's address is outside the perimeter
        LLMError: it did not answer, or answered empty
    """
    conf = settings or get_settings()
    # Wall time of the whole call, retries and waits included.
    started = time.monotonic()

    # The role sets the address, the key and the model; without a role it is the
    # shared settings. That way calls from the old code keep working, while new
    # ones can go to their own provider without dragging the settings through
    # half a dozen layers.
    base_url = provider.url if provider is not None else conf.ollama_url
    api_key = provider.api_key if provider is not None else conf.llm_api_key
    chosen = model or (provider.model if provider is not None else conf.generator_model)

    check_model_host(base_url, conf)

    # The settings hold this service's identifier; the provider knows the model
    # by its own name. Translated here, at the one place a name leaves for the
    # wire, rather than in each of the callers.
    wire = catalog.load(conf).native(chosen, kind_for_url(base_url))
    # Both names in a failure, when they differ: that is what tells a wrong
    # identifier from a wrong translation of it.
    named = chosen if wire == chosen else f"{chosen} (sent as {wire})"

    body: dict[str, Any] = {
        "model": wire,
        "temperature": conf.llm_temperature if temperature is None else temperature,
        "max_tokens": max_tokens,
        "messages": messages
        or [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }
    asked_effort = conf.judge_reasoning_effort.value
    if judging:
        body.pop("temperature")
        body.update(judge_tuning(chosen, base_url, conf))
    searched: str | bool = False
    steps: list[_Step] = []
    results = conf.web_search_max_results if max_results is None else max_results
    if web_search and supports_web_search(base_url):
        searched = _engine_for(web_search_engine, chosen, conf)
        steps = _search_steps(search_mechanism(chosen, conf), wire, searched)
        _apply_search(body, steps[0], searched, results)
    url = f"{_api_root(base_url)}/v1/chat/completions"

    last: Exception | None = None
    # How high the budget may be raised on a cut-off. A caller that asked for
    # more than the shared ceiling keeps what it asked for: this is a floor
    # under the retries, not a cap on the request.
    ceiling = max(int(body["max_tokens"]), conf.answer_max_tokens)
    doublings = 0
    # Failed attempts are counted apart from all attempts: `retries` bounds the
    # failures, and a cut-off is not one. Counted together, a call could spend
    # its whole retry budget on raising the cap and have nothing left for the
    # network.
    failures = 0
    attempts = 0
    # Busy replies (429, overload) waited out, and the seconds spent waiting.
    busy = 0
    waited = 0.0
    # USD over every priced response of this call, cut-offs included; None —
    # the provider priced none of them.
    spent: float | None = None
    while True:
        attempts += 1
        try:
            resp = httpx.post(
                url,
                json=body,
                headers=_headers_for(api_key, conf.llm_app_name),
                timeout=conf.llm_timeout,
            )
            if resp.status_code >= 400:
                raise _classify(
                    resp.status_code,
                    f"{named} -> {resp.status_code}: {resp.text[:300]}",
                    retry_after_of(resp.headers),
                )
            data = resp.json()
            # The provider also hands a refusal back with HTTP 200, putting it
            # in the body. Without parsing that, "out of credits" would look
            # like an empty answer from the model.
            if isinstance(data.get("error"), dict):
                failure = data["error"]
                raise _classify(
                    int(failure.get("code") or 0),
                    f"{named}: {str(failure.get('message'))[:300]}",
                )

            priced = cost.cost_of(data.get("usage") or {})
            cost.charge(priced, cost.role_of(role))
            if priced is not None:
                spent = (spent or 0.0) + priced

            choice = (data.get("choices") or [{}])[0]
            content = ((choice.get("message") or {}).get("content") or "").strip()
            finish = str(choice.get("finish_reason") or "")

            usage: dict[str, Any] = dict(data.get("usage") or {})
            usage.update(
                # Who served the call, when the provider is a router rather
                # than the model's owner: the same name can reach hosts running
                # different quantisations, and that changes the answers.
                # Recorded, not pinned — see docs/limitations.md.
                served_by=str(data.get("provider") or ""),
                finish_reason=finish,
                max_tokens=body["max_tokens"],
                truncated=finish == "length",
                length_retry=doublings > 0,
                length_retries=doublings,
                attempts=attempts,
                busy_retries=busy,
                backoff_seconds=round(waited, 1),
                web_search=searched,
                citations=citations_of(choice.get("message") or {}),
                cost_usd=spent,
            )
            if judging:
                usage.update(
                    temperature=body.get("temperature"),
                    reasoning_effort=(body.get("reasoning") or {}).get("effort")
                    or False,
                )
            if steps:
                usage.update(
                    web_search_via=steps[0][0],
                    web_search_forced=steps[0][1] or False,
                    web_search_requests=search_requests(usage),
                )

            if finish == "length" and int(body["max_tokens"]) < ceiling:
                # A reasoning model spends output tokens on reasoning BEFORE it
                # prints the answer, and hits the cap on that. Retry with a
                # doubled budget — ported from LiveTruth's P1, where
                # measurements reached 3269 tokens of reasoning and one case
                # burned 4096. No pause is needed here: the provider answered,
                # just briefly.
                #
                # The doubling REPEATS up to the ceiling rather than happening
                # once. A single doubling was a number in disguise: whichever
                # cap the caller starts from, one doubling of it is just as
                # arbitrary, and the next reasoning model overruns that too —
                # tiered_explanation did, at 1400 per item and again at twice
                # that. Now the budget climbs until it either fits or reaches
                # the ceiling every other call in the service already uses.
                doublings += 1
                # The floor of 1 is what keeps this loop finite: a caller that
                # asked for no tokens at all would otherwise double nothing
                # forever.
                body["max_tokens"] = min(max(int(body["max_tokens"]), 1) * 2, ceiling)
                continue

            if not content:
                # Empty with a normal finish_reason — a retry will change
                # nothing; empty with length — the budget has climbed to the
                # ceiling and the model printed nothing before reaching it. The
                # budget is named, because that is the number to raise.
                raise (LLMTruncatedError if finish == "length" else LLMFatalError)(
                    f"{named} returned an empty answer "
                    f"(finish_reason={finish}, max_tokens={body['max_tokens']})"
                )

            # A truncated answer comes back with a note rather than a failure:
            # truncated text can be graded, missing text cannot. Array parsing
            # can pull whole objects out of it.
            usage["latency_s"] = round(time.monotonic() - started, 3)
            return content, usage
        except LLMFatalError as exc:
            # A judge's reasoning effort or temperature refused: step it down.
            if judging and _refuses_tuning(exc, named, body, wire, asked_effort):
                continue
            # A refused search step: the next one down, at once. Forcing the
            # tool or the tool itself can be refused where plain search works.
            if len(steps) > 1 and _refuses_search(exc, named):
                if steps[0][0] == "tool":
                    _step_down(wire, str(searched), steps)
                steps.pop(0)
                _apply_search(body, steps[0], str(searched), results)
                continue
            # There is nothing to retry: it is the key, access, the model name
            # or the money. We fail at once so the cause is visible.
            raise
        except LLMBusyError as exc:
            # A rate limit or an overload: wait, longer each time, as long as
            # the provider asks, and try the same call again.
            last = exc
            busy += 1
            if busy > BUSY_RETRIES:
                break
            delay = backoff_delay(busy, exc.retry_after)
            waited += delay
            time.sleep(delay)
        except (httpx.TimeoutException, httpx.TransportError, LLMError) as exc:
            last = exc
            failures += 1
            if failures > retries:
                break
            # Ollama serves one request at a time: during indexing or someone
            # else's request the answer may not arrive in time. A pause before
            # the retry, not an instant one back into the same busy queue.
            time.sleep(5 * failures)

    raise LLMError(f"{chosen}: {last}")


def _balanced(text: str, opening: str, closing: str) -> str | None:
    """The first balanced fragment from opening to its matching closing.

    Brackets inside string literals do not count, otherwise an answer with text
    such as "see item [2]" falls the parsing apart.
    """
    start = text.find(opening)
    if start < 0:
        return None
    depth = 0
    in_string = False
    escaped = False
    for i in range(start, len(text)):
        char = text[i]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == opening:
            depth += 1
        elif char == closing:
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


def _all_balanced(text: str, opening: str, closing: str) -> list[str]:
    """Every balanced fragment in a row, left to right.

    Needed for a truncated answer: the model regularly hits the token cap in
    the middle of an array, and then the array's closing bracket is missing but
    several whole objects inside it already exist. Parsing them one by one is
    the only way not to throw away work that has already been done.
    """
    found: list[str] = []
    cursor = 0
    while cursor < len(text):
        piece = _balanced(text[cursor:], opening, closing)
        if piece is None:
            break
        found.append(piece)
        cursor += text[cursor:].find(piece) + len(piece)
    return found


def _strip_fence(raw: str) -> str:
    """Strip the ``` fence the model likes to wrap JSON in."""
    text = raw.strip()
    if not text.startswith("```"):
        return text
    return "\n".join(
        line for line in text.splitlines() if not line.strip().startswith("```")
    ).strip()


def parse_json_list(raw: str) -> list[dict[str, Any]]:
    """A list of objects out of the model's answer.

    We accept three forms: a bare array, an array in a ``` fence, a single
    object. Anything else is an error: better to skip a chunk than to write a
    parsing invention into the dataset.

    Raises:
        LLMError: the answer holds no parseable JSON
    """
    text = _strip_fence(raw)

    candidate = _balanced(text, "[", "]")
    if candidate:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError as exc:
            raise LLMError(f"cannot parse the JSON array: {exc}") from exc
        return [item for item in parsed if isinstance(item, dict)]

    # There is no array: either a single object arrived, or the array broke off
    # in the middle. Both cases are parsed the same way — we take every whole
    # object.
    salvaged: list[dict[str, Any]] = []
    for piece in _all_balanced(text, "{", "}"):
        try:
            parsed_one = json.loads(piece)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed_one, dict):
            salvaged.append(parsed_one)
    if salvaged:
        return salvaged

    raise LLMError(f"the answer holds no JSON: {raw[:200]}")


def parse_json_object(raw: str) -> dict[str, Any]:
    """The first balanced JSON object out of the model's answer.

    Kept apart from parse_json_list: a judge's verdict is always an object, and
    looking for an array in such an answer first is risky. Reasoning such as
    "according to [1]" looks like an array, parses into [1] and turns the
    verdict into nothing.

    Raises:
        LLMError: there is no object, or it does not parse
    """
    candidate = _balanced(_strip_fence(raw), "{", "}")
    if not candidate:
        raise LLMError(f"the answer holds no JSON object: {raw[:200]}")
    try:
        data = json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise LLMError(f"cannot parse the JSON object: {exc}") from exc
    if not isinstance(data, dict):
        raise LLMError(f"expected an object, got {type(data).__name__}")
    return data


def check_model_available(
    model: str | None = None,
    settings: Settings | None = None,
    provider: Provider | None = None,
) -> str:
    """Make sure a role's model is available at its provider.

    Args:
        model: The model name; defaults to the role's, otherwise the generator
        settings: Process settings
        provider: The role whose address and key are checked. Without it the
            shared settings are used — and then the check goes somewhere other
            than where the call will actually go, if the role has its own
            provider

    Returns:
        The name of the checked model

    Raises:
        ExternalCallBlocked: the address is outside the perimeter
        LLMError: the model is not among the pulled ones, or the provider did
            not accept it
    """
    conf = settings or get_settings()
    base_url = provider.url if provider is not None else conf.ollama_url
    api_key = provider.api_key if provider is not None else conf.llm_api_key
    check_model_host(base_url, conf)

    wanted = model or (provider.model if provider is not None else conf.generator_model)
    # The provider is asked about its own name for the model, not about ours.
    wire = catalog.load(conf).native(wanted, kind_for_url(base_url))

    # /api/tags is Ollama's own route; external providers do not have it.
    # Asking them for a list of pulled models makes no sense: they pull
    # nothing. So we check availability the only way it can be checked against
    # someone else's API — with a short request.
    if api_key:
        resp = httpx.post(
            f"{_api_root(base_url)}/v1/chat/completions",
            json={
                "model": wire,
                "max_tokens": 1,
                "messages": [{"role": "user", "content": "ping"}],
            },
            headers=_headers_for(api_key, conf.llm_app_name),
            timeout=60,
        )
        if resp.status_code < 400:
            with contextlib.suppress(ValueError, AttributeError):
                cost.charge(cost.cost_of(resp.json().get("usage") or {}))
        if resp.status_code >= 400:
            raise LLMError(
                f'the provider did not accept the model "{wire}": '
                f"{resp.status_code} {resp.text[:200]}"
            )
        return wanted

    names = set(installed_models(base_url))
    if wire not in names and f"{wire}:latest" not in names:
        raise LLMError(
            f'Ollama has no model "{wire}" '
            f"(available: {', '.join(sorted(names)) or '-'}). "
            f"Pull it: ollama pull {wire}"
        )
    return wanted


def installed_models(base_url: str, *, timeout: int = 30) -> list[str]:
    """The models Ollama has pulled, by name.

    Its own route: no other provider has one, because none of them pull
    anything.

    Args:
        base_url: The Ollama address, with or without /v1
        timeout: Seconds to wait

    Returns:
        The names, as Ollama gives them — tag and all

    Raises:
        httpx.HTTPError: Ollama did not answer
    """
    resp = httpx.get(f"{_api_root(base_url)}/api/tags", timeout=timeout)
    resp.raise_for_status()
    return [str(m["name"]) for m in resp.json().get("models", []) if m.get("name")]
