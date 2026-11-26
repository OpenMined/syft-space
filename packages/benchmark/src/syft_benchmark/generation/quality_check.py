"""The quality check: can a question be asked apart from its article, in any
language?

The patterns of ``quality.py`` are English and pass every other language
unscreened. This check asks a model instead, in one call per unit: the article
and the unit's questions, each with the checks that apply to its kind. The
model names the checks a question fails and why; a question that fails any is
rejected as written. A failed call or a question the reply leaves out keeps
the question.

The call sees the article, so it goes to the question writer's address
(``quality_check_model`` only swaps the model): it stays inside the same
perimeter as the writer.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Mapping
from contextlib import AbstractContextManager, nullcontext
from dataclasses import dataclass, field, replace
from typing import Any

from loguru import logger

from syft_benchmark.config import Settings
from syft_benchmark.generation import decisions, entities
from syft_benchmark.generation.generators import (
    MAX_DOCUMENT_CHARS,
    document_header,
    document_text,
    writer_passage,
)
from syft_benchmark.generation.pair import Pair
from syft_benchmark.llm import LLMError, Provider, cost, parse_json_list
from syft_benchmark.sources import Chunk, Document

# ``meta`` key of a pair's check record.
META = "quality_check"
# The build's drop reason and the start of a rejected pair's note.
POOR_QUALITY = "quality check"

SOURCE_REFERENCE = "source_reference"
UNANCHORED = "unanchored"
QUOTE = "quote"
UNSUPPORTED = "unsupported_wording"
SEVERAL_ANSWERS = "several_answers"
OBVIOUS = "obvious"

# How a failed check reads in a note.
LABELS: dict[str, str] = {
    SOURCE_REFERENCE: "refers to the source",
    UNANCHORED: "no antecedent",
    QUOTE: "a quote",
    UNSUPPORTED: "not what the article says",
    SEVERAL_ANSWERS: "several correct answers",
    OBVIOUS: "obvious without the article",
}

# Self-sufficiency is asked of every kind. A control question is meant to have
# no answer in the article, or to contradict it; a two-truths item holds a lie
# on purpose; an explanation is judged by its topic; so the checks on answer
# and wording are for the ordinary kinds that have one answer.
_STANDALONE = (SOURCE_REFERENCE, UNANCHORED)
CHECKS: dict[str, tuple[str, ...]] = {
    "named_entity_masking": (*_STANDALONE, QUOTE, OBVIOUS),
    "numeric_masking": (*_STANDALONE, QUOTE, OBVIOUS),
    "temporal_masking": (*_STANDALONE, QUOTE, OBVIOUS),
    "mcq": (*_STANDALONE, UNSUPPORTED, SEVERAL_ANSWERS, OBVIOUS),
    "qa": (*_STANDALONE, UNSUPPORTED, SEVERAL_ANSWERS, OBVIOUS),
    "multihop_synthesis": (*_STANDALONE, UNSUPPORTED, SEVERAL_ANSWERS, OBVIOUS),
    "two_truths_one_lie": _STANDALONE,
    "tiered_explanation": _STANDALONE,
    "unanswerable_property": _STANDALONE,
    "false_premise": _STANDALONE,
}
# The checks that need the gold answer shown.
_NEEDS_ANSWER = frozenset({UNSUPPORTED, SEVERAL_ANSWERS, OBVIOUS})

# For the prompt: the language the questions are judged in.
LANGUAGE_NAMES: dict[str, str] = {
    "en": "English",
    "es": "Spanish",
    "pt": "Portuguese",
    "fr": "French",
    "de": "German",
    "it": "Italian",
    "nl": "Dutch",
    "ru": "Russian",
}

SYSTEM = """\
You review benchmark questions before they are used. In the test the \
answerer sees only the question (with its options), never the article. A \
question is usable only if a reader who sees nothing but the question knows \
what is asked, and the article answers it.

Each numbered question lists the checks to run on it; run only those. The \
questions may be in any language: judge them as a native reader of that \
language. A check fails when:

- source_reference: the question points at its source instead of at the \
world: "the article", "the text", "this story", "the fragment", "según el \
artículo", "en el texto", "la nota", "segundo o texto", "selon l'article", \
"laut dem Artikel". An outlet or a report named as such ("WIRED's review", \
"el informe del INE de 2025") is not a reference.
- unanchored: a pronoun or demonstrative ("he", "it", "this decision", "él", \
"ella", "esta medida", "dicho acuerdo", "ese anuncio", "cette décision", \
"diese Maßnahme") whose referent the question itself does not name. "This \
year", or a referent named earlier in the same question, passes. A blank \
"______" is the answer to fill in, not an anchor.
- quote: the sentence is someone's quoted wording (direct speech) rather than \
a statement of fact. A short quoted name or term passes.
- unsupported_wording: the question, or its answer, states or presupposes \
something the article does not say, or words it so that the fact changes.
- several_answers: more than one answer fits the question and the article: \
an open wording ("name one of", "what is an example of", "uno de los"), \
"what did X say" when X says several things in the article, or, with \
options, more than one correct option.
- obvious: a well-informed reader answers it without the article: general \
or historical knowledge that does not depend on this story, an answer the \
wording gives away, or options of which only one is plausible.

Return ONLY a JSON array, one object per question, no markdown. "fails" maps \
each failed check to a short reason in English that quotes the words at \
fault; it is empty when every check passes:
[{"index": 1, "fails": {}}, {"index": 2, "fails": {"unanchored": "'él' names \
no one"}}]
"""

# Answer budget per question, on top of the shared headroom.
TOKENS_PER_QUESTION = 80


# The model call (``llm.chat``).
type Chat = Callable[..., tuple[str, dict[str, Any]]]


@dataclass(frozen=True, slots=True)
class Verdict:
    """One question's verdict: the failed checks with their reasons."""

    fails: dict[str, str] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.fails

    def note(self) -> str:
        """``quality check: no antecedent ('él' names no one)``."""
        named = [
            f"{LABELS.get(code, code)} ({why})" if why else LABELS.get(code, code)
            for code, why in self.fails.items()
        ]
        return f"{POOR_QUALITY}: {'; '.join(named)}"


def provider(conf: Settings, writer: Provider) -> Provider:
    """The writer's provider, with ``quality_check_model`` when one is set."""
    model = conf.quality_check_model
    return replace(writer, model=model) if model else writer


def article(doc: Document, chunk: Chunk | None) -> str:
    """The article the check judges against: the whole document, cut at its
    limit, with the passage the questions came from put after it when the cut
    left it out."""
    text = document_text(doc)[:MAX_DOCUMENT_CHARS]
    passage = writer_passage(doc, chunk)
    if passage not in text:
        text = f"{text}\n\n[...]\n\n{passage}"
    return text


def user_prompt(
    doc: Document,
    chunk: Chunk | None,
    questions: list[tuple[str, Pair]],
    language: str | None,
) -> str:
    """The article and the numbered questions, each with its checks."""
    lines = document_header(doc)
    if language in LANGUAGE_NAMES:
        lines.append(f"Language: {LANGUAGE_NAMES[language]}")
    body: list[str] = []
    for i, (key, pair) in enumerate(questions, start=1):
        checks = CHECKS.get(key, _STANDALONE)
        item = [f"{i}. Checks: {', '.join(checks)}", entities.shown(key, pair)]
        if _NEEDS_ANSWER & set(checks):
            item.append(f"Answer: {pair.answer}")
        body.append("\n".join(item))
    questions_text = "\n\n".join(body)
    return (
        "\n".join(lines)
        + f'\n\nArticle:\n"""\n{article(doc, chunk)}\n"""\n\n'
        + f"Questions:\n\n{questions_text}"
    )


def parse(raw: str, asked: list[tuple[str, ...]]) -> dict[int, Verdict]:
    """Verdicts by 0-based question index; a question the reply leaves out is
    absent. A failed check the question was not asked about is ignored.

    Raises:
        LLMError: the reply holds no readable verdict
    """
    out: dict[int, Verdict] = {}
    for item in parse_json_list(raw):
        index = item.get("index")
        fails = item.get("fails")
        if not isinstance(index, int) or isinstance(index, bool):
            continue
        if not 1 <= index <= len(asked):
            continue
        if fails is None:
            fails = {}
        if not isinstance(fails, dict):
            continue
        checks = asked[index - 1]
        out[index - 1] = Verdict(
            {
                str(code): str(why or "").strip()
                for code, why in fails.items()
                if code in checks
            }
        )
    if not out:
        raise LLMError("the quality check reply holds no verdict")
    return out


def record(
    checks: tuple[str, ...], verdict: Verdict | None, language: str | None, error: str
) -> dict[str, Any]:
    """A pair's ``meta.quality_check``: each check's verdict and the reasons."""
    out: dict[str, Any] = {"language": language}
    if verdict is None:
        out.update(
            outcome=decisions.FAILED,
            error=error or "the reply has no verdict on it",
            checks=dict.fromkeys(checks, "unchecked"),
        )
        return out
    out.update(
        outcome=decisions.KEPT if verdict.ok else decisions.REMOVED,
        checks={c: "fail" if c in verdict.fails else "pass" for c in checks},
        reasons=dict(verdict.fails),
    )
    return out


def screen(
    made: Mapping[str, list[Pair]],
    doc: Document,
    chunk: Chunk | None,
    *,
    language: str | None,
    conf: Settings,
    provider: Provider,
    chat: Chat,
    headroom: int,
    hold: Callable[[], AbstractContextManager[None]] = nullcontext,
) -> tuple[dict[str, list[Pair]], dict[str, list[tuple[Pair, str]]], dict[str, Any]]:
    """The quality check over one unit's questions, in one call.

    Args:
        made: Per kind, the questions the earlier checks kept
        doc: Their article
        chunk: Their passage; None — a document-scope unit
        language: The article's language code, as the language check
            detected it; None — not detected
        chat: The model call (``llm.chat``)
        headroom: Answer tokens on top of the per-question budget

    Returns:
        Per kind the questions kept, each with its record in
        ``meta.quality_check``; per kind the rejected ones with their notes;
        and the call ({call, model, system, user, reply, cost_usd,
        latency_s}; empty — the check is off or the call failed)
    """
    kept: dict[str, list[Pair]] = {key: [] for key in made}
    rejected: dict[str, list[tuple[Pair, str]]] = {key: [] for key in made}
    order = [(key, pair) for key, pairs in made.items() for pair in pairs]
    if not conf.quality_check or not order:
        return dict(made), rejected, {}
    asked = [CHECKS.get(key, _STANDALONE) for key, _ in order]
    user = user_prompt(doc, chunk, order, language)
    call: dict[str, Any] = {}
    verdicts: dict[int, Verdict] = {}
    error = ""
    try:
        with hold():
            raw, usage = chat(
                SYSTEM,
                user,
                provider=provider,
                max_tokens=TOKENS_PER_QUESTION * len(order) + headroom,
                settings=conf,
                role=cost.WRITER,
            )
        call = {
            "call": uuid.uuid4().hex,
            "model": provider.model,
            "system": SYSTEM,
            "user": user,
            "reply": raw,
            **cost.spent(usage),
        }
        verdicts = parse(raw, asked)
    except LLMError as exc:
        error = str(exc)
        logger.warning(f"quality check failed, the questions are kept: {error}")
    for i, (key, pair) in enumerate(order):
        verdict = verdicts.get(i)
        stamped = replace(
            pair, meta={**pair.meta, META: record(asked[i], verdict, language, error)}
        )
        if verdict is not None and not verdict.ok:
            rejected[key].append((stamped, verdict.note()))
        else:
            kept[key].append(stamped)
    return kept, rejected, call
