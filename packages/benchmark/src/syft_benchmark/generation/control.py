"""Verifying the control set's labelling.

A generated negative is no more than the model's conjecture about what is not
in the corpus. A conjecture can be wrong: the generator sees ONE chunk, while
retrieval searches the whole collection, and the answer may well lie in a
neighbouring document. Letting such a question into the measurement means
recording a correct answer as a hallucination — and that is exactly the error
because of which, in the original, "a bad question" and "the model does not
know" produced the same row.

So a candidate goes through a gate: it is put to live retrieval and we look at
whether among what was found there is a chunk that answers it. A judge decides,
not the generator — there is no reason for the generator to judge its own work.

Two gates share that search and that judge. ``gate_unanswerable`` keeps a
question retrieval does NOT answer (a missing detail). ``gate_answerable``
keeps a question retrieval DOES answer; a false premise goes through it with
its correction as the expected answer, since refuting the premise needs the
archive to state the true fact.

The gate uses THE SAME retrieval that is measured afterwards. This is not a
simplification but a definition: the label "there is no answer" is meaningful
only relative to a specific endpoint, not to an abstract corpus.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

from syft_benchmark.config import Settings, get_settings
from syft_benchmark.llm import LLMError, Provider, chat, cost, parse_json_object
from syft_benchmark.llm.roles import web_search_for

# What to query retrieval with: a question in, the texts of the chunks found
# out. A callable rather than an endpoint client, for two reasons: generation
# must not depend on the runs module, and the gate has to be testable offline.
Retriever = Callable[[str], list[str]]

_GATE_SYSTEM = """\
You check whether a question can be answered from the material found for it.

You are given a question and the fragments a search returned for it. Decide \
whether ANY fragment states the answer.

Be strict in one direction only: a fragment that is merely about the same \
topic does NOT answer the question. The answer must actually be stated.

Return ONLY a JSON object, no markdown and no commentary:
{"answered": false, "where": "", "reasoning": "one short sentence"}

Set "answered" to true only if a fragment states the answer, and put a short \
quote from it in "where".
"""

_ANSWERABLE_SYSTEM = """\
You check whether the material found for a question states its expected answer.

You are given a question, its expected answer, sometimes the facts that answer \
rests on, and the fragments a search returned for the question. Decide whether \
ANY fragment states the expected answer.

When a false premise is given, the question rests on a claim that is not true \
and the expected answer is its correction. Then decide whether any fragment \
states the true fact that contradicts the false premise.

A fragment that is merely about the same topic does NOT count: the fact must \
actually be stated. The wording may differ; the meaning must match.

Return ONLY a JSON object, no markdown and no commentary:
{"answered": false, "where": "", "reasoning": "one short sentence"}

Set "answered" to true only if a fragment states it, and put a short quote \
from that fragment in "where".
"""

# Fragments beyond this many characters are not shown to the judge.
_FRAGMENTS_CHARS = 8000


@dataclass(frozen=True, slots=True)
class Gate:
    """The result of checking one candidate against live retrieval."""

    clear: bool  # the candidate is fit for the set
    note: str
    fragments: int = 0
    checked: bool = True  # False — the check failed, fitness is unknown
    # The model call, for the record: {model, system, user, reply, cost_usd,
    # latency_s}; empty — no call was made or it failed.
    call: dict[str, Any] = field(default_factory=dict)


def _search(question: str, retrieve: Retriever) -> list[str] | Gate:
    """The non-empty fragments found, or the failed check."""
    try:
        return [text.strip() for text in retrieve(question) if text.strip()]
    except Exception as exc:  # noqa: BLE001 - the endpoint may have been rebooting
        return Gate(False, f"retrieval unreachable: {exc}", checked=False)


def _ask(
    system: str, user: str, conf: Settings, judge: Provider | None
) -> tuple[dict[str, Any], dict[str, Any]]:
    """The judge's parsed reply and the call record; raises ``LLMError``."""
    model = judge.model if judge is not None else conf.judge_model
    searching, engine = web_search_for(conf, "judge", model)
    raw, usage = chat(
        system,
        user,
        model=None if judge is not None else conf.judge_model,
        provider=judge,
        max_tokens=600,
        settings=conf,
        judging=True,
        web_search=searching,
        web_search_engine=engine or "auto",
        role=cost.WEB_CHECK,
    )
    call = {
        "model": model,
        "system": system,
        "user": user,
        "reply": raw,
        **cost.spent(usage),
    }
    return parse_json_object(raw), call


def gate_unanswerable(
    question: str,
    retrieve: Retriever,
    *,
    settings: Settings | None = None,
    judge: Provider | None = None,
) -> Gate:
    """Make sure live retrieval does not answer this question.

    Args:
        question: A candidate for the control set
        retrieve: What to search with: question → the texts of the chunks found
        settings: The process's settings
        judge: Who decides; a judge, not the generator

    Returns:
        Gate: whether the candidate is fit, and why
    """
    conf = settings or get_settings()

    fragments = _search(question, retrieve)
    if isinstance(fragments, Gate):
        return fragments

    if not fragments:
        # Retrieval found nothing — the question is certainly unanswerable by
        # this endpoint. There is nothing to check and no reason to call a model.
        return Gate(True, "retrieval returned nothing", fragments=0)

    listed = "\n---\n".join(fragments)[:_FRAGMENTS_CHARS]
    user = f"Question:\n{question}\n\nFragments:\n{listed}\n\nIs it answered?"
    try:
        data, call = _ask(_GATE_SYSTEM, user, conf, judge)
    except LLMError as exc:
        # Unknown is not fit: a candidate about which one cannot say whether it
        # is answerable does not go into the measurement.
        return Gate(
            False, f"the gate did not run: {exc}", len(fragments), checked=False
        )

    answered = bool(data.get("answered", False))
    if answered:
        where = str(data.get("where", ""))[:200]
        return Gate(
            False,
            f"retrieval answers the question: {where}",
            len(fragments),
            call=call,
        )
    return Gate(
        True,
        f"retrieval does not answer ({len(fragments)} chunks)",
        len(fragments),
        call=call,
    )


def gate_answerable(
    question: str,
    expected: str,
    retrieve: Retriever,
    *,
    facts: Sequence[str] = (),
    premise: str = "",
    settings: Settings | None = None,
    judge: Provider | None = None,
) -> Gate:
    """Make sure live retrieval finds the expected answer to this question.

    With ``premise`` set, the question rests on that false claim and
    ``expected`` is its correction: a fragment must state the true fact.

    Args:
        question: The candidate question
        expected: Its gold answer; for a false premise, the correction
        retrieve: What to search with: question → the texts of the chunks found
        facts: The stored facts the answer rests on (``meta.claims``)
        premise: The false claim built into the question; empty — none
        settings: The process's settings
        judge: Who decides; a judge, not the generator

    Returns:
        Gate: whether the candidate is fit, and why
    """
    conf = settings or get_settings()
    what = "correction" if premise else "answer"

    fragments = _search(question, retrieve)
    if isinstance(fragments, Gate):
        return fragments
    if not fragments:
        return Gate(
            False, f"{what} not found in the archive: retrieval returned nothing"
        )

    listed = "\n---\n".join(fragments)[:_FRAGMENTS_CHARS]
    parts = [f"Question:\n{question}"]
    if premise:
        parts.append(f"False premise:\n{premise}")
    parts.append(f"Expected answer:\n{expected}")
    if facts:
        parts.append("Facts it rests on:\n" + "\n".join(f"- {f}" for f in facts))
    parts.append(f"Fragments:\n{listed}")
    parts.append(
        "Does any fragment state the true fact that contradicts the false premise?"
        if premise
        else "Does any fragment state the expected answer?"
    )
    user = "\n\n".join(parts)
    try:
        data, call = _ask(_ANSWERABLE_SYSTEM, user, conf, judge)
    except LLMError as exc:
        # Unknown is not fit, as in gate_unanswerable.
        return Gate(
            False, f"the gate did not run: {exc}", len(fragments), checked=False
        )

    if bool(data.get("answered", False)):
        where = str(data.get("where", ""))[:200]
        return Gate(
            True, f"{what} found in the archive: {where}", len(fragments), call=call
        )
    return Gate(
        False,
        f"{what} not found in the archive ({len(fragments)} chunks)",
        len(fragments),
        call=call,
    )
