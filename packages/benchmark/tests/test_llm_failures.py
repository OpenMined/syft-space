"""Provider refusals: what to retry, what not to, and what to do with a cut-off.

A port of fixes P1 and P2 from LiveTruth (`local_docs/FIXES.md`). The
benchmark's client came from the OMSyft prototype rather than from LiveTruth's
fixed client — and neither fix made it across. Because of that a cut-off at the
token cap happened three times: gemini could not manage 200 tokens at the judge,
Opus cut an item off at 1100 on a live rig. Each time it was cured with a number
rather than with a mechanism.

These tests hold the mechanism: a cut-off is spotted by finish_reason and
retried with a doubled budget, and a fatal refusal is not retried at all.
"""

from __future__ import annotations

import time
from typing import Any

import httpx
import pytest

from syft_benchmark.config import Settings
from syft_benchmark.llm import LLMError, LLMFatalError, chat


def _reply(content: str, finish: str = "stop") -> dict[str, Any]:
    return {
        "choices": [{"message": {"content": content}, "finish_reason": finish}],
        "usage": {"completion_tokens": 7},
    }


class _Provider:
    """The provider's replies in order; every call records the budget requested."""

    def __init__(self, *replies: tuple[int, dict[str, Any]]) -> None:
        self.replies = list(replies)
        self.budgets: list[int] = []
        self.calls = 0

    def __call__(self, url: str, **kwargs: Any) -> httpx.Response:
        self.calls += 1
        self.budgets.append(int(kwargs["json"]["max_tokens"]))
        status, payload = self.replies[min(self.calls - 1, len(self.replies) - 1)]
        return httpx.Response(status, json=payload, request=httpx.Request("POST", url))


def _local() -> Settings:
    return Settings(ollama_url="http://localhost:11434")  # type: ignore[call-arg]


# --- P1: a cut-off at the token cap ----------------------------------------


def test_a_truncated_reply_is_retried_with_a_doubled_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The main fix: a mechanism instead of a number.

    A reasoning model spends output tokens on reasoning BEFORE the answer and
    hits the cap on that. Raising the constant is a patch: the next model will
    hit the next number.
    """
    provider = _Provider(
        (200, _reply("", finish="length")),
        (200, _reply('{"correct": true}')),
    )
    monkeypatch.setattr(httpx, "post", provider)

    answer, usage = chat("s", "u", max_tokens=1000, settings=_local())

    assert answer == '{"correct": true}'
    assert provider.budgets == [1000, 2000], "the budget must double exactly once"
    assert usage["length_retry"] is True


def test_the_budget_climbs_until_it_fits_rather_than_doubling_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One doubling is the same number in disguise.

    Whatever cap the caller starts from, twice it is just as arbitrary a guess:
    tiered_explanation was cut off at 2200 and again at 4400. The climb goes on
    until the answer fits or the shared ceiling is reached.
    """
    provider = _Provider(
        (200, _reply("", finish="length")),
        (200, _reply("", finish="length")),
        (200, _reply("", finish="length")),
        (200, _reply('{"correct": true}')),
    )
    monkeypatch.setattr(httpx, "post", provider)

    answer, usage = chat("s", "u", max_tokens=1000, settings=_local())

    assert answer == '{"correct": true}'
    assert provider.budgets == [1000, 2000, 4000, 8000]
    assert usage["length_retries"] == 3


def test_the_climb_stops_at_the_shared_answer_ceiling(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A model that never stops must not be paid for indefinitely.

    The ceiling is the one every other call in the service already asks for, so
    reaching it means the answer does not fit the measurement at all — not that
    the budget was set too low here.
    """
    provider = _Provider((200, _reply("", finish="length")))
    monkeypatch.setattr(httpx, "post", provider)

    with pytest.raises(LLMError):
        chat("s", "u", max_tokens=2000, retries=0, settings=_local())

    assert provider.budgets == [2000, 4000, 8000, 8192]


def test_raising_the_budget_does_not_spend_the_retry_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`retries` bounds failures, and a cut-off is not a failure.

    Counted together, a call could climb its way out of retries and have none
    left for the network — the failure it is actually there for.
    """
    provider = _Provider(
        (200, _reply("", finish="length")),
        (200, _reply("", finish="length")),
        (503, {"error": "the gateway is busy"}),
        (200, _reply("an answer")),
    )
    monkeypatch.setattr(httpx, "post", provider)
    monkeypatch.setattr(time, "sleep", lambda _seconds: None)

    answer, usage = chat("s", "u", max_tokens=1000, retries=1, settings=_local())

    assert answer == "an answer"
    assert usage["attempts"] == 4


def test_a_truncated_reply_with_text_is_returned_marked_not_dropped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A truncated answer can be graded, a missing one cannot.

    Array parsing can pull whole objects out of a fragment, and there is no
    point throwing away work that has been paid for. But the mark has to be
    there.
    """
    provider = _Provider((200, _reply('[{"q": "1"}, {"q": "2"', finish="length")))
    monkeypatch.setattr(httpx, "post", provider)

    answer, usage = chat("s", "u", max_tokens=500, settings=_local())

    assert answer.startswith("[")
    assert usage["truncated"] is True
    assert usage["finish_reason"] == "length"


def test_truncation_without_any_text_is_an_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The cap did not help even after doubling — there is nothing to return."""
    provider = _Provider((200, _reply("", finish="length")))
    monkeypatch.setattr(httpx, "post", provider)

    with pytest.raises(LLMError):
        chat("s", "u", max_tokens=100, retries=0, settings=_local())


def test_the_budget_is_recorded_for_the_audit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A cut-off has to be visible in the record, not inferred from odd numbers."""
    provider = _Provider((200, _reply("an answer")))
    monkeypatch.setattr(httpx, "post", provider)

    _answer, usage = chat("s", "u", max_tokens=321, settings=_local())

    assert usage["max_tokens"] == 321
    assert usage["truncated"] is False
    assert usage["attempts"] == 1


# --- P2: the taxonomy of refusals ------------------------------------------


@pytest.mark.parametrize("status", [400, 401, 402, 403, 404, 422])
def test_a_fatal_refusal_is_not_retried(
    monkeypatch: pytest.MonkeyPatch, status: int
) -> None:
    """The key, access, the model name, the money — a retry will change nothing.

    On an external provider with a 900-second timeout three attempts would cost
    forty-five minutes of waiting instead of an instant hint about what to
    check.
    """
    provider = _Provider((status, {"error": {"message": "nope"}}))
    monkeypatch.setattr(httpx, "post", provider)

    with pytest.raises(LLMFatalError):
        chat("s", "u", retries=2, settings=_local())

    assert provider.calls == 1, "a fatal refusal is not retried"


def test_a_refusal_in_the_body_of_a_200_is_still_a_refusal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The provider puts its refusal in the body with HTTP 200.

    Without parsing it this would look like an empty answer from the model —
    that is, like a property of the model rather than the state of an account.
    """
    provider = _Provider(
        (200, {"error": {"code": 402, "message": "Insufficient credits"}})
    )
    monkeypatch.setattr(httpx, "post", provider)

    with pytest.raises(LLMFatalError):
        chat("s", "u", retries=2, settings=_local())

    assert provider.calls == 1


def test_a_transient_refusal_is_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    """Overload and 500s are cured by a retry — that was the original point."""
    provider = _Provider(
        (503, {"error": {"message": "overloaded"}}),
        (200, _reply("an answer")),
    )
    monkeypatch.setattr(httpx, "post", provider)
    monkeypatch.setattr("syft_benchmark.llm.ollama.time.sleep", lambda _s: None)

    answer, _usage = chat("s", "u", retries=2, settings=_local())

    assert answer == "an answer"
    assert provider.calls == 2


def test_an_empty_reply_at_a_normal_finish_is_not_retried(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Empty with a normal finish_reason — a retry will change nothing."""
    provider = _Provider((200, _reply("")))
    monkeypatch.setattr(httpx, "post", provider)

    with pytest.raises(LLMFatalError):
        chat("s", "u", retries=2, settings=_local())

    assert provider.calls == 1
