"""Abstractive generators: items that demand understanding.

A port from LiveTruth with one substantive change to each: there the source was
a news article and what was tested was whether the model knew paid content. Our
source is a private corpus, and a RAG endpoint is tested as well, so the wordings
speak of "the document" instead of "the article", and the item language is taken
from the language of the chunk.

Two generators work over the whole document rather than over a chunk, and that is
no trifle: `multihop_synthesis` requires connecting at least two facts, and
`tiered_explanation` requires laying out the core of a topic. On a single chunk
both degenerate into paraphrasing a paragraph.
"""

from __future__ import annotations

import random
from typing import Any

from syft_benchmark.generation.pair import Pair
from syft_benchmark.generation.quality import reject_reason
from syft_benchmark.generation.shuffle import seed_of, shuffle_options
from syft_benchmark.generation.wording import ANCHOR_RULE

# ---------------------------------------------------------------------------
# two_truths_one_lie
# ---------------------------------------------------------------------------
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

# ---------------------------------------------------------------------------
# multihop_synthesis
# ---------------------------------------------------------------------------
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

# ---------------------------------------------------------------------------
# tiered_explanation
# ---------------------------------------------------------------------------
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


def clean_ttil(
    items: list[dict[str, Any]], pairs: int, document: str
) -> tuple[list[Pair], list[str]]:
    """Assemble a "two truths, one lie" item.

    Judged by the letter, like MCQ: a judge is not needed here and would only add
    noise.
    """
    rejected: list[str] = []
    statements = [
        item
        for item in items
        if isinstance(item, dict) and str(item.get("statement") or "").strip()
    ]
    if len(statements) != 3:
        return [], [f"expected 3 statements, got {len(statements)}"]

    lies = [i for i, s in enumerate(statements) if s.get("label") == "lie"]
    if len(lies) != 1:
        return [], [f"expected one lie, {len(lies)} labelled"]

    lie_index = lies[0]
    texts = [str(s["statement"]).strip() for s in statements]
    # The detail about the lie is taken BEFORE shuffling: afterwards the index is
    # different, and the note would move to someone else statement.
    lie_detail = str(statements[lie_index].get("source_detail") or "")

    # Statements are not a question, and the self-sufficiency requirement still
    # applies to them: "this solution" in a statement is just as unreadable out
    # of context.
    for text in texts:
        reason = reject_reason(text, document, task_type="statement")
        if reason:
            rejected.append(reason)
            return [], rejected

    # We shuffle: the generator numbers the statements in the order it produced
    # them, and the prompt asks for "two truths and one lie" — the lie settles in
    # last place, and the constant answer "C" gives an accuracy of 1.00 while
    # knowing nothing about the corpus.
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
                    # The gold answer here is the LIE, and checking it for support
                    # in the source is back to front: a good lie is obliged to
                    # contradict it. What has to follow from the chunk is the two
                    # true statements, and those are what go to screening.
                    "claims": [t for i, t in enumerate(texts) if i != lie_index],
                    "source_detail": lie_detail[:500],
                },
            )
        ],
        rejected,
    )


def clean_multihop(
    items: list[dict[str, Any]], pairs: int, document: str
) -> tuple[list[Pair], list[str]]:
    """Select questions that require connecting several facts."""
    good: list[Pair] = []
    rejected: list[str] = []

    for item in items[: pairs * 2]:
        question = str(item.get("question") or "").strip()
        answer = str(item.get("answer") or "").strip()
        hops = [str(f).strip() for f in (item.get("hop_facts") or []) if str(f).strip()]

        if len(question) < 15 or len(answer) < 5:
            rejected.append("empty question or answer")
            continue
        # Fewer than two facts is an ordinary question, and it has no place in
        # multihop.
        if len(hops) < 2:
            rejected.append("fewer than two facts in the link")
            continue

        reason = reject_reason(question, document, task_type="abstractive")
        if reason:
            rejected.append(reason)
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
    *,
    rng: random.Random | None = None,
) -> tuple[list[Pair], list[str]]:
    """Keep one audience level of the topic, picked at random.

    Judged by key facts rather than by a text match: an explanation can be
    correct and unlike the gold answer, and comparing prose with prose would mean
    punishing the wording. The levels share one list of key facts.

    Args:
        rng: Picks the level; None — seeded from the topic, so the same topic
            always keeps the same level
    """
    rejected: list[str] = []

    payload = items[0] if items else {}
    topic = str(payload.get("topic") or "").strip()
    tiers = payload.get("tiers") or []
    if not topic or not isinstance(tiers, list):
        return [], ["no topic or tiers"]
    shared = _facts(payload.get("key_facts"))

    candidates: list[Pair] = []
    for tier_data in tiers:
        if not isinstance(tier_data, dict):
            continue
        tier_id = str(tier_data.get("tier") or "").strip().lower()
        spec = TIERS.get(tier_id)
        explanation = str(tier_data.get("explanation") or "").strip()
        facts = (shared or _facts(tier_data.get("key_facts")))[:MAX_KEY_FACTS]

        if spec is None or len(explanation) < 20:
            rejected.append(f"tier {tier_id!r} without an explanation")
            continue
        if not facts:
            # Without key facts there is nothing to judge the item by: comparing
            # prose with prose is a lottery, not an assessment.
            rejected.append(f"tier {tier_id!r} without key facts")
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
    picker = rng or random.Random(seed_of(topic))
    return [picker.choice(candidates)], rejected
