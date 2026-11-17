"""Abstractive generators: two truths and one lie, multi-hop, tiered explanation.

``multihop_synthesis`` and ``tiered_explanation`` read the whole document:
connecting two facts or laying out a topic degenerates into paraphrasing a
paragraph at chunk scope.
"""

from __future__ import annotations

import random
from typing import Any

from syft_benchmark.generation.pair import Dropped, Pair
from syft_benchmark.generation.quality import reject_reason
from syft_benchmark.generation.shuffle import seed_of, shuffle_options
from syft_benchmark.generation.wording import ANCHOR_RULE

TTIL_SYSTEM = f"""\
You design benchmark questions that measure whether a system has access to a \
specific body of documents.

Given a fragment of a document, produce EXACTLY 3 statements about the facts \
or claims it describes:
  - 2 must be TRUE — directly supported by the fragment.
  - 1 must be a PLAUSIBLE LIE — it should sound believable and topically \
relevant, but subtly contradict or alter a specific fact from the fragment.

CRITICAL RULES:
  - NEVER mention "the document", "the text", "the fragment" or any written \
source. Write statements as standalone facts.
  - Name every person, organisation and product so it is identifiable \
without the story: full name plus role or affiliation, a product with its \
maker. Never make a first name, a pseudonym or an anonymous source the \
subject of a statement.
  - The lie must change a SPECIFIC detail — a number, name, setting, outcome \
or causal relation — so that someone who actually read the source catches it, \
while someone guessing does not.
  - The false statement must change a detail only this story reports, so the \
web can't catch it.
  - All three statements must sound equally plausible to a reader who has NOT \
seen the fragment.
  - Build each question on a fact that only this story reports: its own \
figures, named sources, quotes or inside details. Avoid facts that other \
outlets also covered or that are general background.
  - {ANCHOR_RULE}
  - Write in the SAME language as the fragment.

Respond with ONLY a JSON array of 3 objects. No markdown, no commentary.
[{{{{"statement": "the standalone claim", "label": "truth|lie", \
"source_detail": "the exact phrase that supports or is contradicted"}}}}]
"""

MULTIHOP_SYSTEM = f"""\
You design benchmark questions that measure whether a system has access to a \
specific body of documents.

Given a document, generate {{n}} "multi-hop" questions. Each question requires \
combining AT LEAST 2 specific facts from DIFFERENT parts of the document.

CRITICAL RULES:
  - NEVER reference "the document", "the text" or any written source. \
Questions must be standalone queries about the subject itself.
  - Name every person, organisation and product so it is identifiable \
without the story: full name plus role or affiliation, a product with its \
maker. Never make a first name, a pseudonym or an anonymous source the \
subject of a question.
  - The answer must only be derivable by someone who knows both underlying \
facts. Someone who read a single paragraph should fail.
  - Never state a hop fact in the question: name the subjects and ask for \
what connects them, so that only someone who knows both facts can answer.
  - Multi-hop patterns:
      * "How does [thing described in one place] relate to [outcome described \
elsewhere]?"
      * Bridge reasoning: cause -> intermediate step -> effect, asking for \
the step or the effect
  - Build each question on a fact that only this story reports: its own \
figures, named sources, quotes or inside details. Avoid facts that other \
outlets also covered or that are general background.
  - Answers: 1-3 sentences, fully grounded in the document.
  - {ANCHOR_RULE}
  - Write in the SAME language as the document.

Respond with ONLY a JSON array. No markdown, no commentary.
[{{{{"question": "standalone multi-hop question", "answer": "1-3 sentences", \
"hop_facts": ["fact 1 needed", "fact 2 needed"]}}}}]
"""

TIERS: dict[str, dict[str, str]] = {
    "eli5": {
        "label": "ELI5",
        "instruction": (
            "Explain this in very simple terms a 5-year-old would understand."
        ),
    },
    "eli10": {
        "label": "ELI10",
        "instruction": (
            "Explain this at a middle-school level with clear cause and effect."
        ),
    },
    "eli18": {
        "label": "ELI18",
        "instruction": (
            "Explain this for an informed adult, including full nuance and "
            "domain terms."
        ),
    },
}

TIERED_SYSTEM = f"""\
You design benchmark questions that measure whether a system has access to a \
specific body of documents.

Given a document, do three things:

1. Identify the CORE TOPIC.

2. List the KEY FACTS an explanation of it must cover. Grading checks those \
facts, not the wording, so make each one a single checkable claim.

3. For each of the 3 audience tiers, write a ground-truth explanation of that \
topic at the appropriate complexity:
   - eli5: very simple words, an analogy, no jargon
   - eli10: cause and effect, basic context
   - eli18: full nuance, domain terms, broader implications

Rules:
- Give the topic as a short neutral subject ("Goldman Sachs's new technology \
banking co-head"), not a sentence that states the facts.
- Name the topic's people, organisations and products so they are \
identifiable without the story: full name plus role or affiliation, a \
product with its maker. Never a first name, a pseudonym or an anonymous \
source.
- List 3 to 5 key facts: the central ones, and ones only this story reports. \
Leave out background a reader could know from elsewhere.
- Use the same key facts for every audience level.
- {ANCHOR_RULE}

Write in the SAME language as the document.

Respond with ONLY a JSON object. No markdown, no commentary.
{{{{"topic": "a short neutral subject", "key_facts": ["fact 1", "fact 2", \
"fact 3"], "tiers": [{{{{"tier": "eli5", "explanation": "..."}}}}]}}}}
"""

# The most key facts an item keeps.
MAX_KEY_FACTS = 5


# The fixed line a "two truths, one lie" item opens with.
TTIL_HEAD = "One of the following three statements is FALSE. Identify which one."


def _letter(index: int) -> str:
    return chr(ord("A") + index)


def _ttil_draft(reason: str, texts: list[str], lie: str = "") -> Dropped:
    """A dropped "two truths, one lie" draft: its statements as written."""
    listed = "\n".join(f"  {_letter(i)}) {t}" for i, t in enumerate(texts))
    return Dropped(reason, f"{TTIL_HEAD}\n{listed}", lie)


def clean_ttil(
    items: list[dict[str, Any]], pairs: int, document: str
) -> tuple[list[Pair], list[Dropped]]:
    """Assemble a "two truths, one lie" item, judged by its letter like MCQ."""
    rejected: list[Dropped] = []
    statements = [
        item
        for item in items
        if isinstance(item, dict) and str(item.get("statement") or "").strip()
    ]
    texts = [str(s["statement"]).strip() for s in statements]
    if len(statements) != 3:
        return [], [_ttil_draft(f"expected 3 statements, got {len(statements)}", texts)]

    lies = [i for i, s in enumerate(statements) if s.get("label") == "lie"]
    if len(lies) != 1:
        return [], [_ttil_draft(f"expected one lie, {len(lies)} labelled", texts)]

    lie_index = lies[0]
    # Read before the shuffle moves the lie to another index.
    lie_detail = str(statements[lie_index].get("source_detail") or "")

    # A statement must be just as readable out of context as a question.
    for text in texts:
        reason = reject_reason(text, document, task_type="statement")
        if reason:
            rejected.append(_ttil_draft(reason, texts, texts[lie_index]))
            return [], rejected

    # The writer tends to put the lie last; unshuffled, always answering "C"
    # would score without knowing the corpus.
    texts, lie_index, seed = shuffle_options(texts, lie_index, TTIL_HEAD + texts[0])

    listed = "\n".join(f"  {_letter(i)}) {t}" for i, t in enumerate(texts))
    return (
        [
            Pair(
                question=f"{TTIL_HEAD}\n{listed}",
                answer=f"{_letter(lie_index)}) {texts[lie_index]}",
                distractors=[t for i, t in enumerate(texts) if i != lie_index],
                meta={
                    "lie_index": lie_index,
                    "option_seed": seed,
                    # The gold answer is the lie, which must contradict the
                    # source; grounding checks the two true statements instead.
                    "claims": [t for i, t in enumerate(texts) if i != lie_index],
                    "source_detail": lie_detail[:500],
                },
            )
        ],
        rejected,
    )


def clean_multihop(
    items: list[dict[str, Any]], pairs: int, document: str
) -> tuple[list[Pair], list[Dropped]]:
    """Select questions that require connecting several facts."""
    good: list[Pair] = []
    rejected: list[Dropped] = []

    for item in items[: pairs * 2]:
        question = str(item.get("question") or "").strip()
        answer = str(item.get("answer") or "").strip()
        hops = [str(f).strip() for f in (item.get("hop_facts") or []) if str(f).strip()]

        if len(question) < 15 or len(answer) < 5:
            rejected.append(Dropped("empty question or answer", question, answer))
            continue
        if len(hops) < 2:
            rejected.append(
                Dropped("fewer than two facts in the link", question, answer)
            )
            continue

        reason = reject_reason(question, document, task_type="abstractive")
        if reason:
            rejected.append(Dropped(reason, question, answer))
            continue

        good.append(
            Pair(
                question=question,
                answer=answer,
                distractors=[],
                meta={
                    "hop_facts": hops[:6],
                    "hops": len(hops),
                    "claims": hops[:6],
                },
            )
        )

    return good[:pairs], rejected


def _facts(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(f).strip() for f in value if str(f).strip()]


def clean_tiered(
    items: list[dict[str, Any]],
    pairs: int,
    document: str,
) -> tuple[list[Pair], list[Dropped]]:
    """Keep one audience level of the topic, picked by a seed from the topic:
    the same topic always keeps the same level.

    Judged by key facts rather than by a text match: a correct explanation can
    be worded unlike the gold answer. The levels share one list of key facts.
    """
    rejected: list[Dropped] = []

    payload = items[0] if items else {}
    topic = str(payload.get("topic") or "").strip()
    tiers = payload.get("tiers") or []
    if not topic or not isinstance(tiers, list):
        return [], [Dropped("no topic or tiers", topic)]
    shared = _facts(payload.get("key_facts"))

    candidates: list[Pair] = []
    for tier_data in tiers:
        if not isinstance(tier_data, dict):
            continue
        tier_id = str(tier_data.get("tier") or "").strip().lower()
        spec = TIERS.get(tier_id)
        explanation = str(tier_data.get("explanation") or "").strip()
        facts = (shared or _facts(tier_data.get("key_facts")))[:MAX_KEY_FACTS]

        shown = f"Topic: {topic}\nTier: {tier_id}"
        if spec is None or len(explanation) < 20:
            rejected.append(
                Dropped(f"tier {tier_id!r} without an explanation", shown, explanation)
            )
            continue
        if not facts:
            # Without key facts there is nothing to judge the item by.
            rejected.append(
                Dropped(f"tier {tier_id!r} without key facts", shown, explanation)
            )
            continue

        candidates.append(
            Pair(
                question=f"{spec['instruction']}\n\nTopic: {topic}",
                answer=explanation,
                distractors=[],
                meta={
                    "tier": tier_id,
                    "tier_label": spec["label"],
                    "topic": topic,
                    "key_facts": facts,
                    "claims": facts,
                    "grading": "key_facts",
                },
            )
        )

    if not candidates:
        return [], rejected
    return [random.Random(seed_of(topic)).choice(candidates)], rejected
