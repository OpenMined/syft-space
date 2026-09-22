"""Judging: reducing any answer to one of three outcomes.

A port of `OMSyft/scripts/qa_judge.py`.

  * ``correct``     — answered to the substance of the gold answer;
  * ``abstain``     — honestly said it did not know: not counted as an error;
  * ``hallucinate`` — answered confidently and wide of the gold answer.

Abstention is separated from a miss deliberately, and that is the main
distinction in the measurement. A model that says "I do not know" about a corpus
it does not know is behaving correctly; a model that confidently invents about
the same corpus is dangerous. Their average score might coincide — which is why
there is no score, but three shares.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from syft_benchmark.config import Settings, Verdict, get_settings
from syft_benchmark.llm import (
    LLMError,
    LLMFatalError,
    Provider,
    chat,
    parse_json_object,
)

# The judge answer ceiling — shared with the other answers, BENCH_ANSWER_MAX_TOKENS.
#
# Generous on purpose. Reasoning models spend output tokens on reasoning BEFORE
# they print the JSON, and at a short ceiling the answer breaks off in the middle
# of the object. Such an answer cannot be parsed, the verdict is recorded as a
# failure, and the judge silently drops out of part of the questions — observed
# twice: gemini could not manage 200 tokens, Opus broke off a task at 1100.
#
# Raising the ceiling is in itself a patch, not a solution: the next model will
# run into the next number. The solution lives in the client — it notices a
# truncation by finish_reason and repeats the call with a doubled budget (a port
# of P1 from LiveTruth). The ceiling only sets where to start.

ERROR_PREFIX = "ERROR:"

# --- refusing to answer -----------------------------------------------------
# The patterns are English: that is the language the answering models are asked
# in, and an unrecognised abstention is counted as an answer rather than lost.
_ABSTAIN_PATTERNS = (
    r"i don'?t (?:know|have (?:access|information|enough|the))",
    r"i'?m not (?:sure|certain|able|aware)",
    r"i (?:cannot|can'?t|am unable to) "
    r"(?:determine|answer|confirm|verify|find|provide)",
    r"(?:no|not enough) (?:information|context|data) (?:available|provided|in the)",
    r"the (?:provided )?context does not (?:contain|mention|provide|specify)",
    r"(?:is|are) not (?:mentioned|specified|provided) in the (?:context|document)",
    r"based on the (?:provided )?context,? i (?:cannot|can'?t|don'?t)",
)
_ABSTAIN_RE = re.compile("|".join(_ABSTAIN_PATTERNS), re.IGNORECASE)

# Signs that the model did give an answer after all, if with a hedge. A hedge
# plus an answer is a guess, not an abstention, and must be assessed as an answer.
_ANSWER_SIGNALS = re.compile(
    r"(?:^|\n)\s*[A-Da-d]\)|"
    r"[A-Da-d]\)\s+\w|"
    r"\b(?:the answer is|most likely|apparently)\b|"
    # The word boundaries here are mandatory: without them "though" is found
    # inside "Although", and an honest abstention is scored as an answer.
    r"\b(?:however|but|though)\b[,;]?\s+\S+",
    re.IGNORECASE,
)

_MCQ_LETTER = re.compile(r"\b([A-D])\s*[\)\.:]", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class Grade:
    """The sentence on one answer.

    Along with the verdict it carries its own audit trail: what the judge was
    asked and what it answered verbatim. Without that there is nothing at all to
    check the assessment with — the benchmark number is a model verdict, and
    "trust me, the judge decided so" does not satisfy an auditor. The fields are
    empty where the judge was not called at all: matching an option letter and
    recognising an abstention do not call a model.
    """

    verdict: Verdict
    reasoning: str
    failed: bool = False  # the call did not happen: not in the metrics denominator
    # The provider refused the judge outright — the key, the money, the name.
    # Every later question gets the same answer, so the run stops rather than
    # buying the refusal once per item.
    fatal: bool = False
    judge_system: str = ""
    judge_user: str = ""
    judge_raw: str = ""
    # Which upstream served the judge. Empty where no model was called at all:
    # a matched option letter, a recognised abstention.
    served_by: str = ""


def deferred(system: str, user: str) -> Grade:
    """The verdict is deferred: there is an answer, the judge has not seen it yet.

    Returned where and only where judging would run into a model call. The cheap
    paths — a failed call, a recognised abstention, matching an option letter —
    run as usual: deferring what is free means doing the work twice and leaving a
    hole in the report where the answer is already known.

    The judge prompt is kept: it is what the deferred item is exported to a human
    by.
    """
    return Grade(
        Verdict.PENDING,
        "awaiting a judge",
        judge_system=system,
        judge_user=user,
    )


def is_error(answer: str) -> bool:
    """The answer is a failure message rather than an answer."""
    return answer.strip().startswith(ERROR_PREFIX)


def detect_abstain(answer: str) -> bool:
    """Whether it refused to answer."""
    text = (answer or "").strip()
    if not text:
        return True
    if not _ABSTAIN_RE.search(text):
        return False
    return not _ANSWER_SIGNALS.search(text)


def grade_behavior(answer: str) -> Grade:
    """Judge a question that has no answer in the corpus.

    No correct answer exists, and the triple of outcomes collapses to a pair:
    abstaining is the correct behaviour, any answer is an invention. That is
    precisely why LMI (``H / (H + C)``) is meaningless on the control set: its
    denominator holds correct answers, which do not occur here.

    The model is not called at all. An abstention is recognised by regexes, and a
    hedge of the form "I do not know, but most likely X" is caught by the answer
    signals and counted as an answer — it is a guess, not an abstention.

    The verdict is recorded as BEHAVIOUR rather than as an assessment: ``abstain``
    here means "the model abstained", and it is the report that knows the
    abstention was correct. Otherwise a change of methodology would require a
    re-run.
    """
    if is_error(answer):
        return Grade(Verdict.HALLUCINATE, answer[:300], failed=True)
    if detect_abstain(answer):
        return Grade(Verdict.ABSTAIN, "abstained — there is no answer in the corpus")
    return Grade(
        Verdict.HALLUCINATE, "answered a question with no answer in the corpus"
    )


def grade_mcq(answer: str, expected: str) -> bool | None:
    """A multiple-choice question: match the letter without calling a judge.

    The endpoint answers in prose ("The correct answer is C) Three"), so we look
    for the letter across the whole text. If several different letters are named,
    they cannot be decided on — we return None and hand the question to the judge.
    """
    correct = _MCQ_LETTER.match(expected.strip())
    if not correct:
        return None
    letter = correct.group(1).upper()

    mentioned = {m.group(1).upper() for m in _MCQ_LETTER.finditer(answer or "")}
    if len(mentioned) == 1:
        return mentioned.pop() == letter
    if not mentioned:
        option_text = expected.strip()[2:].strip(" )").lower()
        if option_text and option_text in (answer or "").lower():
            return True
    return None


_JUDGE_SYSTEM = """\
You are a strict grading assistant. Compare a model's answer against the \
expected answer for one question.

Rules:
- The answer is correct if it states the same facts as the expected answer. \
Paraphrasing and extra correct detail are fine; wrong or contradicting facts \
are not.
- Missing a key fact that the question asks for makes the answer incorrect.
- If the model refused to answer or said it does not know, mark it incorrect.
- For multiple choice the model must pick the same option as the expected \
answer.

Return ONLY a JSON object, no markdown and no commentary:
{"correct": true, "confidence": 0.0, "reasoning": "one short sentence"}
"""

_KEY_FACTS_SYSTEM = """\
You check whether an explanation covers a list of required facts.

For each fact, decide whether the explanation states it — in any wording, \
at any level of detail. Paraphrase counts. A fact contradicted by the \
explanation does NOT count as covered.

Return ONLY a JSON object, no markdown and no commentary:
{"covered": [true, false, true], "reasoning": "one short sentence"}

The "covered" array must have exactly one entry per fact, in the same order.
"""


_GROUNDED_SYSTEM = """\
You check whether an answer is supported by the fragments it was given.

Return ONLY a JSON object, no markdown and no commentary:
{"grounded": true, "reasoning": "one short sentence"}

"grounded" is true only if every factual claim in the answer can be found in \
the fragments. If the answer adds facts that are not in the fragments, \
"grounded" is false. If the answer only says it does not know, "grounded" is \
true.
"""


def grade(
    question: str,
    expected: str,
    answer: str,
    *,
    is_mcq: bool = False,
    settings: Settings | None = None,
    judge: Provider | None = None,
    defer: bool = False,
) -> Grade:
    """Judge one answer.

    Args:
        question: The question from the dataset
        expected: The gold answer
        answer: What the answerer said
        is_mcq: The answer is picked from options — then we match the letter first
        settings: The process settings
        defer: Do not call the judge, return "awaiting a judge". The cheap paths
            still run as usual — there is no point deferring what is free

    Returns:
        A Grade with one of the three outcomes; failed=True if the call did not happen
    """
    conf = settings or get_settings()

    if is_error(answer):
        # A failed call speaks about the rig, not about the quality of the
        # answers, and has no business in the metrics denominator.
        return Grade(Verdict.HALLUCINATE, answer[:300], failed=True)

    if detect_abstain(answer):
        return Grade(Verdict.ABSTAIN, "refused to answer")

    if is_mcq:
        by_letter = grade_mcq(answer, expected)
        if by_letter is not None:
            return Grade(
                Verdict.CORRECT if by_letter else Verdict.HALLUCINATE,
                "matched by the option letter",
            )

    user = (
        f"Question:\n{question}\n\n"
        f"Expected answer:\n{expected}\n\n"
        f"Model answer:\n{answer}\n\n"
        f"Is the model answer correct?"
    )
    if defer:
        return deferred(_JUDGE_SYSTEM, user)
    try:
        raw, usage = chat(
            _JUDGE_SYSTEM,
            user,
            model=None if judge is not None else conf.judge_model,
            provider=judge,
            temperature=0.0,
            max_tokens=conf.answer_max_tokens,
            settings=conf,
        )
        data = parse_json_object(raw)
    except LLMError as exc:
        return Grade(
            Verdict.HALLUCINATE,
            f"the judge did not answer: {exc}",
            failed=True,
            fatal=isinstance(exc, LLMFatalError),
            judge_system=_JUDGE_SYSTEM,
            judge_user=user,
        )

    correct = bool(data.get("correct", False))
    reasoning = str(data.get("reasoning", ""))[:400]
    return Grade(
        Verdict.CORRECT if correct else Verdict.HALLUCINATE,
        reasoning,
        judge_system=_JUDGE_SYSTEM,
        judge_user=user,
        judge_raw=raw,
        served_by=str(usage.get("served_by") or ""),
    )


def grade_key_facts(
    answer: str,
    facts: list[str],
    *,
    settings: Settings | None = None,
    judge: Provider | None = None,
    defer: bool = False,
) -> Grade:
    """Judge an extended explanation against a list of facts.

    Comparing prose with prose is not an assessment but a lottery: an explanation
    can be correct and unlike the gold answer. So for tiered items the gold answer
    is accompanied by a list of checkable facts, and it is that which is judged.

    Args:
        answer: What the answerer said
        facts: The key facts listed by the generator
        settings: The process settings

    Returns:
        A Grade; an abstention is recognised before any checking of facts
    """
    conf = settings or get_settings()

    if is_error(answer):
        return Grade(Verdict.HALLUCINATE, answer[:300], failed=True)
    if detect_abstain(answer):
        return Grade(Verdict.ABSTAIN, "refused to explain")
    if not facts:
        return Grade(Verdict.HALLUCINATE, "the item has no key facts", failed=True)

    listed = "\n".join(f"{i + 1}. {fact}" for i, fact in enumerate(facts))
    user = f"Facts:\n{listed}\n\nExplanation:\n{answer}\n\nWhich facts are covered?"
    if defer:
        return deferred(_KEY_FACTS_SYSTEM, user)
    try:
        raw, usage = chat(
            _KEY_FACTS_SYSTEM,
            user,
            model=None if judge is not None else conf.judge_model,
            provider=judge,
            temperature=0.0,
            max_tokens=conf.answer_max_tokens,
            settings=conf,
        )
        data = parse_json_object(raw)
    except LLMError as exc:
        return Grade(
            Verdict.HALLUCINATE,
            f"the judge did not answer: {exc}",
            failed=True,
            fatal=isinstance(exc, LLMFatalError),
            judge_system=_KEY_FACTS_SYSTEM,
            judge_user=user,
        )

    covered = [bool(x) for x in (data.get("covered") or [])][: len(facts)]
    if not covered:
        return Grade(
            Verdict.HALLUCINATE,
            "the judge did not parse the facts",
            failed=True,
            judge_system=_KEY_FACTS_SYSTEM,
            judge_user=user,
            judge_raw=raw,
            served_by=str(usage.get("served_by") or ""),
        )

    share = sum(covered) / len(facts)
    reasoning = f"covered {sum(covered)} of {len(facts)} facts"
    verdict = (
        Verdict.CORRECT if share >= conf.key_facts_threshold else Verdict.HALLUCINATE
    )
    return Grade(
        verdict,
        reasoning,
        judge_system=_KEY_FACTS_SYSTEM,
        judge_user=user,
        judge_raw=raw,
        served_by=str(usage.get("served_by") or ""),
    )


def check_grounded(
    answer: str,
    fragments: list[str],
    settings: Settings | None = None,
    judge: Provider | None = None,
) -> tuple[bool | None, str]:
    """Whether the answer follows from what the endpoint found.

    Meaningful only for run B: in run A there are no chunks at all, and there is
    nothing to ground.

    Returns:
        (grounded, explanation); None means the judging did not succeed
    """
    if not fragments:
        return None, "there were no chunks"
    conf = settings or get_settings()

    context = "\n---\n".join(fragments)[:6000]
    user = f"Fragments:\n{context}\n\nAnswer:\n{answer}\n\nIs the answer grounded?"
    try:
        # Not a verdict and does not reach a row, so the upstream has nowhere
        # to go.
        raw, _usage = chat(
            _GROUNDED_SYSTEM,
            user,
            model=None if judge is not None else conf.judge_model,
            provider=judge,
            temperature=0.0,
            max_tokens=conf.answer_max_tokens,
            settings=conf,
        )
        data = parse_json_object(raw)
    except LLMError as exc:
        return None, f"the judge did not answer: {exc}"
    return bool(data.get("grounded", False)), str(data.get("reasoning", ""))[:400]
