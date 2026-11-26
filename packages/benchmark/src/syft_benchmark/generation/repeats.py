"""Questions of one article that ask the same fact.

Each kind is written by its own call, so a fill-in, a choice question and an
open question can all come down to one figure of the same sentence; the
manual review of la diaria (17.11) found 7 such repeats in 93 questions. A
repeated fact weighs twice in the score and tells nothing new about the
corpus.

A question's fact is what its gold answer adds to the question (its content
words less the question's own) and the source sentences its gold evidence
(``gold.py``) puts it in. Two questions repeat each other when they share an
evidence sentence and the smaller fact is at least ``MIN_SHARE`` inside the
other; when either was not located, only when the facts are near equal. The
question written later is rejected as written; the earlier one stays. Kinds
without a fact of their own are not compared: an unanswerable question has
no answer, a tiered explanation covers the article's key facts by design.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select

from syft_benchmark.config import PairStatus, Settings
from syft_benchmark.db import QaPair, session_scope
from syft_benchmark.generation import gold
from syft_benchmark.generation.abstractive import TTIL_HEAD
from syft_benchmark.generation.extractive import FILL_IN_PREFIX

# The build's drop reason and the start of a rejected pair's note.
REPEATED_FACT = "repeated fact"
# ``meta`` key of a rejected repeat: the question it repeats.
META = "repeats"

SKIPPED = frozenset({"unanswerable_property", "tiered_explanation"})
_ROLES = frozenset({gold.ANSWER, gold.CORRECTION, gold.HOP})

# Share of the smaller fact's words the other must hold.
MIN_SHARE = 0.6
# Without a shared sentence to anchor them, facts must be near equal.
_NEAR_EQUAL = 0.8

_WORD = re.compile(r"\w+")
_YEAR = re.compile(r"^(19|20)\d\d$")
# Words this long are compared by their first letters, as in ``gold.py``.
_PREFIX = 5
# Shorter words are function words in most languages ("de", "los", "the");
# a number is content at any length.
_MIN_LETTERS = 4


def _words(text: str) -> frozenset[str]:
    tokens = _WORD.findall(gold.normalize(text))
    return frozenset(
        token[:_PREFIX]
        for token in tokens
        if any(ch.isdigit() for ch in token) or len(token) >= _MIN_LETTERS
    )


def _sides(
    generator: str, question: str, answer: str, meta: dict[str, Any]
) -> tuple[str, str]:
    """What the question states and what its gold answer gives."""
    if generator == "mcq":
        stem = question.split("\n", 1)[0]
        head, sep, rest = answer.partition(") ")
        return stem, rest if sep and len(head) == 1 else answer
    if generator == "two_truths_one_lie":
        # The question lists every statement; the fact is the altered detail.
        detail = str(meta.get("source_detail") or "").strip()
        return "", detail or answer
    if question.startswith(FILL_IN_PREFIX):
        return question[len(FILL_IN_PREFIX) :], answer
    if question.startswith(TTIL_HEAD):
        return "", answer
    return question, answer


@dataclass(frozen=True, slots=True)
class Fact:
    """One question's fact."""

    generator: str
    question: str
    words: frozenset[str]
    passages: frozenset[str]
    # Empty for a question not stored yet.
    qa_id: str = ""

    def record(self) -> dict[str, Any]:
        """What a rejected repeat keeps of the question it repeats."""
        return {
            "qa_id": self.qa_id or None,
            "generator": self.generator,
            "question": self.question,
        }

    def note(self) -> str:
        """``repeated fact: the answer of qa "…"``."""
        shown = (
            self.question if len(self.question) <= 160 else self.question[:157] + "…"
        )
        return f'{REPEATED_FACT}: the answer of {self.generator} "{shown}"'


def fact_of(
    generator: str,
    question: str,
    answer: str,
    meta: dict[str, Any],
    evidence: Iterable[dict[str, Any]],
    qa_id: str = "",
) -> Fact | None:
    """The fact a question asks; None — a kind not compared, or no words."""
    if generator in SKIPPED:
        return None
    asked, given = _sides(generator, question, answer, meta)
    answered = _words(given)
    dated = frozenset(w for w in answered if _YEAR.match(w))
    # A year the anchor rule added says when, not what.
    if answered - dated:
        answered -= dated
    novel = answered - _words(asked)
    words = novel or answered
    if not words:
        return None
    passages = frozenset(
        gold.normalize(str(p.get("text") or ""))
        for item in evidence
        if isinstance(item, dict) and item.get("role") in _ROLES
        for p in item.get("passages") or []
        if isinstance(p, dict) and p.get("text")
    )
    return Fact(generator, question, words, passages, qa_id)


def repeated(new: Fact, old: Fact) -> bool:
    """Whether ``new`` asks the fact ``old`` asks."""
    shared = len(new.words & old.words)
    if not shared:
        return False
    if new.passages and old.passages:
        if not new.passages & old.passages:
            return False
        return shared / min(len(new.words), len(old.words)) >= MIN_SHARE
    smaller = min(len(new.words), len(old.words))
    return smaller >= 2 and shared / len(new.words | old.words) >= _NEAR_EQUAL


def first_repeat(new: Fact, facts: Iterable[Fact]) -> Fact | None:
    """The earliest of ``facts`` that ``new`` repeats."""
    return next((old for old in facts if repeated(new, old)), None)


def stored_facts(space: str, cohort: str, doc_id: str, conf: Settings) -> list[Fact]:
    """The facts of the article's questions already stored in the cohort and
    not rejected, oldest first."""
    meta = QaPair.meta
    with session_scope(conf) as session:
        rows = session.execute(
            select(
                QaPair.id,
                QaPair.generator,
                QaPair.question,
                QaPair.answer,
                meta.op("->")(gold.META),
                meta.op("->")("source_detail"),
            )
            .where(
                QaPair.space == space,
                QaPair.cohort == cohort,
                QaPair.doc_id == doc_id,
                QaPair.status != PairStatus.REJECTED.value,
                QaPair.generator.not_in(SKIPPED),
            )
            .order_by(QaPair.created_at, QaPair.id)
        ).all()
    facts: list[Fact] = []
    for qa_id, generator, question, answer, found, detail in rows:
        evidence = found.get("evidence") if isinstance(found, dict) else None
        fact = fact_of(
            generator,
            question,
            answer,
            {"source_detail": detail} if detail else {},
            evidence if isinstance(evidence, list) else [],
            qa_id,
        )
        if fact is not None:
            facts.append(fact)
    return facts
