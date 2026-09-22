"""Item types: a prompt plus the parsing of the model answer.

A port from `OMSyft/scripts/generate_qa.py`. Two generators: a free-form answer
and a choice of four options. The prompts are in English deliberately — a 4B
model follows an instruction noticeably more precisely in it, while the language
of the pair is set by rule 7 and taken from the language of the chunk.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Iterable
from dataclasses import dataclass
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
from syft_benchmark.generation.pair import Pair
from syft_benchmark.generation.quality import reject_reason
from syft_benchmark.generation.shuffle import LETTERS, shuffle_options
from syft_benchmark.sources import Chunk, Document

MAX_FRAGMENT_CHARS = 6000
MAX_DOCUMENT_CHARS = 12000

_RULES = """\
Rules:
1. Every question must be fully answerable from the fragment alone.
2. Questions must be standalone. Never write "the text", "the fragment", \
"the document", "the article" or "according to ...". Name the subject \
explicitly instead, so that the question still makes sense to someone who \
has never seen the fragment.
3. Never point at something with "this", "that", "these", "those" — no "this \
statement", "that decision", "these measures". The reader sees your question \
alone, with no earlier question to point back to. Name the thing instead.
4. The question must have exactly ONE correct answer. Do not ask "what did X \
say about Y" when X is quoted more than once, and do not ask for "one of the" \
several things: pin the question to a detail that identifies the answer.
5. Prefer concrete facts: numbers, names, dates, settings, causes, steps.
6. Use only what the fragment states. Invent nothing.
7. Write the question and the answer in the SAME language as the fragment.
"""

_QA_SYSTEM = f"""\
You build a question-answer benchmark for a private knowledge base. \
You are given ONE fragment of ONE document and must produce exactly {{n}} \
question-answer pairs.

{_RULES}8. The answer is short: one to three sentences.

Return ONLY a JSON array of {{n}} objects:
[{{{{"question": "...", "answer": "...", "difficulty": "easy|medium|hard"}}}}]
No markdown fences, no commentary.
"""

_MCQ_SYSTEM = f"""\
You build a multiple-choice benchmark for a private knowledge base. \
You are given ONE fragment of ONE document and must produce exactly {{n}} \
questions with four options each.

{_RULES}8. Exactly one option is correct; the other three are plausible but wrong \
according to the fragment.

Return ONLY a JSON array of {{n}} objects:
[{{{{"question": "...", "options": {{{{"A": "...", "B": "...", "C": "...", \
"D": "..."}}}}, "correct": "A", "difficulty": "easy|medium|hard"}}}}]
No markdown fences, no commentary.
"""


Cleaner = Callable[[list[dict[str, Any]], int, str], tuple[list[Pair], list[str]]]


@dataclass(frozen=True, slots=True)
class Generator:
    """One way of building items out of a text.

    Args:
        key: The name in the CLI and in the database
        task_type: The item class — it determines both the screening rules and
            how the item is judged afterwards
        scope: What is fed in. ``chunk`` — one chunk; ``document`` — the whole
            document. This is not a performance setting: you cannot connect two
            facts or lay out the core of a topic from a single paragraph, such
            items degenerate into paraphrase at chunk scope
        grading: What the answer is measured by. ``letter`` — matching the
            option letter, no judge needed; ``judge`` — a judge model;
            ``key_facts`` — checking the listed facts rather than a text match
        system: The system prompt; ``{n}`` is substituted with the item count
        clean: Parsing and screening of the model answer
        tokens_per_pair: The answer ceiling, reckoned per item
        needs_llm: False only on the spaCy path of the extractive generators
        expected: What counts as the correct behaviour for such an item. For all
            the ordinary generators it is to answer: the item was built OUT OF a
            chunk and is therefore answerable. For the control ones it is to
            abstain or to refute the premise, and that changes both the screening
            (there is no gold answer, nothing to ground) and the judging
    """

    key: str
    task_type: str
    scope: str
    grading: str
    system: str
    clean: Cleaner
    tokens_per_pair: int
    needs_llm: bool = True
    expected: ExpectedBehavior = ExpectedBehavior.ANSWER

    @property
    def is_control(self) -> bool:
        """A control generator: builds questions with no answer in the corpus."""
        return self.expected is not ExpectedBehavior.ANSWER


def user_prompt(doc: Document, chunk: Chunk, pairs: int) -> str:
    """The chunk and how many pairs are wanted from it."""
    lines = [f"Document: {doc.title}"]
    if chunk.headings:
        lines.append(f"Section: {chunk.headings}")
    lines += [
        "",
        "Fragment:",
        '"""',
        chunk.text[:MAX_FRAGMENT_CHARS],
        '"""',
        "",
        f"Generate exactly {pairs} pairs.",
    ]
    return "\n".join(lines)


def _clean_qa(
    items: list[dict[str, Any]], pairs: int, document: str
) -> tuple[list[Pair], list[str]]:
    """Select the valid free-answer pairs."""
    good: list[Pair] = []
    rejected: list[str] = []
    # We take extra: some will be filtered out, and it is better to have a choice.
    for item in items[: pairs * 2]:
        question = str(item.get("question") or "").strip()
        answer = str(item.get("answer") or "").strip()
        if len(question) < 10 or len(answer) < 2:
            rejected.append("empty question or answer")
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
                meta={"difficulty": str(item.get("difficulty") or "medium")},
            )
        )
    return good[:pairs], rejected


def _clean_mcq(
    items: list[dict[str, Any]], pairs: int, document: str
) -> tuple[list[Pair], list[str]]:
    """Select the valid multiple-choice questions."""
    good: list[Pair] = []
    rejected: list[str] = []
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
            rejected.append("a question without four options or without a correct one")
            continue
        # The answer options make the question unambiguous by themselves, so only
        # self-sufficiency is checked here.
        reason = reject_reason(question, document, task_type="choice")
        if reason:
            rejected.append(reason)
            continue
        # We shuffle rather than take the generator order: the model numbers the
        # options as it pleases, and the correct one ends up in a predictable
        # place. Then "a correct answer without access to the corpus" would mean
        # not a leak but a match with the generator favourite letter.
        ordered = [options[key] for key in sorted(options)]
        was = sorted(options).index(correct)
        values, now, seed = shuffle_options(ordered, was, question)

        letter = LETTERS[now]
        listed = "\n".join(f"  {LETTERS[i]}) {v}" for i, v in enumerate(values))
        good.append(
            Pair(
                question=f"{question}\n{listed}",
                answer=f"{letter}) {values[now]}",
                distractors=[
                    f"{LETTERS[i]}) {v}" for i, v in enumerate(values) if i != now
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
    # --- extractive: span masking ----------------------------------------
    # The only class where the gold answer cannot be invented: it is cut out of
    # the text. The three categories are built by one call (or one spaCy pass)
    # but live separately in the database — their numbers are about different things.
    "named_entity_masking": Generator(
        key="named_entity_masking",
        task_type="extractive",
        scope="chunk",
        grading="judge",
        system="",  # the prompt is shared, see extractive.COMBINED_SYSTEM
        clean=_clean_qa,
        tokens_per_pair=90,
        needs_llm=False,
    ),
    "numeric_masking": Generator(
        key="numeric_masking",
        task_type="extractive",
        scope="chunk",
        grading="judge",
        system="",
        clean=_clean_qa,
        tokens_per_pair=90,
        needs_llm=False,
    ),
    "temporal_masking": Generator(
        key="temporal_masking",
        task_type="extractive",
        scope="chunk",
        grading="judge",
        system="",
        clean=_clean_qa,
        tokens_per_pair=90,
        needs_llm=False,
    ),
    # --- abstractive ------------------------------------------------------
    "mcq": Generator(
        key="mcq",
        task_type="choice",
        scope="chunk",
        grading="letter",
        system=_MCQ_SYSTEM,
        clean=_clean_mcq,
        tokens_per_pair=280,
    ),
    "two_truths_one_lie": Generator(
        key="two_truths_one_lie",
        task_type="choice",
        scope="chunk",
        grading="letter",
        system=TTIL_SYSTEM,
        clean=clean_ttil,
        tokens_per_pair=420,
    ),
    "multihop_synthesis": Generator(
        key="multihop_synthesis",
        task_type="abstractive",
        scope="document",
        grading="judge",
        system=MULTIHOP_SYSTEM,
        clean=clean_multihop,
        tokens_per_pair=320,
    ),
    "tiered_explanation": Generator(
        key="tiered_explanation",
        task_type="abstractive",
        scope="document",
        grading="key_facts",
        system=TIERED_SYSTEM,
        clean=clean_tiered,
        # The longest item of them all: three explanations of differing levels
        # plus a list of facts, and all in one JSON object. 900 was enough for a
        # 4B model; on a live run Opus broke off in the middle of the first line.
        # Raising it a third time is not what fixed that — the pipeline starts
        # this one generator from the shared answer ceiling, and a cut-off call
        # is repeated with a larger budget. The number stays as the estimate it
        # always was.
        tokens_per_pair=1400,
    ),
    # --- our addition -----------------------------------------------------
    # A free-form question with a short answer. There is nothing like it in
    # LiveTruth: there, knowledge of paid content was tested, whereas we also need
    # the ordinary shape in which a real storefront user comes to the endpoint.
    "qa": Generator(
        key="qa",
        task_type="abstractive",
        scope="chunk",
        grading="judge",
        system=_QA_SYSTEM,
        clean=_clean_qa,
        tokens_per_pair=190,
    ),
    # --- the control set: there is NO answer in the corpus ----------------
    # Without these two the dataset consists of answerable questions only and
    # measures half the behaviour: what the pair does when there is no answer is
    # not measured at all. The labelling is verified by live retrieval (control.py)
    # — a negative without that check is an unfounded accusation of invention.
    "unanswerable_property": Generator(
        key="unanswerable_property",
        task_type="negative",
        scope="chunk",
        grading="behavior",
        system=UNANSWERABLE_SYSTEM,
        clean=clean_unanswerable,
        tokens_per_pair=170,
        expected=ExpectedBehavior.ABSTAIN,
    ),
    "false_premise": Generator(
        key="false_premise",
        task_type="negative",
        scope="chunk",
        grading="judge",
        system=FALSE_PREMISE_SYSTEM,
        clean=clean_false_premise,
        tokens_per_pair=240,
        expected=ExpectedBehavior.CORRECT_PREMISE,
    ),
}

# The control generators. Listed separately because they have their own road: a
# gate instead of gold-answer screening, and their own correct behaviour.
CONTROL_KEYS = tuple(key for key, spec in GENERATORS.items() if spec.is_control)

# The extractive ones are built together: one spaCy pass or one LLM call gives
# all three categories at once, and there is no reason to call the model three
# times over one chunk.
EXTRACTIVE_KEYS = ("named_entity_masking", "numeric_masking", "temporal_masking")

# The mapping "category in the model answer -> generator key".
EXTRACTIVE_CATEGORIES = {
    "named_entity": "named_entity_masking",
    "numeric": "numeric_masking",
    "temporal": "temporal_masking",
}

# By default ALL the generators work: each tests its own property, and choosing
# on the user behalf which property is uninteresting to them is wrong. They are
# switched off through disabled_generators — deliberately and by name.
DEFAULT_GENERATORS = tuple(GENERATORS)


def enabled_generators(disabled: list[str] | None = None) -> tuple[str, ...]:
    """The generators that should be run.

    Args:
        disabled: The names of the disabled ones, from the settings

    Returns:
        All the known ones except the disabled
    """
    off = set(disabled or ())
    return tuple(key for key in GENERATORS if key not in off)
