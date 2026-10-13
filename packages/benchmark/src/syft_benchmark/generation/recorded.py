"""The writer call behind each generated pair, kept for the export.

One writer call can write several pairs (of one kind or, for masking, of
three). Every pair it wrote carries ``meta.writer.call``; the full texts —
system prompt, user prompt, raw reply — sit on the first pair stored from
the call only. The passage the prompt was built from is not stored twice: in
``user`` it is replaced by ``PASSAGE_MARK``, and ``passage`` is kept only
when it differs from that pair's ``context``.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable, Mapping
from typing import Any, Protocol

WRITER = "writer"
PASSAGE_MARK = "⟦passage⟧"
# The texts that sit on one pair of a call.
_FULL = ("model", "system", "user", "reply", "passage", "cost_usd", "latency_s")


class _Pair(Protocol):
    meta: dict[str, Any]
    context: str


def new_call(
    *,
    model: str,
    system: str,
    user: str,
    reply: str,
    passage: str,
    usage: Mapping[str, Any],
) -> dict[str, Any]:
    """A writer call as made: its id and full texts."""
    latency = usage.get("latency_s")
    return {
        "call": uuid.uuid4().hex,
        "model": model,
        "system": system,
        "user": user,
        "reply": reply,
        "passage": passage,
        "cost_usd": usage.get("cost_usd"),
        "latency_s": round(float(latency), 2) if latency is not None else None,
    }


def writer_meta(call: dict[str, Any], context: str) -> dict[str, Any]:
    """``meta.writer`` for the next pair stored from ``call``.

    The first pair gets the full texts, the rest only the call id. ``call``
    remembers that its texts were stored.
    """
    if call.get("_stored"):
        return {"call": call["call"]}
    call["_stored"] = True
    out = {key: call[key] for key in _FULL if key in call}
    out["call"] = call["call"]
    passage = str(out.pop("passage", "") or "")
    user = str(out.get("user") or "")
    if passage and user.count(passage) == 1:
        out["user"] = user.replace(passage, PASSAGE_MARK)
        if passage != context:
            out["passage"] = passage
    return out


def writer_calls(pairs: Iterable[_Pair]) -> dict[str, dict[str, Any]]:
    """Every writer call the pairs carry the texts of, by call id, the user
    prompt with its passage put back: {model, system, user, reply, passage,
    cost_usd, latency_s}."""
    out: dict[str, dict[str, Any]] = {}
    for pair in pairs:
        writer = (pair.meta or {}).get(WRITER)
        if not isinstance(writer, dict) or "system" not in writer:
            continue
        passage = str(writer.get("passage") or pair.context or "")
        user = str(writer.get("user") or "")
        if PASSAGE_MARK in user:
            user = user.replace(PASSAGE_MARK, passage)
        out[str(writer.get("call"))] = {
            "model": str(writer.get("model") or ""),
            "system": str(writer.get("system") or ""),
            "user": user,
            "reply": str(writer.get("reply") or ""),
            "passage": passage,
            "cost_usd": writer.get("cost_usd"),
            "latency_s": writer.get("latency_s"),
        }
    return out


def writer_call(
    pair: _Pair, calls: Mapping[str, dict[str, Any]]
) -> dict[str, Any] | None:
    """The writer call that wrote ``pair``; None — not recorded."""
    writer = (pair.meta or {}).get(WRITER)
    if not isinstance(writer, dict):
        return None
    return calls.get(str(writer.get("call")))


# The texts of a check call that sit on one pair of it.
_CHECK_FULL = ("model", "system", "user", "reply", "cost_usd", "latency_s")


def check_meta(call: dict[str, Any], verdict: dict[str, Any]) -> dict[str, Any]:
    """A pair's check record: its verdict, plus the call's texts on the first
    pair stored from ``call``. ``call`` remembers that its texts were stored."""
    if not call.get("call"):
        return dict(verdict)
    out = {**verdict, "call": call["call"]}
    if not call.get("_stored"):
        call["_stored"] = True
        out.update({key: call[key] for key in _CHECK_FULL if key in call})
    return out


def check_calls(pairs: Iterable[_Pair], key: str) -> dict[str, dict[str, Any]]:
    """Every check call under ``meta[key]`` the pairs carry the texts of, by
    call id: {model, system, user, reply, cost_usd, latency_s}."""
    out: dict[str, dict[str, Any]] = {}
    for pair in pairs:
        record = (pair.meta or {}).get(key)
        if isinstance(record, dict) and record.get("call") and "system" in record:
            out[str(record["call"])] = {k: record.get(k) for k in _CHECK_FULL}
    return out
