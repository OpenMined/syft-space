"""The chat client every role calls through: one OpenAI-compatible request,
retried, widened on a cut-off, stepped down on a refused search or tuning.

The same client talks to a local Ollama and to an external provider. It is
also the one place where the perimeter is enforced: before every call the
address is checked, because there are many callers and forgetting the check
once is enough.
"""

from __future__ import annotations

import contextlib
import time
from typing import TYPE_CHECKING, Any

import httpx

from syft_benchmark.config import Settings, check_model_host, get_settings
from syft_benchmark.llm import catalog, cost
from syft_benchmark.llm.errors import (
    BUSY_RETRIES,
    LLMBusyError,
    LLMError,
    LLMFatalError,
    LLMTruncatedError,
    backoff_delay,
    classify,
    error_detail,
    retry_after_of,
)
from syft_benchmark.llm.providers import api_root, kind_for_url
from syft_benchmark.llm.tuning import judge_tuning, refuses_tuning
from syft_benchmark.llm.web_search import (
    EXA,
    PLUGIN_STEP,
    SearchStep,
    apply_search,
    citations_of,
    engine_for,
    refuses_search,
    search_mechanism,
    search_missed,
    search_requests,
    search_steps,
    step_down,
    supports_web_search,
)

if TYPE_CHECKING:
    from syft_benchmark.llm.roles import Provider


def _headers_for(api_key: str, app_name: str) -> dict[str, str]:
    """Headers for one key; a local Ollama needs none and is sent none."""
    if not api_key:
        return {}
    return {
        "Authorization": f"Bearer {api_key}",
        # OpenRouter shows this in its console; optional, but it lets the
        # benchmark's runs be told apart from the rest of the traffic.
        "X-Title": app_name,
    }


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
            "required", then by naming it, then the ``web`` plugin, stepping
            down when the provider refuses a step (and straight to the plugin
            for a model without tool calling). An answer that shows no search
            is asked once more with the Exa plugin, which always searches.
            Elsewhere the call goes without it and usage says
            ``web_search: False``
        web_search_engine: "native", "plugin" (Exa) or "auto" (native when the
            catalogue says the model has it, else Exa)
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
        ("required", "named" or False), web_search_requests (the provider's
        count, or None) and web_search_retry (why the call was asked again
        with the Exa plugin: "leaked" or "unused"; absent — it was not)

    Raises:
        ExternalCallBlocked: the model's address is outside the perimeter
        LLMError: it did not answer, or answered empty
    """
    conf = settings or get_settings()
    # Wall time of the whole call, retries and waits included.
    started = time.monotonic()

    # The role sets the address, the key and the model; without a role it is the
    # shared settings.
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
    steps: list[SearchStep] = []
    results = conf.web_search_max_results
    # The search cap is the tested models': the web check searches unbounded.
    calls = conf.web_search_max_calls if cost.role_of(role) == cost.SUBJECTS else 0
    if web_search and supports_web_search(base_url):
        searched = engine_for(web_search_engine, chosen, conf)
        steps = search_steps(search_mechanism(chosen, conf), wire, searched)
        apply_search(body, steps[0], searched, results, calls)
    url = f"{api_root(base_url)}/v1/chat/completions"

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
    # Why the call was asked again with the Exa plugin; "" — it was not. The
    # answer before that retry is returned if the retry fails.
    retry = ""
    before: tuple[str, dict[str, Any]] | None = None

    def fallback() -> tuple[str, dict[str, Any]] | None:
        if before is None:
            return None
        latency = round(time.monotonic() - started, 3)
        return before[0], {**before[1], "cost_usd": spent, "latency_s": latency}

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
                try:
                    refusal = resp.json()
                except ValueError:
                    refusal = None
                raise classify(
                    resp.status_code,
                    f"{named} -> {resp.status_code}: "
                    f"{error_detail(refusal, resp.text)}",
                    retry_after_of(resp.headers),
                )
            data = resp.json()
            # The provider also hands a refusal back with HTTP 200, putting it
            # in the body. Without parsing that, "out of credits" would look
            # like an empty answer from the model.
            if isinstance(data.get("error"), dict):
                failure = data["error"]
                raise classify(
                    int(failure.get("code") or 0),
                    f"{named}: {error_detail(data, str(failure.get('message')))}",
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
                    web_search_via=steps[0].mechanism,
                    web_search_forced=steps[0].forcing or False,
                    web_search_requests=search_requests(usage),
                )
                if retry:
                    usage["web_search_retry"] = retry
                missed = search_missed(usage, choice.get("message") or {})
                exa = steps[0].mechanism == "plugin" and searched == EXA
                if missed and not retry and not exa:
                    # No search shown: once more with the Exa plugin, which
                    # always searches. The first answer stays as a fallback.
                    retry = missed
                    if content:
                        before = (content, {**usage, "web_search_retry": missed})
                    searched = EXA
                    steps = [PLUGIN_STEP]
                    apply_search(body, steps[0], EXA, results, calls)
                    continue

            if finish == "length" and int(body["max_tokens"]) < ceiling:
                # A reasoning model spends output tokens on reasoning BEFORE it
                # prints the answer, and hits the cap on that. Retry with a
                # doubled budget. No pause is needed here: the provider
                # answered, just briefly.
                #
                # The doubling repeats until the answer fits or the budget
                # reaches the ceiling every other call in the service uses: a
                # single doubling of any starting cap is just as arbitrary.
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
            if judging and refuses_tuning(exc, named, body, wire, asked_effort):
                continue
            # A refused search step: the next one down, at once. Forcing the
            # tool or the tool itself can be refused where plain search works.
            if len(steps) > 1 and refuses_search(exc, named, bool(steps[0].forcing)):
                if steps[0].mechanism == "tool":
                    step_down(wire, str(searched), steps)
                steps.pop(0)
                apply_search(body, steps[0], str(searched), results, calls)
                continue
            # The Exa retry failed: the answer before it, marked as unsearched.
            kept = fallback()
            if kept is not None:
                return kept
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

    kept = fallback()
    if kept is not None:
        return kept
    raise LLMError(f"{chosen}: {last}")


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
            f"{api_root(base_url)}/v1/chat/completions",
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
    resp = httpx.get(f"{api_root(base_url)}/api/tags", timeout=timeout)
    resp.raise_for_status()
    return [str(m["name"]) for m in resp.json().get("models", []) if m.get("name")]
