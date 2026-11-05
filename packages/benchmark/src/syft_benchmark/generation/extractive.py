"""Extractive generators: masking one span of a sentence taken verbatim.

``named_entity_masking``, ``numeric_masking`` and ``temporal_masking`` share
the shape, and the masked span is the gold answer:

    Fill in the blank: The Hub stores endpoint metadata in ______.

One LLM call writes all three categories for a chunk, in the chunk's language;
``parse_combined`` keeps only items whose blank and answer fit the sentence.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from syft_benchmark.generation.wording import FILL_IN_TIME_RULE

_MASK = "______"

# The fixed words a masked sentence is asked with.
FILL_IN_PREFIX = "Fill in the blank:"

# A vague time ("recently") is guessable and checks nothing.
_VAGUE_TIME = re.compile(
    r"^(now|today|tomorrow|yesterday|recently|later|soon|currently|then|ago|"
    r"early|late)$",
    re.IGNORECASE,
)

# A date counted from the day of writing: "this year", "last month", "two years
# ago". The sentence or the story's own date gives it away; either way it is
# not a fact of the story.
_RELATIVE_TIME = re.compile(
    r"^(?:(?:this|that|last|next|the same|the past|the previous|the following|"
    r"the coming)\s+(?:day|week|weekend|month|quarter|year|season|decade)"
    r"|.*\bago)$",
    re.IGNORECASE,
)

# Markup that does not make a sentence: masking a token of a code block or a
# table tests guessing the syntax, not knowing the corpus.
_MARKUP = (
    "```",
    "|",
    "~~~",
    "<table",
    "</",
    "/>",
    # The arrows of mermaid diagrams: a code block without a fence.
    "->>",
    "-->",
    "->",
    "=>",
)

# The share of letters in a sentence. A line of code or a table falls short: it
# is dominated by brackets, hyphens, slashes and punctuation.
_MIN_LETTER_SHARE = 0.55


def is_prose(sentence: str) -> bool:
    """Whether the sentence looks like text rather than markup."""
    if any(marker in sentence for marker in _MARKUP):
        return False
    # Lines like "  key: value" and "- item" are parameter lists, not speech.
    stripped = sentence.lstrip()
    if stripped.startswith(("-", "*", "#", ">", "=")):
        return False
    letters = sum(1 for ch in sentence if ch.isalpha() or ch.isspace())
    return bool(sentence) and letters / len(sentence) >= _MIN_LETTER_SHARE


# The gold answer length by category: a name can be long, a number cannot.
_MAX_ANSWER_CHARS = {"named_entity": 100, "numeric": 50, "temporal": 60}


@dataclass(frozen=True, slots=True)
class Masked:
    """One masked pair before it turns into a dataset record."""

    question: str
    answer: str
    meta: dict[str, Any]


# What a real gold answer looks like: words, numbers, versions, units.
# Punctuation and operators mark a shard of markup, not an entity.
_ANSWER_SHAPE = re.compile(r"^[\w\s.,'’%$№#-]+$", re.UNICODE)


def _acceptable(category: str, answer: str) -> bool:
    """Whether the span cut out will do as a gold answer."""
    if not answer or len(answer) > _MAX_ANSWER_CHARS[category]:
        return False
    if category != "numeric" and len(answer) < 2:
        return False
    if not _ANSWER_SHAPE.match(answer):
        return False
    if not any(ch.isalnum() for ch in answer):
        return False
    if category != "temporal":
        return True
    return not (_VAGUE_TIME.match(answer) or _RELATIVE_TIME.match(answer))


COMBINED_SYSTEM = f"""\
You are a benchmark dataset generator. Given a fragment of a document, \
generate fill-in-the-blank questions by masking specific spans in sentences.

Generate questions in THREE categories:

1. **named_entity**: Mask people, organizations, products, components, \
countries, locations, events.
2. **numeric**: Mask amounts, percentages, statistics, counts, measurements, \
port numbers, versions, rankings.
3. **temporal**: Mask specific dates, years, durations, deadlines, intervals \
(NOT vague words like "recently" or "soon").

Rules:
  - Each question replaces exactly ONE span with "______".
  - The sentence must carry enough context to make the answer unambiguous.
  - Skip trivial or vague items. Focus on specific, meaningful facts.
  - Take the sentence from the fragment verbatim; do not rewrite it.
  - The masked span is the answer, exactly as it appears.
  - Write in the SAME language as the fragment.
  - Generate up to {{n}} questions per category, fewer if the fragment lacks \
that type. An empty array is a valid answer.
  - The sentence must make sense to someone who has not read the rest of the \
story. No he, she, it, they or this without the subject named in the same \
sentence.
  - Use sentences that report a fact. Skip quotes, jokes, opinions and \
rhetorical lines.
  - Blank a fact a reader could only know from this story. Never blank a word \
the rest of the sentence gives away (the country before its own prime \
minister, "one", "this year") or lets you work out (a unit conversion).
  - Use a sentence only if it names its people, organisations and \
products so they are identifiable without the story: full name plus role \
or affiliation, a product with its maker. Skip a sentence whose subject is \
a first name, a pseudonym or an anonymous source.
  - {FILL_IN_TIME_RULE}
  - Use each sentence once.

Respond with ONLY a JSON object with three arrays. No markdown, no commentary.
{{{{
  "named_entity": [
    {{{{"question": "sentence with ______", "answer": "masked span", \
"entity_type": "PERSON|ORG|PRODUCT|GPE|LOC|EVENT"}}}}
  ],
  "numeric": [
    {{{{"question": "sentence with ______", "answer": "masked span", \
"entity_type": "MONEY|PERCENT|COUNT|MEASUREMENT|VERSION|PORT"}}}}
  ],
  "temporal": [
    {{{{"question": "sentence with ______", "answer": "masked span", \
"entity_type": "DATE|DURATION|YEAR|DEADLINE|TIME"}}}}
  ]
}}}}
"""


def parse_combined(
    data: dict[str, Any], categories: tuple[str, ...]
) -> dict[str, list[Masked]]:
    """Parse the LLM answer into masked items by category.

    An item without a blank, or with the answer still in the sentence, is
    skipped: it tests repeating the text, not the endpoint.
    """
    out: dict[str, list[Masked]] = {name: [] for name in categories}
    seen: set[str] = set()

    for category in categories:
        for item in data.get(category) or []:
            if not isinstance(item, dict):
                continue
            question = str(item.get("question") or "").strip()
            answer = str(item.get("answer") or "").strip()

            if _MASK not in question or not _acceptable(category, answer):
                continue
            if not is_prose(question):
                continue
            # A gold answer left in the question text makes the item pointless.
            if answer.lower() in question.replace(_MASK, " ").lower():
                continue

            # One item per sentence, even when the model ignores the prompt.
            sentence = question.replace(_MASK, answer)
            if sentence in seen:
                continue
            seen.add(sentence)

            out[category].append(
                Masked(
                    question=f"{FILL_IN_PREFIX} {question}",
                    answer=answer,
                    meta={
                        "entity_label": str(item.get("entity_type") or ""),
                        "category": category,
                    },
                )
            )

    return out
