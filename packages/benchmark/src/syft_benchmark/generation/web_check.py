"""The web check: drop the questions a model answers without the publisher.

A question measures the publisher's archive only if a model cannot answer it
without that archive. So every grounded pending question is put to the web
check model (``filter_model``) as a bare question: no passage, no context,
none of the publisher's data. The model may search the web and use its own
training. The answer is graded the way the main run grades that kind of
question (``runs.judge``: option letter, key facts, judge). A question it
answers correctly is rejected as ``web_answerable``; the rest stay and go on
to the set cap.

A trick question (``unanswerable_property``) is checked too: the web model
answers it bare, the behaviour judge (``runs.judge.grade_control``) reads the
answer, and a specific answer its search supports (``web_sourced``) rejects it
as ``public_knowledge``. A false premise is not checked: a model doubting it
says nothing about what the web knows.

Web search follows ``web_search_for(conf, "filter", model)``: always asked
for, used when the model's provider offers it. Without it the model answers
from its own training alone, and every pair it checks carries that note in
``meta.web_check``. Such a check rejects fewer questions, but what it rejects
is still answerable without the publisher.

A failed answer call or a failed grading never decides a pair: it stays
pending with a note and is checked again on the next pass.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from loguru import logger

from syft_benchmark.config import ControlOutcome, Settings, Verdict
from syft_benchmark.db import QaPair
from syft_benchmark.llm import LLMError, LLMFatalError, Provider, chat, cost, roles
from syft_benchmark.llm.ollama import search_unused, supports_web_search
from syft_benchmark.runs.judge import (
    Grade,
    control_case,
    grade,
    grade_control,
    grade_key_facts,
)

WEB_ANSWERABLE = "web_answerable"

WEB_CHECK_SYSTEM = """\
Answer the question. Search the web and use your own knowledge.

If you cannot find the answer, respond with ONLY: I don't know

Do not guess. An honest "I don't know" is better than a confident answer that \
might be wrong.
"""

# The same instruction for a model that cannot search here.
OWN_KNOWLEDGE_SYSTEM = """\
Answer the question from your own knowledge.

If you are not sure, respond with ONLY: I don't know

Do not guess. An honest "I don't know" is better than a confident answer that \
might be wrong.
"""

NO_SEARCH_NOTE = "no web search for this model here: answered from its own training"
CONTROL_NOTE = "not checked: a control question, its right answer is to abstain"
# The note on a trick question the web model answers from its search.
PUBLIC_KNOWLEDGE = "public knowledge"
# The control kinds the web check asks: their missing detail must not be public.
_PUBLIC_CHECKED = frozenset({"unanswerable_property"})
NO_FACTS_NOTE = "not checked: a key-facts question without key facts"

# How much of the web model's answer ``meta.web_check`` keeps; the job's
# decision record (``meta.screening``) keeps it whole, with the prompts.
_ANSWER_KEPT = 2000
_CITATIONS_KEPT = 10
# The full texts of a check, kept only in the decision record.
FULL_KEYS = (
    "system",
    "user",
    "judge_system",
    "judge_prompt",
    "judge_reply",
)


def lean(record: dict[str, Any]) -> dict[str, Any]:
    """The record ``meta.web_check`` keeps: no prompts, the answer cut."""
    out = {k: v for k, v in record.items() if k not in FULL_KEYS}
    if isinstance(out.get("answer"), str):
        out["answer"] = out["answer"][:_ANSWER_KEPT]
    return out


@dataclass(frozen=True, slots=True)
class WebVerdict:
    """The web check's word on one pair.

    ``answerable`` is None when the check did not happen: the call or the
    judge failed. Such a pair stays pending and is checked on the next pass.
    ``meta`` is folded into the pair's meta either way.
    """

    answerable: bool | None
    note: str
    meta: dict[str, Any] = field(default_factory=dict)
    fatal: bool = False


@dataclass(slots=True)
class WebCheckSummary:
    """What one web check pass did."""

    checked: int = 0
    removed: int = 0
    kept: int = 0
    failed: int = 0
    # Of the checked: pairs already in the set (active or held back by the cap).
    rechecked: int = 0
    # The model could not search: it answered from its own training.
    own_training_only: bool = False
    notes: list[str] = field(default_factory=list)

    def line(self) -> str:
        line = (
            f"web check: checked {self.checked}, removed {self.removed}, "
            f"kept {self.kept}, failed {self.failed}"
        )
        if self.rechecked:
            line += f" ({self.rechecked} of them already in the set)"
        if self.own_training_only:
            line += " (no web search: own training only)"
        return line


def filter_model(conf: Settings) -> str:
    """The web check model; empty — the check is off."""
    return str(getattr(conf, "filter_model", None) or "")


def filter_provider(conf: Settings) -> Provider | None:
    """Where the web check model is called: the subjects' provider."""
    return roles.filter_provider(conf)


def filter_judge(conf: Settings) -> Provider | None:
    """The web check judge: ``filter_judge_model``, else Judge 1."""
    model = conf.filter_judge_model or ""
    if model:
        return Provider(
            role="judge",
            url=conf.judge_url or conf.ollama_url,
            api_key=conf.judge_key or conf.llm_api_key,
            model=model,
        )
    judges = roles.judge_providers(conf)
    return judges[0] if judges else None


def search_for(conf: Settings, provider: Provider) -> tuple[bool, str]:
    """Whether the web check model searches, and with which engine.

    The role is always on; the model's provider decides whether it can.
    """
    resolve = getattr(roles, "web_search_for", None)
    enabled, engine = (
        resolve(conf, "filter", provider.model)
        if resolve
        else (True, conf.web_search_engine.value)
    )
    if not enabled or not supports_web_search(provider.url):
        return False, ""
    return True, str(engine or "")


def exclusion(row: QaPair) -> str:
    """Why this pair is not put to the web check; empty — it is."""
    meta = row.meta or {}
    grading = str(meta.get("grading") or "judge")
    if row.task_type == "negative" or grading == "behavior":
        return CONTROL_NOTE
    if grading == "key_facts" and not meta.get("key_facts"):
        return NO_FACTS_NOTE
    return ""


def checks_public(row: QaPair) -> bool:
    """A trick question the web check asks whether its detail is public."""
    return row.generator in _PUBLIC_CHECKED


def web_checked(row: QaPair, model: str) -> bool:
    """Whether this pair passed, or is exempt from, the web check by ``model``.

    A control question is exempt. Any other needs a graded verdict from this
    very model: a check by another model, a failed one or none does not count.
    """
    if exclusion(row) == CONTROL_NOTE:
        return True
    record = (row.meta or {}).get("web_check") or {}
    return (
        bool(model)
        and record.get("model") == model
        and bool(record.get("verdict"))
        and not record.get("error")
    )


def manual_wins(conf: Settings) -> bool:
    """Whether a status the owner set by hand outranks the web check."""
    priority = getattr(conf, "manual_status_priority", "filter") or "filter"
    return str(priority) == "manual"


def manual_override(row: QaPair) -> bool:
    """Whether the owner set this pair's status by hand."""
    return bool((row.meta or {}).get("manual_override"))


def passed_filter(row: QaPair, conf: Settings) -> bool:
    """Whether this pair may be asked of the tested models.

    True for a control question (exempt from the web check; its own gate is
    its status), for a hand-set pair when ``manual_status_priority`` is
    "manual", and for a pair whose web check by the current ``filter_model``
    was graded and the model did not answer it correctly. False otherwise,
    and always with no ``filter_model``. Status is not looked at here.
    """
    if exclusion(row) == CONTROL_NOTE:
        return True
    if manual_wins(conf) and manual_override(row):
        return True
    model = filter_model(conf)
    if not web_checked(row, model):
        return False
    verdict = ((row.meta or {}).get("web_check") or {}).get("verdict")
    return verdict != Verdict.CORRECT.value


def _graded(
    row: QaPair,
    answer: str,
    conf: Settings,
    judge: Provider | None,
    citations: list[dict[str, str]] | None = None,
) -> Grade:
    """The main run's grading for this pair's kind (runs.judge.grade_item).

    An explanation is checked against its key facts only: a web answer brings
    in facts the article lacks, and only "correct" matters here. A trick
    question gets the behaviour judge, told the answer's citations.
    """
    meta = row.meta or {}
    if checks_public(row):
        case = control_case(row.generator, row.question, row.answer, meta)
        return grade_control(
            case, answer, citations=citations or [], settings=conf, judge=judge
        )
    if str(meta.get("grading") or "judge") == "key_facts":
        facts = [str(f) for f in meta.get("key_facts", [])]
        return grade_key_facts(answer, facts, settings=conf, judge=judge)
    return grade(
        row.question,
        row.answer,
        answer,
        is_mcq=row.task_type == "choice",
        fill_in=row.task_type == "extractive",
        hop_facts=[str(f) for f in meta.get("hop_facts") or []],
        settings=conf,
        judge=judge,
    )


def _citations(usage: dict[str, Any]) -> list[dict[str, str]]:
    kept: list[dict[str, str]] = []
    for item in usage.get("citations") or []:
        if isinstance(item, dict) and item.get("url"):
            kept.append(
                {"url": str(item["url"]), "title": str(item.get("title") or "")}
            )
    return kept[:_CITATIONS_KEPT]


def _attempts(row: QaPair) -> int:
    previous = (row.meta or {}).get("web_check") or {}
    return int(previous.get("attempts") or 0) + 1


def check_pair(
    row: QaPair,
    provider: Provider,
    judge: Provider | None,
    conf: Settings,
    *,
    searching: bool = True,
    engine: str = "",
) -> WebVerdict:
    """Ask the web check model one bare question and grade its answer."""
    record: dict[str, Any] = {
        "model": provider.model,
        "judge": judge.model if judge is not None else conf.judge_model,
        "judge_temperature": conf.judge_temperature,
        "judge_reasoning_effort": conf.judge_reasoning_effort.value,
        "search": (engine or "auto") if searching else "none",
        "checked_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "attempts": _attempts(row),
    }
    if not searching:
        record["note"] = NO_SEARCH_NOTE
    record["system"] = WEB_CHECK_SYSTEM if searching else OWN_KNOWLEDGE_SYSTEM
    record["user"] = row.question
    try:
        answer, usage = chat(
            record["system"],
            record["user"],
            provider=provider,
            temperature=0.0,
            max_tokens=conf.answer_max_tokens,
            settings=conf,
            web_search=searching,
            web_search_engine=engine or "auto",
            role=cost.WEB_CHECK,
        )
    except LLMError as exc:
        return WebVerdict(
            None,
            f"web check failed, will retry: {exc}",
            {"web_check": {**record, "error": str(exc)[:400]}},
            fatal=isinstance(exc, LLMFatalError),
        )

    citations = _citations(usage)
    record["answer"] = answer
    record.update(cost.spent(usage))
    record["citations"] = citations
    record["web_search"] = usage.get("web_search", searching)
    for key in ("web_search_via", "web_search_forced", "web_search_requests"):
        if key in usage:
            record[key] = usage[key]
    if searching and search_unused({**usage, "web_search": True}):
        record["web_search_unused"] = True

    # The judging functions are the run's; the call is the web check's.
    with cost.acting_as(cost.WEB_CHECK):
        verdict = _graded(
            row, answer, conf, judge, citations if record["web_search"] else []
        )
    record.update(
        judge_system=verdict.judge_system,
        judge_prompt=verdict.judge_user,
        judge_reply=verdict.judge_raw,
        judge_cost_usd=verdict.cost_usd,
        judge_latency_s=verdict.latency_s,
    )
    record["verdict"] = verdict.verdict.value
    record["reasoning"] = verdict.reasoning
    if verdict.behavior:
        record["behavior"] = verdict.behavior
    if verdict.failed or verdict.verdict is Verdict.PENDING:
        return WebVerdict(
            None,
            f"web check not graded, will retry: {verdict.reasoning}",
            {"web_check": {**record, "error": verdict.reasoning}},
            fatal=verdict.fatal,
        )
    if checks_public(row):
        public = verdict.behavior == ControlOutcome.WEB_SOURCED.value
        return WebVerdict(
            public, PUBLIC_KNOWLEDGE if public else "", {"web_check": record}
        )
    answerable = verdict.verdict is Verdict.CORRECT
    return WebVerdict(
        answerable, WEB_ANSWERABLE if answerable else "", {"web_check": record}
    )


def skips_manual(row: QaPair, conf: Settings) -> bool:
    """A pair the owner set by hand, and the owner's word wins: not checked."""
    return manual_wins(conf) and manual_override(row)


class WebChecker:
    """The web check for one pass, callable from many threads.

    Resolves the model, its judge and its search once. ``check`` gives None
    once the check has stopped: on a provider refusal, or after
    ``max_consecutive_failures`` failed checks in a row. Counts go to
    ``summary``.
    """

    def __init__(self, conf: Settings, judge: Provider | None = None) -> None:
        self.conf = conf
        self.summary = WebCheckSummary()
        self.provider = filter_provider(conf)
        self.judge = judge or filter_judge(conf)
        self.searching, self.engine = (
            search_for(conf, self.provider) if self.provider else (False, "")
        )
        self.stopped = ""
        self._streak = 0
        self._warned = False
        self._lock = threading.Lock()

    @property
    def ready(self) -> bool:
        return self.provider is not None

    def _warn_once(self) -> None:
        if self.searching or self._warned or self.provider is None:
            return
        self._warned = True
        self.summary.own_training_only = True
        note = (
            f"web check: {self.provider.model} cannot search the web here, "
            f"so it answered from its own training"
        )
        logger.warning(note)
        self.summary.notes.append(note)

    def stop(self, note: str) -> None:
        with self._lock:
            if not self.stopped:
                self.stopped = note
                self.summary.notes.append(note)

    def check(self, row: QaPair) -> WebVerdict | None:
        """Check one pair; None — not checked, the check has stopped."""
        if self.stopped or self.provider is None:
            return None
        with self._lock:
            self._warn_once()
        verdict = check_pair(
            row,
            self.provider,
            self.judge,
            self.conf,
            searching=self.searching,
            engine=self.engine,
        )
        give_up = self.conf.max_consecutive_failures
        with self._lock:
            self.summary.checked += 1
            if verdict.answerable is None:
                self.summary.failed += 1
                self._streak += 1
                logger.warning(f"{row.id}: {verdict.note}")
                if verdict.fatal and not self.stopped:
                    self.stopped = f"web check stopped: {verdict.note}"
                    self.summary.notes.append(self.stopped)
                elif give_up and self._streak >= give_up and not self.stopped:
                    self.stopped = (
                        f"web check stopped: {self._streak} checks in a row failed"
                    )
                    self.summary.notes.append(self.stopped)
            else:
                self._streak = 0
                if verdict.answerable:
                    self.summary.removed += 1
                else:
                    self.summary.kept += 1
        return verdict
