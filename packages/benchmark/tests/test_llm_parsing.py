"""Parsing the local model's answers.

A 4B model in 4-bit quantisation answers carelessly, and almost every case
below is not hypothetical but was observed on the rig.
"""

import pytest

from syft_benchmark.config import ExternalCallBlocked, Settings
from syft_benchmark.llm import LLMError, chat, parse_json_list, parse_json_object


def test_plain_array() -> None:
    assert parse_json_list('[{"q": "1"}, {"q": "2"}]') == [{"q": "1"}, {"q": "2"}]


def test_fenced_array() -> None:
    raw = '```json\n[{"q": "1"}]\n```'
    assert parse_json_list(raw) == [{"q": "1"}]


def test_single_object_becomes_a_list() -> None:
    """We asked for an array and the model sent one object — that is a usable answer."""
    assert parse_json_list('{"q": "1"}') == [{"q": "1"}]


def test_prose_around_the_json_is_tolerated() -> None:
    raw = 'Here are the pairs:\n[{"q": "1"}]\nHope that helps.'
    assert parse_json_list(raw) == [{"q": "1"}]


def test_brackets_inside_strings_do_not_break_balance() -> None:
    raw = '[{"a": "see item [2] and {3}"}]'
    assert parse_json_list(raw) == [{"a": "see item [2] and {3}"}]


def test_non_dict_items_dropped() -> None:
    assert parse_json_list('[{"q": "1"}, "rubbish", 42]') == [{"q": "1"}]


def test_no_json_is_an_error() -> None:
    """Better to skip a chunk than to write a parsing invention into the dataset."""
    with pytest.raises(LLMError):
        parse_json_list("I don't know how to answer")


def test_truncated_array_keeps_the_complete_objects() -> None:
    """The model regularly hits the token cap in the middle of an array.

    The array's closing bracket is then missing, but finished pairs inside it
    already exist, and throwing them away means losing work that cost minutes
    of generation.
    """
    raw = '[{"q": "1"}, {"q": "2"}, {"q": '
    assert parse_json_list(raw) == [{"q": "1"}, {"q": "2"}]


def test_nothing_salvageable_is_an_error() -> None:
    with pytest.raises(LLMError):
        parse_json_list('[{"q": ')


def test_object_parser_ignores_citation_brackets() -> None:
    """Exactly the trap object parsing was split off from array parsing for.

    A judge's reasoning of the form "according to [1]" looks like an array;
    were we to look for one first, the verdict would turn into nothing.
    """
    raw = '{"verdict": "correct", "why": "according to [1] and [2]"}'
    parsed = parse_json_object(raw)
    assert parsed["verdict"] == "correct"


def test_object_parser_rejects_arrays() -> None:
    with pytest.raises(LLMError):
        parse_json_object("[1, 2, 3]")


def test_chat_refuses_a_model_outside_the_perimeter() -> None:
    """Invariant 2 fires in the client, before any network.

    The check stands right here rather than in the callers: there will be many
    callers, and forgetting it once is enough.
    """
    outside = Settings(ollama_url="https://api.openai.com/v1")  # type: ignore[call-arg]
    with pytest.raises(ExternalCallBlocked):
        chat("system", "user", settings=outside)
