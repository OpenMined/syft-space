"""Pulling JSON out of a model's answer.

A small model regularly wraps its answer in a fence, adds explanations or
breaks off in the middle of an array, so parsing is forgiving: the first
balanced JSON is taken rather than ``json.loads`` over the whole text.
"""

from __future__ import annotations

import json
from typing import Any

from syft_benchmark.llm.errors import LLMError


def _balanced(text: str, opening: str, closing: str) -> str | None:
    """The first balanced fragment from opening to its matching closing.

    Brackets inside string literals do not count, otherwise an answer with text
    such as "see item [2]" breaks the parsing.
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
    several whole objects inside it already exist.
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

    Three forms are accepted: a bare array, an array in a ``` fence, a single
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

    # No array: a single object arrived, or the array broke off in the middle.
    # Both are parsed the same way — every whole object is taken.
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
    reasoning such as "according to [1]" looks like an array, parses into [1]
    and turns the verdict into nothing.

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
