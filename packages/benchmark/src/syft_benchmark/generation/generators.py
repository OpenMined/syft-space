"""The generator registry: each kind's prompt, unit scope, grading and cleaner.

``GENERATORS`` holds the masking, free-form, choice and control kinds. Prompts
are in English (small models follow English instructions more precisely); the
pair's language comes from the chunk, by the last rule of each prompt.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from syft_benchmark.config import ExpectedBehavior
from syft_benchmark.generation.abstractive import (
    MULTIHOP_SYSTEM,
    TIERED_SYSTEM,
    TTIL_SYSTEM,
    clean_multihop,
    clean_tiered,
    clean_ttil,
)
from syft_benchmark.generation.negative import (
    FALSE_PREMISE_SYSTEM,
    UNANSWERABLE_SYSTEM,
    clean_false_premise,
    clean_unanswerable,
)
from syft_benchmark.generation.pair import Dropped, Pair
from syft_benchmark.generation.quality import reject_reason
from syft_benchmark.generation.shuffle import LETTERS, shuffle_options
from syft_benchmark.generation.wording import ANCHOR_RULE
from syft_benchmark.sources import Chunk, Document

MAX_FRAGMENT_CHARS = 6000
MAX_DOCUMENT_CHARS = 12000

_RULES = f"""\
Rules:
1. Every question must be fully answerable from the fragment alone.
2. Questions must be standalone. Never write "the text", "the fragment", \
"the document", "the article" or "according to ...". Name the subject \
explicitly instead, so that the question still makes sense to someone who \
has never seen the fragment.
3. Name every person, organisation and product so it is identifiable \
without the story: full name plus role or affiliation ("Sarah Chen, the \
CFO of Stripe"), a product with its maker. Never make a first name, a \
pseudonym or an anonymous source the subject of a question; if the \
fragment names someone no better, ask about something else.
4. Never point at something with "this", "that", "these", "those" — no "this \
statement", "that decision", "these measures". The reader sees your question \
alone, with no earlier question to point back to. Name the thing instead.
5. The question must have exactly ONE correct answer. Do not ask "what did X \
say about Y" when X is quoted more than once, and do not ask for "one of the" \
several things: pin the question to a detail that identifies the answer.
6. Prefer concrete facts: numbers, names, dates, settings, causes, steps.
7. Build each question on a fact that only this story reports about a \
subject named as rule 3 says: its own \
figures, named sources, quotes or inside details. Avoid facts that other \
outlets also covered or that are general background.
8. Use only what the fragment states. Invent nothing.
9. {ANCHOR_RULE}
10. Write the question and the answer in the SAME language as the fragment.
"""

_QA_SYSTEM = f"""\
You build a question-answer benchmark for a private knowledge base. \
You are given ONE fragment of ONE document and must produce exactly {{n}} \
question-answer pairs.

{_RULES}11. The answer is short: one to three sentences.

Return ONLY a JSON array of {{n}} objects:
[{{{{"question": "...", "answer": "...", "difficulty": "easy|medium|hard"}}}}]
No markdown fences, no commentary.
"""

_MCQ_SYSTEM = f"""\
You build a multiple-choice benchmark for a private knowledge base. \
You are given ONE fragment of ONE document and must produce exactly {{n}} \
questions with four options each.

{_RULES}11. Exactly one option is correct; the other three are plausible but wrong \
according to the fragment.
12. The wrong options must sound right to someone who hasn't read the story, \
and each must be contradicted by it.

Return ONLY a JSON array of {{n}} objects:
[{{{{"question": "...", "options": {{{{"A": "...", "B": "...", "C": "...", \
"D": "..."}}}}, "correct": "A", "difficulty": "easy|medium|hard"}}}}]
No markdown fences, no commentary.
"""


Cleaner = Callable[[list[dict[str, Any]], int, str], tuple[list[Pair], list[Dropped]]]


class Scope(StrEnum):
    """What one writer call is fed."""

    CHUNK = "chunk"
    DOCUMENT = "document"


@dataclass(frozen=True, slots=True)
class Generator:
    """One way of building items out of a text.

    Args:
        key: The name in the CLI and in the database
        task_type: The item class; it sets both the screening rules and how
            the item is judged
        scope: What is fed in. Connecting two facts or laying out a topic
            needs the whole document: at chunk scope such items degenerate
            into paraphrase
        grading: What the answer is measured by. ``letter`` — the option
            letter, no judge; ``judge`` — a judge model; ``key_facts`` — the
            listed facts rather than a text match; ``behavior`` — the expected
            behaviour
        system: The system prompt; ``{n}`` is substituted with the item count
        clean: Parsing and screening of the model answer
        tokens_per_pair: The answer ceiling, reckoned per item
        expected: The correct behaviour. Ordinary items are built out of a
            chunk and are answerable; control items expect abstaining or
            refuting the premise, which changes both screening (no gold answer
            to ground) and judging
        single_item: The reply is one JSON object holding one item per unit,
            not an array of ``n`` items. Such an item is long, so its call
            starts from the shared answer ceiling
    """

    key: str
    task_type: str
    scope: Scope
    grading: str
    system: str
    clean: Cleaner
    tokens_per_pair: int
    expected: ExpectedBehavior = ExpectedBehavior.ANSWER
    single_item: bool = False

    @property
    def is_control(self) -> bool:
        """A control generator: builds questions with no answer in the corpus."""
        return self.expected is not ExpectedBehavior.ANSWER


def document_header(doc: Document) -> list[str]:
    """The lines every writer prompt opens with: title, outlet, author, date."""
    lines = [f"Document: {doc.title}"]
    if doc.source:
        lines.append(f"Outlet: {doc.source}")
    if doc.author:
        lines.append(f"Author: {doc.author}")
    if doc.published_at is not None:
        lines.append(f"Published: {doc.published_at.date().isoformat()}")
    return lines


def document_text(doc: Document) -> str:
    """The whole document — the pool the endpoint answers from."""
    return "\n\n".join(chunk.text for chunk in doc.chunks)


def writer_passage(doc: Document, chunk: Chunk | None) -> str:
    """The text a writer prompt shows: the chunk, or the whole document for a
    document-scope kind, each cut at its limit. Stored as the pair's ``context``."""
    if chunk is None:
        return document_text(doc)[:MAX_DOCUMENT_CHARS]
    return chunk.text[:MAX_FRAGMENT_CHARS]


def document_prompt(doc: Document, tasks: int) -> str:
    """The whole document and how many items are wanted from it."""
    header = "\n".join(document_header(doc))
    text = writer_passage(doc, None)
    return f'{header}\n\nText:\n"""\n{text}\n"""\n\nGenerate {tasks}.'


def user_prompt(doc: Document, chunk: Chunk, pairs: int) -> str:
    """The chunk and how many pairs are wanted from it."""
    lines = document_header(doc)
    if chunk.headings:
        lines.append(f"Section: {chunk.headings}")
    lines += [
        "",
        "Fragment:",
        '"""',
        writer_passage(doc, chunk),
        '"""',
        "",
        f"Generate exactly {pairs} pairs.",
    ]
    return "\n".join(lines)


def _clean_qa(
    items: list[dict[str, Any]], pairs: int, document: str
) -> tuple[list[Pair], list[Dropped]]:
    """Select the valid free-answer pairs."""
    good: list[Pair] = []
    rejected: list[Dropped] = []
    for item in items[: pairs * 2]:
        question = str(item.get("question") or "").strip()
        answer = str(item.get("answer") or "").strip()
        if len(question) < 10 or len(answer) < 2:
            rejected.append(Dropped("empty question or answer", question, answer))
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
                meta={"difficulty": str(item.get("difficulty") or "medium")},
            )
        )
    return good[:pairs], rejected


def _mcq_draft(reason: str, question: str, options: Any, correct: str) -> Dropped:
    """A dropped multiple-choice draft: the question with its options listed."""
    if not isinstance(options, dict):
        return Dropped(reason, question)
    listed = [f"  {key}) {value}" for key, value in sorted(options.items())]
    answer = f"{correct}) {options[correct]}" if correct in options else ""
    return Dropped(reason, "\n".join([question, *listed]), answer)


def _clean_mcq(
    items: list[dict[str, Any]], pairs: int, document: str
) -> tuple[list[Pair], list[Dropped]]:
    """Select the valid multiple-choice questions."""
    good: list[Pair] = []
    rejected: list[Dropped] = []
    for item in items[: pairs * 2]:
        question = str(item.get("question") or "").strip()
        options = item.get("options") or {}
        correct = str(item.get("correct") or "").strip().upper()[:1]
        if (
            len(question) < 10
            or not isinstance(options, dict)
            or len(options) != 4
            or correct not in options
        ):
            rejected.append(
                _mcq_draft(
                    "a question without four options or without a correct one",
                    question,
                    options,
                    correct,
                )
            )
            continue
        # The answer options make the question unambiguous by themselves, so only
        # self-sufficiency is checked here.
        reason = reject_reason(question, document, task_type="choice")
        if reason:
            rejected.append(_mcq_draft(reason, question, options, correct))
            continue
        # The writer puts the correct option in a predictable place; shuffled,
        # a correct answer cannot come from matching its favourite letter.
        ordered = [options[key] for key in sorted(options)]
        written_at = sorted(options).index(correct)
        values, at, seed = shuffle_options(ordered, written_at, question)

        letter = LETTERS[at]
        listed = "\n".join(f"  {LETTERS[i]}) {v}" for i, v in enumerate(values))
        good.append(
            Pair(
                question=f"{question}\n{listed}",
                answer=f"{letter}) {values[at]}",
                distractors=[
                    f"{LETTERS[i]}) {v}" for i, v in enumerate(values) if i != at
                ],
                meta={
                    "correct": letter,
                    "option_seed": seed,
                    "generator_correct": correct,
                    "difficulty": str(item.get("difficulty") or "medium"),
                },
            )
        )
    return good[:pairs], rejected


def reasons(rejected: Iterable[str]) -> str:
    """The screening reasons in one line: "a reference to the source x2, ..."."""
    counted = Counter(rejected)
    return ", ".join(
        reason if count == 1 else f"{reason} ×{count}"
        for reason, count in counted.most_common()
    )


GENERATORS: dict[str, Generator] = {
    # Span masking: the only kinds whose gold answer is a span of the text.
    # One call builds all three categories; they are stored as separate kinds.
    "named_entity_masking": Generator(
        key="named_entity_masking",
        task_type="extractive",
        scope=Scope.CHUNK,
        grading="judge",
        system="",  # the prompt is shared, see extractive.COMBINED_SYSTEM
        clean=_clean_qa,
        tokens_per_pair=90,
    ),
    "numeric_masking": Generator(
        key="numeric_masking",
        task_type="extractive",
        scope=Scope.CHUNK,
        grading="judge",
        system="",
        clean=_clean_qa,
        tokens_per_pair=90,
    ),
    "temporal_masking": Generator(
        key="temporal_masking",
        task_type="extractive",
        scope=Scope.CHUNK,
        grading="judge",
        system="",
        clean=_clean_qa,
        tokens_per_pair=90,
    ),
    "mcq": Generator(
        key="mcq",
        task_type="choice",
        scope=Scope.CHUNK,
        grading="letter",
        system=_MCQ_SYSTEM,
        clean=_clean_mcq,
        tokens_per_pair=280,
    ),
    "two_truths_one_lie": Generator(
        key="two_truths_one_lie",
        task_type="choice",
        scope=Scope.CHUNK,
        grading="letter",
        system=TTIL_SYSTEM,
        clean=clean_ttil,
        tokens_per_pair=420,
    ),
    "multihop_synthesis": Generator(
        key="multihop_synthesis",
        task_type="abstractive",
        scope=Scope.DOCUMENT,
        grading="judge",
        system=MULTIHOP_SYSTEM,
        clean=clean_multihop,
        tokens_per_pair=320,
    ),
    "tiered_explanation": Generator(
        key="tiered_explanation",
        task_type="abstractive",
        scope=Scope.DOCUMENT,
        grading="key_facts",
        system=TIERED_SYSTEM,
        clean=clean_tiered,
        tokens_per_pair=1400,
        single_item=True,
    ),
    # A free-form question with a short answer: the ordinary shape in which a
    # real user comes to the endpoint.
    "qa": Generator(
        key="qa",
        task_type="abstractive",
        scope=Scope.CHUNK,
        grading="judge",
        system=_QA_SYSTEM,
        clean=_clean_qa,
        tokens_per_pair=190,
    ),
    # The control set: no answer in the corpus. Without it only answering is
    # measured, not what the pair does when there is nothing to answer from.
    # Its labelling is verified against live retrieval (control.py).
    "unanswerable_property": Generator(
        key="unanswerable_property",
        task_type="negative",
        scope=Scope.CHUNK,
        grading="behavior",
        system=UNANSWERABLE_SYSTEM,
        clean=clean_unanswerable,
        tokens_per_pair=170,
        expected=ExpectedBehavior.ABSTAIN,
    ),
    "false_premise": Generator(
        key="false_premise",
        task_type="negative",
        scope=Scope.CHUNK,
        grading="judge",
        system=FALSE_PREMISE_SYSTEM,
        clean=clean_false_premise,
        tokens_per_pair=240,
        expected=ExpectedBehavior.CORRECT_PREMISE,
    ),
}

# Screened by the retrieval gate instead of gold-answer grounding.
CONTROL_KEYS = tuple(key for key, spec in GENERATORS.items() if spec.is_control)

# Built together: one call gives all three categories.
EXTRACTIVE_KEYS = ("named_entity_masking", "numeric_masking", "temporal_masking")

# Category in the model answer -> generator key.
EXTRACTIVE_CATEGORIES = {
    "named_entity": "named_entity_masking",
    "numeric": "numeric_masking",
    "temporal": "temporal_masking",
}


def enabled_generators(disabled: list[str] | None = None) -> tuple[str, ...]:
    """Every known generator key except the ``disabled`` ones, in registry order."""
    off = set(disabled or ())
    return tuple(key for key in GENERATORS if key not in off)
