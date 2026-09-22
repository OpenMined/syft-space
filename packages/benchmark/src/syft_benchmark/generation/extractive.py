"""Extractive generators: masking a span in a sentence.

A port of three LiveTruth generators — `named_entity_masking`,
`numeric_masking`, `temporal_masking`. The shape is one: take a sentence,
replace one span with "______", and the span itself becomes the gold answer.

    Fill in the blank: The Hub stores endpoint metadata in ______.

The value of this shape is that **the gold answer cannot be invented**: it is
cut out of the text, not composed. Our gold-answer screening passes trivially on
span pairs, and this is the only class of items where the generator cannot lie.

Two paths, as in the original, but the choice is automatic (see `language.py`):

  * **spaCy** — named entity recognition. Deterministic, without calling a
    model, hundreds of pairs in seconds. Requires an installed language model.
  * **LLM** — one call for all three categories at once. Any language, but the
    gold answer is once again produced by a model, and screening becomes
    mandatory.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

_MIN_SENTENCE_CHARS = 40
_MASK = "______"

# The spaCy labels by category. They match the original: the set was checked on
# a news corpus and is carried over unchanged.
NER_LABELS = frozenset({"PERSON", "ORG", "GPE", "NORP", "FAC", "LOC", "EVENT"})
NUMERIC_LABELS = frozenset({"CARDINAL", "MONEY", "PERCENT", "QUANTITY", "ORDINAL"})
TEMPORAL_LABELS = frozenset({"DATE", "TIME"})

# There is no point masking a vague time: "recently" is restored out of thin air
# and checks nothing. Both languages are listed — the corpus can be in either.
_VAGUE_TIME = re.compile(
    r"^(now|today|tomorrow|yesterday|recently|later|soon|currently|then|ago|"
    r"early|late)$",
    re.IGNORECASE,
)

# Markup that does not make a sentence. LiveTruth worked over news prose, where
# there is none of this; technical documentation, though, is half made of code
# blocks, tables and parameter lists, and sentence segmentation cuts straight
# through them. Masking "Bearer" inside an example request is meaningless: what
# gets tested is not knowledge of the corpus but the ability to guess the syntax.
_MARKUP = (
    "```",
    "|",
    "~~~",
    "<table",
    "</",
    "/>",
    # The arrows of mermaid diagrams: a code block without a fence, which the
    # sentence segmenter takes for a phrase.
    "->>",
    "-->",
    "->",
    "=>",
)

# The share of letters in a sentence. A line of code or a table falls short: it
# is dominated by brackets, hyphens, slashes and punctuation.
_MIN_LETTER_SHARE = 0.55


def is_prose(sentence: str) -> bool:
    """Whether the sentence looks like text rather than markup.

    The check stands before masking: a masked fragment of code gives an item that
    measures nothing yet lands confidently in the metrics.
    """
    if any(marker in sentence for marker in _MARKUP):
        return False
    # Lines like "  key: value" and "- item" are parameter lists, not speech.
    stripped = sentence.lstrip()
    if stripped.startswith(("-", "*", "#", ">", "=")):
        return False
    letters = sum(1 for ch in sentence if ch.isalpha() or ch.isspace())
    return bool(sentence) and letters / len(sentence) >= _MIN_LETTER_SHARE


CATEGORIES: dict[str, frozenset[str]] = {
    "named_entity": NER_LABELS,
    "numeric": NUMERIC_LABELS,
    "temporal": TEMPORAL_LABELS,
}

# The gold answer length by category: a name can be long, a number cannot.
_MAX_ANSWER_CHARS = {"named_entity": 100, "numeric": 50, "temporal": 60}


@dataclass(frozen=True, slots=True)
class Masked:
    """One masked pair before it turns into a dataset record."""

    question: str
    answer: str
    context: str
    meta: dict[str, Any]


# What a real gold answer looks like: words, numbers, versions, units. Anything
# with punctuation and operators in it is a shard of markup, not an entity.
#
# The check is needed because of the corpus. The entity recogniser was trained on
# news, and on technical documentation it errs noticeably: "+ vector" arrives
# labelled DATE, and so does "402/403 +". Such an item measures nothing yet lands
# confidently in the metrics.
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
    return not (category == "temporal" and _VAGUE_TIME.match(answer))


def mask_with_spacy(
    text: str, nlp: Any, categories: tuple[str, ...] = ("named_entity",)
) -> dict[str, list[Masked]]:
    """Build pairs from a chunk using spaCy.

    Args:
        text: A chunk of the document
        nlp: A loaded spaCy model
        categories: Which categories to build

    Returns:
        The pairs by category
    """
    out: dict[str, list[Masked]] = {name: [] for name in categories}
    seen: set[tuple[str, str]] = set()

    doc = nlp(text)
    for sent in doc.sents:
        sentence = sent.text.strip()
        if len(sentence) < _MIN_SENTENCE_CHARS or not is_prose(sentence):
            continue

        # We parse the sentence separately: the entity offsets are needed
        # relative to it, not to the whole chunk.
        parsed = nlp(sentence)
        for ent in parsed.ents:
            for category in categories:
                if ent.label_ not in CATEGORIES[category]:
                    continue
                answer = ent.text.strip()
                if not _acceptable(category, answer):
                    continue

                key = (sentence, answer)
                if key in seen:
                    continue
                seen.add(key)

                masked = sentence[: ent.start_char] + _MASK + sentence[ent.end_char :]
                out[category].append(
                    Masked(
                        question=f"Fill in the blank: {masked}",
                        answer=answer,
                        context=sentence,
                        meta={
                            "entity_label": ent.label_,
                            "mode": "spacy",
                            "category": category,
                        },
                    )
                )

    return out


COMBINED_SYSTEM = """\
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
  - Generate up to {n} questions per category, fewer if the fragment lacks \
that type. An empty array is a valid answer.

Respond with ONLY a JSON object with three arrays. No markdown, no commentary.
{{
  "named_entity": [
    {{"question": "sentence with ______", "answer": "masked span", \
"entity_type": "PERSON|ORG|PRODUCT|GPE|LOC|EVENT"}}
  ],
  "numeric": [
    {{"question": "sentence with ______", "answer": "masked span", \
"entity_type": "MONEY|PERCENT|COUNT|MEASUREMENT|VERSION|PORT"}}
  ],
  "temporal": [
    {{"question": "sentence with ______", "answer": "masked span", \
"entity_type": "DATE|DURATION|YEAR|DEADLINE|TIME"}}
  ]
}}
"""


def parse_combined(
    data: dict[str, Any], categories: tuple[str, ...]
) -> dict[str, list[Masked]]:
    """Parse the LLM answer into pairs by category.

    We skip everything where there is no mask or the gold answer was not
    substituted into the sentence: the model sometimes returns the original
    sentence whole, and such a "pair" tests not the endpoint but the ability to
    repeat a text.
    """
    out: dict[str, list[Masked]] = {name: [] for name in categories}
    seen: set[tuple[str, str]] = set()

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

            key = (question, answer)
            if key in seen:
                continue
            seen.add(key)

            out[category].append(
                Masked(
                    question=f"Fill in the blank: {question}",
                    answer=answer,
                    context=question,
                    meta={
                        "entity_label": str(item.get("entity_type") or ""),
                        "mode": "llm",
                        "category": category,
                    },
                )
            )

    return out
