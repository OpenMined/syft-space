"""Screening the gold answers.

This step was not in the prototype — it answers question 5 of the spec. The
gold answer is written by an LLM with the chunk in front of it, and it usually
copies it from there. But sometimes it fills in from memory: adds a year, a job
title, a unit of measurement that is not in the chunk. Such a gold answer looks
plausible and spoils the measurement silently — a good endpoint answers from
the document, the judge compares against an invention and records a miss. This
cannot be spotted in the metrics: they are simply lower than they should be.

The check is lexical rather than model-based, and that is deliberate. It is
cheap (there are thousands of gold answers), deterministic (the same input
gives the same verdict — for screening that matters more than subtlety) and it
checks exactly what is needed: whether the answer was taken from the chunk.
Confirmation by a second model remains a possible extension, but starting with
it would mean judging a generator with a generator.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from syft_benchmark.config import Settings, get_settings

# Function words carry no content: their matching proves nothing, and in a
# short phrase they give almost a hundred percent coverage out of thin air.
# The list is English: for a corpus in another language nothing is subtracted,
# and the coverage threshold is merely applied more strictly.
_STOPWORDS = frozenset(
    {
        "the", "a", "an", "and", "or", "but", "of", "in", "on", "at", "to",
        "for", "with", "by", "from", "as", "is", "are", "was", "were", "be",
        "been", "it", "its", "this", "that", "these", "those", "there",
        "which", "who", "what", "when", "where", "how", "not", "no", "than",
        "then", "so", "such", "can", "will", "would", "should", "may",
    }
)  # fmt: skip

_TOKEN_RE = re.compile(r"[\w’'-]+", re.UNICODE)

# Short gold answers — "47", "Alembic", "2026-09-08" — are not measured by
# coverage: one word is either there or it is not, there is no share in between.
_SHORT_ANSWER_TOKENS = 3


@dataclass(frozen=True, slots=True)
class Review:
    """The verdict on a gold answer."""

    grounded: bool
    coverage: float
    note: str


def _content_tokens(text: str) -> list[str]:
    """Content words: no function words and nothing one character long."""
    return [
        token
        for token in (m.group(0).lower() for m in _TOKEN_RE.finditer(text))
        if len(token) > 1 and token not in _STOPWORDS
    ]


def _stem(token: str) -> str:
    """A crude word stem.

    Full lemmatisation is not needed here and would drag in a dependency: the
    aim is for "migrations" in the chunk to count for "migration" in the gold
    answer, not to build a morphology.
    """
    return token[:-2] if len(token) > 5 else token


def review_claims(
    claims: list[str], fragment: str, settings: Settings | None = None
) -> Review:
    """Whether the listed claims rest on the chunk.

    For generators whose gold answer is deliberately a different wording. An
    explanation "for a five-year-old" is obliged to use words that are not in
    the source: that is the point of it. Checking its text for a match with the
    source means screening out precisely what the item was created for.

    So for such items the generator lists the facts the explanation rests on,
    and those are what get checked. A majority is enough: one fact may be
    phrased far from the text, but if all of them miss — the gold answer is
    invented.

    Args:
        claims: The claims to check — key_facts or hop_facts
        fragment: The text the item was built from

    Returns:
        A Review with the share of confirmed claims
    """
    if not claims:
        return Review(False, 0.0, "nothing to check: no claims were listed")

    verdicts = [review_answer(claim, fragment, settings) for claim in claims]
    grounded = sum(1 for v in verdicts if v.grounded)
    share = grounded / len(verdicts)

    if share > 0.5:
        return Review(True, share, "")
    return Review(
        False,
        share,
        f"{grounded} of {len(verdicts)} claims follow from the chunk",
    )


def review_answer(
    answer: str, fragment: str, settings: Settings | None = None
) -> Review:
    """Whether the gold answer was taken from the chunk.

    Args:
        answer: The gold answer from the generator
        fragment: The chunk the pair was built from
        settings: The process settings; the coverage threshold comes from them

    Returns:
        A Review with the coverage share and an explanation
    """
    threshold = (settings or get_settings()).answer_coverage_threshold
    tokens = _content_tokens(answer)
    if not tokens:
        return Review(False, 0.0, "the gold answer has no content words")

    haystack = {_stem(token) for token in _content_tokens(fragment)}
    hits = sum(1 for token in tokens if _stem(token) in haystack)
    coverage = hits / len(tokens)

    if len(tokens) <= _SHORT_ANSWER_TOKENS:
        # A short answer is a whole fact: a number, a name, a date. It is either
        # in the chunk or invented, and there is nothing to average here.
        if hits == len(tokens):
            return Review(True, 1.0, "")
        missing = [t for t in tokens if _stem(t) not in haystack]
        return Review(
            False,
            coverage,
            f"the short gold answer is not in the chunk: {', '.join(missing[:3])}",
        )

    if coverage >= threshold:
        return Review(True, coverage, "")
    return Review(
        False,
        coverage,
        f"the gold answer rests on what is not in the chunk (coverage {coverage:.0%})",
    )
