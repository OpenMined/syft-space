"""The control set: questions with no answer in the corpus.

  * ``unanswerable_property`` — a property the corpus does not state, of a
    subject it does describe. Retrieval returns topically relevant chunks with
    no answer: where a model assembles an invention out of real quotations.
  * ``false_premise`` — a premise the source contradicts. The correct
    behaviour is a correction, not abstention, so it has its own gold answer
    and judging.

A generated negative is only the writer's conjecture about what the corpus
lacks; ``control.py`` verifies it against live retrieval before it is measured.
"""

from __future__ import annotations

from typing import Any

from syft_benchmark.generation.pair import Dropped, Pair
from syft_benchmark.generation.quality import reject_reason
from syft_benchmark.generation.wording import ANCHOR_RULE

# What an unanswerable item's answer field opens with.
NOT_IN_CORPUS = "not in the corpus:"

_SHARED_RULES = f"""\
Rules:
1. The question must be standalone. Never write "the text", "the fragment", \
"the document" or "according to ...". Name the subject explicitly, so that \
the question still makes sense to someone who has never seen the fragment.
2. Name every person, organisation and product so it is identifiable \
without the story: full name plus role or affiliation, a product with its \
maker. Never make a first name, a pseudonym or an anonymous source the \
subject of a question.
3. Never point at something with "this", "that", "these", "those".
4. Ask about something factual and specific — a number, a name, a date, a \
setting, a limit, a default. Never ask for an opinion or a prediction: those \
have no right answer at all, and the benchmark would be measuring nothing.
5. {ANCHOR_RULE}
6. Write the question in the SAME language as the fragment.
"""

UNANSWERABLE_SYSTEM = f"""\
You build the CONTROL half of a question-answering benchmark for a private \
knowledge base. Your questions must be IMPOSSIBLE to answer from the \
knowledge base — that is the point of them.

You are given ONE fragment of ONE document. Produce exactly {{n}} questions \
that are about subjects the fragment DOES name, but ask for a property the \
fragment does NOT state.

{_SHARED_RULES}7. Name a subject that actually appears in the fragment. A \
question about something unrelated is useless here: it must look like a \
question a real user of these documents would ask.
8. The property you ask about must be absent from the fragment. Do not ask \
something the fragment answers, even partly.
9. Do not invent a value and do not hint at one.
10. Ask for exactly ONE missing detail. Never combine two asks in one question.
11. The detail must not be public knowledge either: nothing a well-informed \
person could look up elsewhere, like a famous crew list or a well-known founder.

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

{_SHARED_RULES}7. The false premise must contradict a fact the fragment \
states plainly. Do not build it on something the fragment merely omits — \
that is a different kind of question.
8. Phrase the question as if the premise were settled fact, the way a \
confused user would ask it: "why did X switch to Y", "when was Z removed".
9. The correction must state what the fragment actually says.

Return ONLY a JSON array of {{n}} objects:
[{{{{"question": "...", "premise": "the false claim built into the question", \
"correction": "what the fragment actually states", \
"grounds": ["fact from the fragment that makes the premise false"]}}}}]
No markdown fences, no commentary.
"""


def clean_unanswerable(
    items: list[dict[str, Any]], pairs: int, document: str
) -> tuple[list[Pair], list[Dropped]]:
    """Select questions that should have no answer in the corpus.

    The answer field holds a description of what is missing, for whoever
    audits the labelling or a disputed verdict.
    """
    good: list[Pair] = []
    rejected: list[Dropped] = []
    for item in items[: pairs * 2]:
        question = str(item.get("question") or "").strip()
        missing = str(item.get("missing") or "").strip()
        subject = str(item.get("subject") or "").strip()
        if len(question) < 10 or not missing:
            rejected.append(
                Dropped(
                    "no question, or nothing said about what is missing",
                    question,
                    missing,
                )
            )
            continue
        reason = reject_reason(question, document, task_type="abstractive")
        if reason:
            rejected.append(Dropped(reason, question, missing))
            continue
        good.append(
            Pair(
                question=question,
                # Not judged against: the correct behaviour is to abstain.
                answer=f"{NOT_IN_CORPUS} {missing}",
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
) -> tuple[list[Pair], list[Dropped]]:
    """Select questions with a false premise.

    The gold answer is the correction, judged by an ordinary judge. Abstaining
    is not correct: the endpoint's own documents refute the premise.
    """
    good: list[Pair] = []
    rejected: list[Dropped] = []
    for item in items[: pairs * 2]:
        question = str(item.get("question") or "").strip()
        correction = str(item.get("correction") or "").strip()
        premise = str(item.get("premise") or "").strip()
        grounds = [
            str(g).strip() for g in (item.get("grounds") or []) if str(g).strip()
        ]
        if len(question) < 10 or len(correction) < 5 or not premise:
            rejected.append(
                Dropped("no question, premise or correction", question, correction)
            )
            continue
        reason = reject_reason(question, document, task_type="abstractive")
        if reason:
            rejected.append(Dropped(reason, question, correction))
            continue
        good.append(
            Pair(
                question=question,
                answer=correction,
                distractors=[],
                meta={
                    "premise": premise,
                    # Grounding checks the facts that make the premise false,
                    # not the reworded correction.
                    "claims": grounds or [correction],
                    "grading": "judge",
                },
            )
        )
    return good[:pairs], rejected
