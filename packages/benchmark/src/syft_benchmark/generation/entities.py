"""The entity check: does a question name its subject so anyone can tell who
or what is meant?

A question built on "Mariam, who asked to be identified only by her first
name" has no referent a reader or the web check can pin down. The question
writer is asked again, in a fresh call with no article, to list the people,
organisations, products, places, events and documents each question of a
unit names and to say whether each is identifiable from the question alone.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from syft_benchmark.generation.abstractive import TIERS, TTIL_HEAD
from syft_benchmark.generation.extractive import FILL_IN_PREFIX
from syft_benchmark.generation.pair import Pair
from syft_benchmark.llm import LLMError, parse_json_list

# ``meta`` key of a pair's check record.
META = "entity_check"
# The build's drop reason and the start of a rejected pair's note.
AMBIGUOUS_ENTITY = "ambiguous entity"

SYSTEM = """\
You review benchmark questions before they are used. A question is only \
usable if a reader who sees nothing but the question knows exactly which \
real-world person, organisation, product, place, event or document it is about.

For each numbered question, list every actor and entity it names or refers \
to, and decide for each whether it is identifiable from the question text \
alone.

Identifiable: a full name ("Donald Trump"), a name plus a distinguishing role \
or affiliation ("Sarah Chen, the CFO of Stripe"), a specific organisation \
("the European Central Bank"), a specific product with its maker and model \
("Apple's iPhone 16 Pro"), a writer or piece by its outlet ("WIRED's Nena \
Farrell", "WIRED's review of Amazon's Kindle Aluminum"), an event with its \
date ("the selloff in Singapore bank stocks in the week to Oct 10, 2026").
Not identifiable: a first name only, a pseudonym, an anonymous source, \
"a startup", "the company", "a researcher", "a local official", "her group" \
without a named owner, a product with no maker, "the reviewer" or "the \
author" with no outlet, an event placed only by "last month" or a month \
without its year.

A blank "______" is the answer to be filled in: do not judge it. Judge the \
subject the question depends on, not every word: a generic noun that is not \
the subject ("a lawsuit", "investors") needs no name.

"ok" is false if any entity the question depends on is not identifiable.

Return ONLY a JSON array, one object per question, no markdown:
[{"index": 1, "entities": [{"name": "...", "identifiable": true, \
"why": "short reason"}], "ok": true}]
"""

# Answer budget per question, on top of the shared headroom.
TOKENS_PER_QUESTION = 160


@dataclass(frozen=True, slots=True)
class Verdict:
    """One question's verdict."""

    ok: bool
    entities: list[dict[str, Any]] = field(default_factory=list)

    @property
    def unclear(self) -> list[dict[str, Any]]:
        return [e for e in self.entities if e.get("identifiable") is False]

    def note(self) -> str:
        """``ambiguous entity: Mariam (first name only)``."""
        named = [
            f"{e['name']} ({e['why']})" if e.get("why") else str(e["name"])
            for e in self.unclear
            if e.get("name")
        ]
        return f"{AMBIGUOUS_ENTITY}: {'; '.join(named)}" if named else AMBIGUOUS_ENTITY


def shown(key: str, pair: Pair) -> str:
    """What the check sees of a question: the topic of an explanation, the
    sentence of a fill-in, the statements of a two-truths item, otherwise the
    question with its options."""
    if key == "tiered_explanation":
        topic = str(pair.meta.get("topic") or "")
        if topic:
            return f"Topic: {topic}"
    text = pair.question
    if text.startswith(FILL_IN_PREFIX):
        return text[len(FILL_IN_PREFIX) :].strip()
    if text.startswith(TTIL_HEAD):
        return "Statements:" + text[len(TTIL_HEAD) :]
    for tier in TIERS.values():
        text = text.replace(tier["instruction"], "")
    return text.strip()


def user_prompt(texts: list[str]) -> str:
    """The questions, numbered from 1."""
    body = "\n\n".join(f"{i}. {text}" for i, text in enumerate(texts, start=1))
    return f"Questions:\n\n{body}"


def parse(raw: str, count: int) -> dict[int, Verdict]:
    """Verdicts by 0-based question index; a question the reply leaves out is
    absent.

    Raises:
        LLMError: the reply holds no readable verdict
    """
    out: dict[int, Verdict] = {}
    for item in parse_json_list(raw):
        index = item.get("index")
        ok = item.get("ok")
        if not isinstance(index, int) or isinstance(index, bool):
            continue
        if not 1 <= index <= count or not isinstance(ok, bool):
            continue
        entities = [
            {
                "name": str(e.get("name") or ""),
                "identifiable": e.get("identifiable")
                if isinstance(e.get("identifiable"), bool)
                else None,
                "why": str(e.get("why") or ""),
            }
            for e in item.get("entities") or []
            if isinstance(e, dict)
        ]
        out[index - 1] = Verdict(ok=ok, entities=entities)
    if not out:
        raise LLMError("the entity check reply holds no verdict")
    return out
