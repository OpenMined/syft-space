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

The gate uses THE SAME retrieval that is measured afterwards. This is not a
simplification but a definition: the label "there is no answer" is meaningful
only relative to a specific endpoint, not to an abstract corpus.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from syft_benchmark.config import Settings, get_settings
from syft_benchmark.llm import LLMError, Provider, chat, parse_json_object

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


@dataclass(frozen=True, slots=True)
class Gate:
    """The result of checking one candidate for the control set."""

    clear: bool  # no answer in the retrieval — the question is fit as a negative
    note: str
    fragments: int = 0
    checked: bool = True  # False — the check failed, fitness is unknown


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

    try:
        fragments = [text.strip() for text in retrieve(question) if text.strip()]
    except Exception as exc:  # noqa: BLE001 - the endpoint may have been rebooting
        return Gate(False, f"retrieval unreachable: {exc}", checked=False)

    if not fragments:
        # Retrieval found nothing — the question is certainly unanswerable by
        # this endpoint. There is nothing to check and no reason to call a model.
        return Gate(True, "retrieval returned nothing", fragments=0)

    listed = "\n---\n".join(fragments)[:8000]
    user = f"Question:\n{question}\n\nFragments:\n{listed}\n\nIs it answered?"
    try:
        raw, _usage = chat(
            _GATE_SYSTEM,
            user,
            model=None if judge is not None else conf.judge_model,
            provider=judge,
            temperature=0.0,
            max_tokens=600,
            settings=conf,
        )
        data = parse_json_object(raw)
    except LLMError as exc:
        # Unknown is not fit: a candidate about which one cannot say whether it
        # is answerable does not go into the measurement.
        return Gate(
            False, f"the gate did not run: {exc}", len(fragments), checked=False
        )

    answered = bool(data.get("answered", False))
    if answered:
        where = str(data.get("where", ""))[:200]
        return Gate(False, f"retrieval answers the question: {where}", len(fragments))
    return Gate(
        True, f"retrieval does not answer ({len(fragments)} chunks)", len(fragments)
    )
