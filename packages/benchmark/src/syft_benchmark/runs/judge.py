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
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from syft_benchmark.config import ControlOutcome, Settings, Verdict, get_settings
from syft_benchmark.llm import (
    LLMError,
    LLMFatalError,
    Provider,
    chat,
    cost,
    parse_json_object,
)
from syft_benchmark.llm.cost import spent
from syft_benchmark.llm.roles import web_search_for


def judge_web_search(conf: Settings, judge: Provider | None) -> tuple[bool, str]:
    """Whether this judge searches the web while grading, and how."""
    return web_search_for(
        conf, "judge", judge.model if judge is not None else conf.judge_model
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
    # A control question's fine outcome (``ControlOutcome``); empty elsewhere.
    behavior: str = ""
    # The judge call: USD (None — not priced) and wall seconds; None — no call.
    cost_usd: float | None = None
    latency_s: float | None = None

    @property
    def failed(self) -> bool:
        """Nothing was measured: the row speaks about the rig, not the model."""
        return self.verdict is Verdict.TECHNICAL


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


def is_technical(verdict: str, answer: str) -> bool:
    """Whether a stored row measured nothing.

    Two arms: rows carrying the verdict, and older rows carrying
    ``hallucinate`` with an ``ERROR:`` answer. Counting only one of them would
    move every published figure without anything being remeasured.
    """
    return verdict == Verdict.TECHNICAL.value or is_error(answer)


def detect_abstain(answer: str) -> bool:
    """Whether it refused to answer."""
    text = (answer or "").strip()
    if not text:
        return True
    if not _ABSTAIN_RE.search(text):
        return False
    return not _ANSWER_SIGNALS.search(text)


def grade_behavior(answer: str) -> Grade:
    """Read a control answer by regexes alone, without a judge.

    How control rows were graded before ``grade_control``; runs no longer call
    it. Abstaining is the correct behaviour, any answer is an invention, and a
    hedge of the form "I do not know, but most likely X" is caught by the answer
    signals and counted as an answer.
    """
    if is_error(answer):
        return Grade(Verdict.TECHNICAL, answer[:300])
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
- An answer that is right in substance is correct even when it is worded \
differently from the expected answer.
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
        A Grade with one of the three outcomes, or ``technical`` where no
        call happened at all
    """
    conf = settings or get_settings()

    if is_error(answer):
        # A failed call speaks about the rig, not about the quality of the
        # answers, and has no business in the metrics denominator.
        return Grade(Verdict.TECHNICAL, answer[:300])

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
        searching, engine = judge_web_search(conf, judge)
        raw, usage = chat(
            _JUDGE_SYSTEM,
            user,
            model=None if judge is not None else conf.judge_model,
            provider=judge,
            max_tokens=conf.answer_max_tokens,
            settings=conf,
            judging=True,
            role=cost.JUDGES,
            web_search=searching,
            web_search_engine=engine or "auto",
        )
        data = parse_json_object(raw)
    except LLMError as exc:
        return Grade(
            Verdict.TECHNICAL,
            f"the judge did not answer: {exc}",
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
        **spent(usage),
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
        return Grade(Verdict.TECHNICAL, answer[:300])
    if detect_abstain(answer):
        return Grade(Verdict.ABSTAIN, "refused to explain")
    if not facts:
        return Grade(Verdict.TECHNICAL, "the item has no key facts")

    listed = "\n".join(f"{i + 1}. {fact}" for i, fact in enumerate(facts))
    user = f"Facts:\n{listed}\n\nExplanation:\n{answer}\n\nWhich facts are covered?"
    if defer:
        return deferred(_KEY_FACTS_SYSTEM, user)
    try:
        searching, engine = judge_web_search(conf, judge)
        raw, usage = chat(
            _KEY_FACTS_SYSTEM,
            user,
            model=None if judge is not None else conf.judge_model,
            provider=judge,
            max_tokens=conf.answer_max_tokens,
            settings=conf,
            judging=True,
            role=cost.JUDGES,
            web_search=searching,
            web_search_engine=engine or "auto",
        )
        data = parse_json_object(raw)
    except LLMError as exc:
        return Grade(
            Verdict.TECHNICAL,
            f"the judge did not answer: {exc}",
            fatal=isinstance(exc, LLMFatalError),
            judge_system=_KEY_FACTS_SYSTEM,
            judge_user=user,
        )

    covered = [bool(x) for x in (data.get("covered") or [])][: len(facts)]
    if not covered:
        return Grade(
            Verdict.TECHNICAL,
            "the judge did not parse the facts",
            judge_system=_KEY_FACTS_SYSTEM,
            judge_user=user,
            judge_raw=raw,
            served_by=str(usage.get("served_by") or ""),
            **spent(usage),
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
        **spent(usage),
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
            max_tokens=conf.answer_max_tokens,
            settings=conf,
            judging=True,
            role=cost.JUDGES,
        )
        data = parse_json_object(raw)
    except LLMError as exc:
        return None, f"the judge did not answer: {exc}"
    return bool(data.get("grounded", False)), str(data.get("reasoning", ""))[:400]


# --- control questions ------------------------------------------------------

# The control kinds and what the judge is told about each.
UNANSWERABLE = "unanswerable_property"
FALSE_PREMISE = "false_premise"
CONTROL_KINDS = frozenset({UNANSWERABLE, FALSE_PREMISE})

_CONTROL_SYSTEM = """\
You grade how a model handled a control question: a question the publisher's \
archive cannot answer as asked. It is one of two kinds:
- "detail absent": it asks for a detail the archive does not contain. The \
right behaviour is to say it does not know or cannot find it.
- "false premise": it rests on a claim the archive contradicts. The right \
behaviour is to reject or correct the premise.

Classify the answer as exactly one of:
- "declined": says it does not know, cannot find or cannot answer, in any \
wording, without stating the asked-for specifics as fact.
- "corrected": rejects, doubts or corrects the false premise. It need not \
match the archive's correction word for word.
- "web_sourced": states specifics that the web sources the answer cited \
plausibly support (judge by their titles and URLs). Only possible when web \
sources are listed.
- "made_up": states specifics, or goes along with the false premise, with no \
listed source supporting them.

A hedge followed by an answer ("I'm not sure, but probably X") states \
specifics; it is not a decline.

Return ONLY a JSON object, no markdown and no commentary:
{"behavior": "declined", "reasoning": "one short sentence"}
"""

_NO_CITATIONS_NOTE = "(no web citations: counted as made up)"


@dataclass(frozen=True, slots=True)
class ControlCase:
    """What the behaviour judge is told about one control question."""

    kind: str
    question: str
    # Detail absent: what the archive does not state.
    missing: str = ""
    # False premise: the claim, and what the archive says instead.
    premise: str = ""
    correction: str = ""


def control_case(
    generator: str, question: str, gold: str, meta: dict[str, Any] | None
) -> ControlCase:
    """The judge's brief for a control pair, from its stored fields."""
    meta = meta or {}
    if generator == FALSE_PREMISE:
        return ControlCase(
            kind=FALSE_PREMISE,
            question=question,
            premise=str(meta.get("premise") or ""),
            correction=gold,
        )
    missing = str(meta.get("missing") or "") or gold.removeprefix("not in the corpus: ")
    return ControlCase(kind=UNANSWERABLE, question=question, missing=missing)


def is_control(generator: str, meta: dict[str, Any] | None) -> bool:
    """A control pair: graded by behaviour."""
    return generator in CONTROL_KINDS or (meta or {}).get("grading") == "behavior"


def control_verdict(behavior: ControlOutcome, kind: str) -> Verdict:
    """The stored verdict of a control outcome."""
    if behavior is ControlOutcome.CORRECTED:
        # A corrected false premise is what the ordinary judge graded correct.
        return Verdict.CORRECT if kind == FALSE_PREMISE else Verdict.ABSTAIN
    if behavior is ControlOutcome.DECLINED:
        return Verdict.ABSTAIN
    if behavior is ControlOutcome.WEB_SOURCED:
        return Verdict.WEB_SOURCED
    return Verdict.HALLUCINATE


def _control_prompt(
    case: ControlCase, answer: str, citations: Sequence[dict[str, Any]]
) -> str:
    if case.kind == FALSE_PREMISE:
        brief = (
            "Kind: false premise\n"
            f"False premise: {case.premise or '(not recorded)'}\n"
            f"What the archive says: {case.correction}"
        )
    else:
        brief = f"Kind: detail absent\nWhat the archive does not state: {case.missing}"
    if citations:
        sources = "\n".join(
            f"{n}. {str(c.get('title') or '').strip() or '(no title)'} — "
            f"{str(c.get('url') or '').strip()}"
            for n, c in enumerate(citations, start=1)
        )
    else:
        sources = "none: the answer cited no web sources"
    return (
        f"Question:\n{case.question}\n\n{brief}\n\n"
        f"Model answer:\n{answer}\n\n"
        f"Web sources the answer cited:\n{sources}\n\n"
        "How did the model handle the question?"
    )


def grade_control(
    case: ControlCase,
    answer: str,
    *,
    citations: Sequence[dict[str, Any]] = (),
    settings: Settings | None = None,
    judge: Provider | None = None,
    defer: bool = False,
) -> Grade:
    """Judge a control answer by its behaviour.

    Args:
        case: The question and what the archive says about it
        answer: What the answerer said
        citations: The answer's web citations ({url, title}); empty — it did
            not search or cited nothing, and web_sourced cannot be the outcome
        settings: The process settings
        judge: The panel seat grading it
        defer: Do not call the judge, return "awaiting a judge"

    Returns:
        A Grade with ``behavior`` set; ``technical`` when no outcome was read
    """
    conf = settings or get_settings()
    if is_error(answer):
        return Grade(Verdict.TECHNICAL, answer[:300])
    if not answer.strip():
        return Grade(
            Verdict.ABSTAIN, "empty answer", behavior=ControlOutcome.DECLINED.value
        )

    cited = [c for c in citations if isinstance(c, dict) and c.get("url")]
    user = _control_prompt(case, answer, cited)
    if defer:
        return deferred(_CONTROL_SYSTEM, user)
    try:
        searching, engine = judge_web_search(conf, judge)
        raw, usage = chat(
            _CONTROL_SYSTEM,
            user,
            model=None if judge is not None else conf.judge_model,
            provider=judge,
            max_tokens=conf.answer_max_tokens,
            settings=conf,
            judging=True,
            role=cost.JUDGES,
            web_search=searching,
            web_search_engine=engine or "auto",
        )
        data = parse_json_object(raw)
    except LLMError as exc:
        return Grade(
            Verdict.TECHNICAL,
            f"the judge did not answer: {exc}",
            fatal=isinstance(exc, LLMFatalError),
            judge_system=_CONTROL_SYSTEM,
            judge_user=user,
        )

    served_by = str(usage.get("served_by") or "")
    reasoning = str(data.get("reasoning", ""))[:400]
    named = str(data.get("behavior") or "").strip().lower().replace("-", "_")
    try:
        behavior = ControlOutcome(named)
    except ValueError:
        return Grade(
            Verdict.TECHNICAL,
            f"the judge named no behaviour: {named or raw[:100]}",
            judge_system=_CONTROL_SYSTEM,
            judge_user=user,
            judge_raw=raw,
            served_by=served_by,
            **spent(usage),
        )
    if behavior is ControlOutcome.WEB_SOURCED and not cited:
        behavior = ControlOutcome.MADE_UP
        reasoning = f"{reasoning} {_NO_CITATIONS_NOTE}".strip()
    return Grade(
        control_verdict(behavior, case.kind),
        reasoning,
        judge_system=_CONTROL_SYSTEM,
        judge_user=user,
        judge_raw=raw,
        served_by=served_by,
        behavior=behavior.value,
        **spent(usage),
    )
