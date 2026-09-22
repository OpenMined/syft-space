"""The control set: questions with no answer in the corpus.

Every other generator builds an item OUT OF a chunk, that is, the question is
answerable by construction. A dataset of only such questions measures half the
behaviour: what the pair does when there is no answer is not measured at all —
and that is the most frequent question a live user asks and the most dangerous
trap in RAG.

Two generators, and their axes differ:

  * ``unanswerable_property`` — a question about the same subject, but about a
    property that is not in the corpus. The negative is deliberately NEAR: the
    question is about an entity the documents do describe, so retrieval will
    return topically relevant chunks that contain no answer. This is exactly
    where a model assembles an invention out of real quotations — the answer
    looks as if it were backed by references.
  * ``false_premise`` — a question whose premise contradicts the source. The
    correct behaviour here is not abstention but CORRECTION: "that did not
    happen, in fact it is like this". An abstention is catchable with regexes,
    a correction is not, so this generator has its own gold answer and its own
    judging.

An important point about how reliable the labelling is: a generated negative is
in itself the model conjecture about what is not in the corpus. Letting it into
the measurement unchecked is not allowed, otherwise the benchmark will start
accusing models of invention where an answer did in fact exist. The check is
done by ``control.py`` against live retrieval.
"""

from __future__ import annotations

from typing import Any

from syft_benchmark.generation.pair import Pair
from syft_benchmark.generation.quality import reject_reason

_SHARED_RULES = """\
Rules:
1. The question must be standalone. Never write "the text", "the fragment", \
"the document" or "according to ...". Name the subject explicitly, so that \
the question still makes sense to someone who has never seen the fragment.
2. Never point at something with "this", "that", "these", "those".
3. Ask about something factual and specific — a number, a name, a date, a \
setting, a limit, a default. Never ask for an opinion or a prediction: those \
have no right answer at all, and the benchmark would be measuring nothing.
4. Write the question in the SAME language as the fragment.
"""

UNANSWERABLE_SYSTEM = f"""\
You build the CONTROL half of a question-answering benchmark for a private \
knowledge base. Your questions must be IMPOSSIBLE to answer from the \
knowledge base — that is the point of them.

You are given ONE fragment of ONE document. Produce exactly {{n}} questions \
that are about subjects the fragment DOES name, but ask for a property the \
fragment does NOT state.

{_SHARED_RULES}5. Name a subject that actually appears in the fragment. A \
question about something unrelated is useless here: it must look like a \
question a real user of these documents would ask.
6. The property you ask about must be absent from the fragment. Do not ask \
something the fragment answers, even partly.
7. Do not invent a value and do not hint at one.

Return ONLY a JSON array of {{n}} objects:
[{{{{"question": "...", "subject": "what from the fragment it is about", \
"missing": "what is being asked for that the fragment does not state"}}}}]
No markdown fences, no commentary.
"""

FALSE_PREMISE_SYSTEM = f"""\
You build the CONTROL half of a question-answering benchmark for a private \
knowledge base. Your questions must contain a FALSE PREMISE — something the \
fragment contradicts — so that the only correct response is to reject the \
premise.

You are given ONE fragment of ONE document. Produce exactly {{n}} questions.

{_SHARED_RULES}5. The false premise must contradict a fact the fragment \
states plainly. Do not build it on something the fragment merely omits — \
that is a different kind of question.
6. Phrase the question as if the premise were settled fact, the way a \
confused user would ask it: "why did X switch to Y", "when was Z removed".
7. The correction must state what the fragment actually says.

Return ONLY a JSON array of {{n}} objects:
[{{{{"question": "...", "premise": "the false claim built into the question", \
"correction": "what the fragment actually states", \
"grounds": ["fact from the fragment that makes the premise false"]}}}}]
No markdown fences, no commentary.
"""


def clean_unanswerable(
    items: list[dict[str, Any]], pairs: int, document: str
) -> tuple[list[Pair], list[str]]:
    """Select questions that should have no answer in the corpus.

    Such an item has no gold answer — it has a description of what is missing.
    That goes into the answer field and is needed by two readers: the auditor
    checking the labelling, and the human looking into a disputed verdict.
    """
    good: list[Pair] = []
    rejected: list[str] = []
    for item in items[: pairs * 2]:
        question = str(item.get("question") or "").strip()
        missing = str(item.get("missing") or "").strip()
        subject = str(item.get("subject") or "").strip()
        if len(question) < 10 or not missing:
            rejected.append("no question, or nothing said about what is missing")
            continue
        reason = reject_reason(question, document, task_type="abstractive")
        if reason:
            rejected.append(reason)
            continue
        good.append(
            Pair(
                question=question,
                # Not an answer but an explanation of its absence: it cannot and
                # need not be judged against — the correct behaviour here is to
                # abstain, and that is recognised without any model at all.
                answer=f"not in the corpus: {missing}",
                distractors=[],
                meta={
                    "subject": subject,
                    "missing": missing,
                    "grading": "behavior",
                },
            )
        )
    return good[:pairs], rejected


def clean_false_premise(
    items: list[dict[str, Any]], pairs: int, document: str
) -> tuple[list[Pair], list[str]]:
    """Select questions with a false premise.

    The gold answer here is a real one — it is the correction, and it is judged
    by an ordinary judge. An abstention ("I do not know") is not counted as
    correct behaviour: the premise can be refuted from the very documents the
    endpoint has.
    """
    good: list[Pair] = []
    rejected: list[str] = []
    for item in items[: pairs * 2]:
        question = str(item.get("question") or "").strip()
        correction = str(item.get("correction") or "").strip()
        premise = str(item.get("premise") or "").strip()
        grounds = [
            str(g).strip() for g in (item.get("grounds") or []) if str(g).strip()
        ]
        if len(question) < 10 or len(correction) < 5 or not premise:
            rejected.append("no question, premise or correction")
            continue
        reason = reject_reason(question, document, task_type="abstractive")
        if reason:
            rejected.append(reason)
            continue
        good.append(
            Pair(
                question=question,
                answer=correction,
                distractors=[],
                meta={
                    "premise": premise,
                    # What has to follow from the chunk is not the correction
                    # (it is reworded) but the facts that make the premise
                    # false. Those are what get checked — as with "two truths
                    # and a lie".
                    "claims": grounds or [correction],
                    "grading": "judge",
                },
            )
        )
    return good[:pairs], rejected
