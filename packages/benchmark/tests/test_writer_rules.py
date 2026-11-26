"""The writer rules from the la diaria review of 17.11: attributed claims, no
bylines or bios, tight gold answers, the outlet's own reporting, false
premises only on an explicit contradiction and with varied openings, and
the year in every date.
"""

from __future__ import annotations

import re

import pytest

from syft_benchmark.generation.extractive import COMBINED_SYSTEM
from syft_benchmark.generation.generators import GENERATORS
from syft_benchmark.generation.wording import (
    ANCHOR_RULE,
    ATTRIBUTION_RULE,
    FILL_IN_TIME_RULE,
    NO_BYLINE_RULE,
    OWN_JOURNALISM_RULE,
    TIGHT_ANSWER_RULE,
)

PROMPTS = {
    key: spec.system.format(n=2) for key, spec in GENERATORS.items() if spec.system
}
PROMPTS["fill_in"] = COMBINED_SYSTEM.format(n=2)


@pytest.mark.parametrize("writer", sorted(PROMPTS))
def test_every_writer_skips_bylines_and_copy_from_others(writer: str) -> None:
    # Review T5, T6 (author bios) and 29, 41, 45, 60, 72 (another outlet's fact).
    assert NO_BYLINE_RULE in PROMPTS[writer]
    assert OWN_JOURNALISM_RULE in PROMPTS[writer]


@pytest.mark.parametrize(
    "writer",
    [
        "qa",
        "mcq",
        "two_truths_one_lie",
        "multihop_synthesis",
        "tiered_explanation",
        "false_premise",
    ],
)
def test_writers_of_claims_keep_them_attributed(writer: str) -> None:
    # Review 28, 33, 68: a claim written as fact.
    assert ATTRIBUTION_RULE in PROMPTS[writer]


@pytest.mark.parametrize(
    "writer", ["qa", "mcq", "false_premise", "unanswerable_property"]
)
def test_only_the_story_itself_is_never_named_as_a_source(writer: str) -> None:
    flat = " ".join(PROMPTS[writer].split())
    assert '"according to the article"' in flat
    assert '"according to ..."' not in flat


@pytest.mark.parametrize("writer", ["qa", "multihop_synthesis"])
def test_free_answers_hold_only_what_is_asked(writer: str) -> None:
    # Review 25, 46: the gold answer wider than the question.
    assert TIGHT_ANSWER_RULE in PROMPTS[writer]


def test_a_false_premise_needs_an_explicit_contradiction_and_varied_openings() -> None:
    flat = " ".join(PROMPTS["false_premise"].split())
    # Review 53: a premise the fragment does not refute.
    assert "states explicitly, in words that rule it out" in flat
    assert "nor on a claim that could be true alongside what the fragment says" in flat
    assert "return fewer questions" in flat
    # Every false premise of the review opened "¿Por qué…?".
    assert 'at most one may start with "Why" ("¿Por qué...?")' in flat
    assert "copies, verbatim, a sentence of the fragment" in flat


def test_every_date_carries_its_year() -> None:
    assert '"el 20 de octubre de 2026"' in " ".join(ANCHOR_RULE.split())
    assert '"el 20 de octubre"' in FILL_IN_TIME_RULE
    for writer, prompt in PROMPTS.items():
        if writer != "fill_in":
            assert ANCHOR_RULE in prompt, writer


def test_the_rules_hold_no_braces() -> None:
    for rule in (
        ATTRIBUTION_RULE,
        NO_BYLINE_RULE,
        OWN_JOURNALISM_RULE,
        TIGHT_ANSWER_RULE,
    ):
        assert not re.search(r"[{}]", rule)


def test_the_language_rule_closes_the_shared_rules() -> None:
    for key in ("qa", "mcq"):
        rules = GENERATORS[key].system.split("Rules:\n", 1)[1]
        assert "13. Write the question and the answer in the SAME language" in rules
