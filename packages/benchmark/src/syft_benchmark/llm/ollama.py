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

import json
import time
from typing import TYPE_CHECKING, Any

import httpx

from syft_benchmark.config import Settings, check_model_host, get_settings
from syft_benchmark.llm import catalog
from syft_benchmark.llm.providers import kind_for_url

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


def _classify(status: int, detail: str) -> LLMError:
    """A provider's refusal — fatal, or worth retrying."""
    lowered = detail.lower()
    if status in _FATAL_STATUS or any(mark in lowered for mark in _FATAL_BODY):
        return LLMFatalError(detail)
    return LLMError(detail)


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

    Returns:
        The answer text and usage, extended with finish_reason

    Raises:
        ExternalCallBlocked: the model's address is outside the perimeter
        LLMError: it did not answer, or answered empty
    """
    conf = settings or get_settings()

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
            return content, usage
        except LLMFatalError:
            # There is nothing to retry: it is the key, access, the model name
            # or the money. We fail at once so the cause is visible.
            raise
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
