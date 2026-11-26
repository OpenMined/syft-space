"""The entity check: does a question name its subject so anyone can tell who
or what is meant?

A question built on "Mariam, who asked to be identified only by her first
name" has no referent a reader or the web check can pin down. The question
writer is asked again, in a fresh call with no article, to list the people,
organisations, products, places, events and documents each question of a
unit names and to say whether each is identifiable from the question alone,
with the kind of problem when it is not.

Two rules are kept here rather than left to the model:

  * A reference is never unidentifiable for being unknown to the model:
    news is about new names. An entity rejected as unfamiliar (its ``issue``,
    or its reason reads so) is counted identifiable.
  * One reference, one decision in a build (``Memory``): the first verdict on
    a reference is shown to later calls and overrides a different one.
"""

from __future__ import annotations

import re
import threading
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from syft_benchmark.generation.abstractive import TIERS, TTIL_HEAD
from syft_benchmark.generation.extractive import FILL_IN_PREFIX
from syft_benchmark.generation.gold import normalize
from syft_benchmark.generation.pair import Pair
from syft_benchmark.llm import LLMError, parse_json_list

# ``meta`` key of a pair's check record.
META = "entity_check"
# The build's drop reason and the start of a rejected pair's note.
AMBIGUOUS_ENTITY = "ambiguous entity"

# An entity's ``issue``: why it is not identifiable.
FIRST_NAME = "first_name"
SURNAME_ONLY = "surname_only"
ABBREVIATION = "abbreviation"
GENERIC = "generic"
NO_YEAR = "no_year"
NO_OUTLET = "no_outlet"
UNFAMILIAR = "unfamiliar"
ISSUES = (
    FIRST_NAME,
    SURNAME_ONLY,
    ABBREVIATION,
    GENERIC,
    NO_YEAR,
    NO_OUTLET,
    UNFAMILIAR,
)

# An entity's ``overridden``: why its verdict is not the model's.
OVERRIDDEN_UNFAMILIAR = "unfamiliar is not unidentifiable"
OVERRIDDEN_EARLIER = "the build's earlier decision"

SYSTEM = """\
You review benchmark questions before they are used. A question is only \
usable if a reader who sees nothing but the question knows exactly which \
real-world person, organisation, product, place, event or document it is about.

For each numbered question, list every actor and entity it names or refers \
to, and decide for each whether it is identifiable from the question text \
alone. Give "name" as the question writes it, with any role, expansion or \
affiliation attached ("Ana Pérez, Uruguay's minister of economy", "ASSE").

Identifiable: a full name ("Donald Trump"), a name plus a distinguishing role \
or affiliation ("Sarah Chen, the CFO of Stripe"), a specific organisation \
("the European Central Bank"), a specific product with its maker and model \
("Apple's iPhone 16 Pro"), a writer or piece by its outlet ("WIRED's Nena \
Farrell", "WIRED's review of Amazon's Kindle Aluminum"), an event with its \
date ("the selloff in Singapore bank stocks in the week to Oct 10, 2026"), \
an abbreviation spelled out ("the Administración de los Servicios de Salud \
del Estado (ASSE)") or one any general reader knows (UN, NATO, FIFA, NASA, EU).
Not identifiable, with its issue:
  - "first_name": a first name only, a pseudonym, an anonymous source;
  - "surname_only": a surname with no first name and no role ("Pérez said", \
"the Sánchez report");
  - "abbreviation": an abbreviation or acronym the question does not spell \
out and a general reader would not know (ASSE, MPP, Ursea, INAU);
  - "generic": "a startup", "the company", "a researcher", "a local \
official", "her group" without a named owner, a product with no maker;
  - "no_outlet": "the reviewer" or "the author" with no outlet;
  - "no_year": an event placed only by "last month", or a date or month \
without its year.

Judge only whether the reference is unambiguous, never whether you know it. \
News is about new names: a company, product, film, person or place you have \
never heard of is identifiable when the question gives its full name and \
what it is. Never mark an entity unidentifiable because you do not recognise \
it, cannot verify it, or think it may not exist.

A blank "______" is the answer to be filled in: do not judge it. Judge the \
subject the question depends on, not every word: a generic noun that is not \
the subject ("a lawsuit", "investors") needs no name.

If the questions are followed by earlier decisions of this review, give the \
same decision to the same reference.

"ok" is false if any entity the question depends on is not identifiable.

Return ONLY a JSON array, one object per question, no markdown:
[{"index": 1, "entities": [{"name": "...", "identifiable": true, \
"issue": "", "why": "short reason"}], "ok": true}]
"""

# Answer budget per question, on top of the shared headroom.
TOKENS_PER_QUESTION = 160

# How many earlier decisions one call is shown at most.
MAX_EARLIER = 30

# A reason that says the model does not know the entity, not that the question
# fails to name it.
_UNFAMILIAR_WHY = re.compile(
    r"not (?:a )?(?:widely |well[- ]|commonly |publicly )?(?:recogni[sz]ed|known)"
    r"|unrecogni[sz]ed|unfamiliar|not familiar|never heard"
    r"|(?:cannot|can't|could not|couldn't|unable to) (?:be )?(?:verif|confirm)"
    r"|unverifi|(?:may|might) not exist|does(?: not|n't) exist|no such"
    r"|fictional|fictitious|made[- ]up|not a real",
    re.IGNORECASE,
)
# Issues that name a real defect: an unfamiliar-sounding reason does not
# undo them.
_DEFECTS = frozenset(set(ISSUES) - {UNFAMILIAR})


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


def _recount(ok: bool, entities: list[dict[str, Any]], changed: bool) -> Verdict:
    """The verdict on ``entities``: the model's ``ok`` unless an entity's
    verdict was overridden, then whether none is left unidentifiable."""
    if changed:
        ok = not any(e.get("identifiable") is False for e in entities)
    return Verdict(ok=ok, entities=entities)


def _reference(name: str) -> str:
    """A reference as decisions are kept: normalised, without the quotes or
    punctuation around it."""
    return normalize(name).strip(" \"'.,;:()[]¿?¡!")


class Memory:
    """The entity check's decisions in one build, by reference: the first
    verdict on a reference stands for the rest of the build.

    Shared by the build's worker threads.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._decided: dict[str, dict[str, Any]] = {}

    def earlier(self, texts: Sequence[str]) -> list[dict[str, Any]]:
        """The decisions on references the texts contain, at most
        ``MAX_EARLIER``."""
        joined = normalize(" ".join(texts))
        with self._lock:
            found = [
                decided
                for key, decided in self._decided.items()
                if re.search(rf"(?<!\w){re.escape(key)}(?!\w)", joined)
            ]
        return found[:MAX_EARLIER]

    def settle(self, verdict: Verdict) -> Verdict:
        """``verdict`` with earlier decisions applied; its new references
        remembered."""
        entities: list[dict[str, Any]] = []
        changed = False
        with self._lock:
            for entity in verdict.entities:
                key = _reference(str(entity.get("name") or ""))
                said = entity.get("identifiable")
                if not key or not isinstance(said, bool):
                    entities.append(entity)
                    continue
                decided = self._decided.get(key)
                if decided is None:
                    self._decided[key] = {
                        "name": entity["name"],
                        "identifiable": said,
                        "why": entity.get("why") or "",
                    }
                elif decided["identifiable"] != said:
                    entity = {
                        **entity,
                        "identifiable": decided["identifiable"],
                        "why": decided["why"] or entity.get("why") or "",
                        "overridden": OVERRIDDEN_EARLIER,
                    }
                    changed = True
                entities.append(entity)
        return _recount(verdict.ok, entities, changed)


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


def user_prompt(texts: list[str], earlier: Sequence[dict[str, Any]] = ()) -> str:
    """The questions, numbered from 1, and the earlier decisions on the
    references they contain."""
    body = "\n\n".join(f"{i}. {text}" for i, text in enumerate(texts, start=1))
    prompt = f"Questions:\n\n{body}"
    if earlier:
        lines = [
            f"- {d['name']}: "
            + ("identifiable" if d["identifiable"] else "not identifiable")
            + (f" ({d['why']})" if d.get("why") else "")
            for d in earlier
        ]
        prompt += "\n\nEarlier decisions of this review:\n" + "\n".join(lines)
    return prompt


def _entity(raw: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    """One listed entity, and whether its verdict was overridden: an entity
    rejected only for being unfamiliar is identifiable."""
    said = raw.get("identifiable")
    issue = str(raw.get("issue") or "").strip().lower()
    entity: dict[str, Any] = {
        "name": str(raw.get("name") or ""),
        "identifiable": said if isinstance(said, bool) else None,
        "issue": issue if issue in ISSUES else "",
        "why": str(raw.get("why") or ""),
    }
    unfamiliar = issue == UNFAMILIAR or (
        issue not in _DEFECTS and bool(_UNFAMILIAR_WHY.search(entity["why"]))
    )
    if said is False and unfamiliar:
        entity["identifiable"] = True
        entity["overridden"] = OVERRIDDEN_UNFAMILIAR
        return entity, True
    return entity, False


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
        entities: list[dict[str, Any]] = []
        changed = False
        for listed in item.get("entities") or []:
            if not isinstance(listed, dict):
                continue
            entity, overridden = _entity(listed)
            entities.append(entity)
            changed = changed or overridden
        out[index - 1] = _recount(ok, entities, changed)
    if not out:
        raise LLMError("the entity check reply holds no verdict")
    return out
