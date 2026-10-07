"""The web check: drop the questions a model answers without the publisher.

A question measures the publisher's archive only if a model cannot answer it
without that archive. So every grounded pending question is put to the web
check model (``filter_model``) as a bare question: no passage, no context,
none of the publisher's data. The model may search the web and use its own
training. The answer is graded the way the main run grades that kind of
question (``runs.judge``: option letter, key facts, judge). A question it
answers correctly is rejected as ``web_answerable``; the rest stay and go on
to the set cap.

Control questions (``unanswerable_property``, ``false_premise``) are not
checked: their right answer is to abstain or to catch a false premise, and a
model doing so says nothing about what the web knows.

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
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from contextlib import AbstractContextManager, nullcontext
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from loguru import logger

from syft_benchmark.config import Settings, Verdict
from syft_benchmark.db import QaPair
from syft_benchmark.llm import LLMError, LLMFatalError, Provider, chat, roles
from syft_benchmark.llm.ollama import search_unused, supports_web_search
from syft_benchmark.runs.judge import Grade, grade, grade_key_facts

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
NO_FACTS_NOTE = "not checked: a key-facts question without key facts"

# How much of the web model's answer to keep on the pair, for review.
_ANSWER_KEPT = 2000
_CITATIONS_KEPT = 10


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


def _graded(row: QaPair, answer: str, conf: Settings, judge: Provider | None) -> Grade:
    """The main run's grading for this pair's kind (runs.execute._verdict_for)."""
    meta = row.meta or {}
    if str(meta.get("grading") or "judge") == "key_facts":
        facts = [str(f) for f in meta.get("key_facts", [])]
        return grade_key_facts(answer, facts, settings=conf, judge=judge)
    return grade(
        row.question,
        row.answer,
        answer,
        is_mcq=row.task_type == "choice",
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
        "search": (engine or "auto") if searching else "none",
        "checked_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "attempts": _attempts(row),
    }
    if not searching:
        record["note"] = NO_SEARCH_NOTE
    try:
        answer, usage = chat(
            WEB_CHECK_SYSTEM if searching else OWN_KNOWLEDGE_SYSTEM,
            row.question,
            provider=provider,
            temperature=0.0,
            max_tokens=conf.answer_max_tokens,
            settings=conf,
            web_search=searching,
            web_search_engine=engine or "auto",
        )
    except LLMError as exc:
        return WebVerdict(
            None,
            f"web check failed, will retry: {exc}",
            {"web_check": {**record, "error": str(exc)[:400]}},
            fatal=isinstance(exc, LLMFatalError),
        )

    citations = _citations(usage)
    record["answer"] = answer[:_ANSWER_KEPT]
    record["citations"] = citations
    record["web_search"] = usage.get("web_search", searching)
    for key in ("web_search_via", "web_search_forced", "web_search_requests"):
        if key in usage:
            record[key] = usage[key]
    if searching and search_unused({**usage, "web_search": True}):
        record["web_search_unused"] = True

    verdict = _graded(row, answer, conf, judge)
    record["verdict"] = verdict.verdict.value
    record["reasoning"] = verdict.reasoning
    if verdict.failed or verdict.verdict is Verdict.PENDING:
        return WebVerdict(
            None,
            f"web check not graded, will retry: {verdict.reasoning}",
            {"web_check": {**record, "error": verdict.reasoning}},
            fatal=verdict.fatal,
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


def run_web_check(
    rows: Sequence[QaPair],
    *,
    settings: Settings,
    record: Callable[[QaPair, WebVerdict], None],
    judge: Provider | None = None,
    should_stop: Callable[[], bool] | None = None,
    checker: WebChecker | None = None,
    hold: Callable[[], AbstractContextManager[None]] | None = None,
) -> WebCheckSummary:
    """Check the pairs, ``concurrency`` at a time, and hand each verdict to ``record``.

    ``record`` gets failures too (``answerable`` None): the pair stays pending
    with the note. Stops on the owner's word, on a provider refusal, and after
    ``max_consecutive_failures`` failed checks in a row; pairs not reached are
    left as they are. ``judge`` None — ``filter_judge``. ``hold``, when given,
    is taken around each check (a shared model limit).
    """
    conf = settings
    web = checker or WebChecker(conf, judge)
    if not web.ready or not rows:
        return web.summary
    record_lock = threading.Lock()

    def one(row: QaPair) -> None:
        if web.stopped:
            return
        if should_stop is not None and should_stop():
            web.stop("the web check was stopped at the owner's request")
            return
        with hold() if hold is not None else nullcontext():
            verdict = web.check(row)
        if verdict is not None:
            with record_lock:
                record(row, verdict)

    width = max(1, conf.concurrency)
    with ThreadPoolExecutor(max_workers=width, thread_name_prefix="webcheck") as pool:
        for future in [pool.submit(one, row) for row in rows]:
            future.result()
    return web.summary
