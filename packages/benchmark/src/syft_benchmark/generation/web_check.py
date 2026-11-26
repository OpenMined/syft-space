"""The web check: drop the questions a model answers without the publisher.

Every grounded pending question is put to the web check model
(``filter_model``) bare, with web search where its provider offers it, and
graded as the main run grades that kind of question. A correct answer rejects
it as ``web_answerable`` (a false premise: the answer states the correction);
a trick question its search answers, as ``public_knowledge``. An answer that
cites only reprints of the publisher (``web_check_mirror_domains``) rejects
nothing. A failed call never decides a pair: it stays pending with a note.
The rules: docs/02-generation.md.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlsplit

from loguru import logger

from syft_benchmark.config import (
    ControlOutcome,
    ManualStatusPriority,
    Settings,
    Verdict,
)
from syft_benchmark.db import QaPair
from syft_benchmark.generation.language import detect_language
from syft_benchmark.llm import LLMError, LLMFatalError, Provider, chat, cost, roles
from syft_benchmark.llm.web_search import search_unused, supports_web_search
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

Search in the language of the question first: local and regional sources \
count. If a search finds nothing, search again with other words before you \
give up.

If the question assumes something that is not true, say so and give the facts.

If you cannot find the answer, respond with ONLY: I don't know
Write these three English words exactly, whatever the language of the question.

Do not guess. An honest "I don't know" is better than a confident answer that \
might be wrong.
"""

# The same instruction for a model that cannot search here.
OWN_KNOWLEDGE_SYSTEM = """\
Answer the question from your own knowledge.

If you are not sure, respond with ONLY: I don't know
Write these three English words exactly, whatever the language of the question.

Do not guess. An honest "I don't know" is better than a confident answer that \
might be wrong.
"""

NO_SEARCH_NOTE = "no web search for this model here: answered from its own training"
CONTROL_NOTE = "not checked: a control question, its right answer is to abstain"
# The note on a trick question the web model answers from its search.
PUBLIC_KNOWLEDGE = "public knowledge"
# A trick question: its missing detail must not be public.
_TRICK = "unanswerable_property"
# A false premise: the web must not know the fact that refutes it.
_PREMISE = "false_premise"
_CONTROLS_CHECKED = frozenset({_TRICK, _PREMISE})
NO_FACTS_NOTE = "not checked: a key-facts question without key facts"
# The record of an answer that would reject the pair but cites only reprints.
MIRROR_NOTE = "answered only from reprints of the publisher"

# The languages ``detect_language`` tells apart, as the prompt names them.
_LANGUAGE_NAMES = {
    "en": "English",
    "ru": "Russian",
    "de": "German",
    "fr": "French",
    "es": "Spanish",
    "it": "Italian",
    "pt": "Portuguese",
    "nl": "Dutch",
}
# Earlier checks a pair's record keeps, the newest last.
_HISTORY_KEPT = 10

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


def search_for(conf: Settings, provider: Provider) -> tuple[bool, str]:
    """Whether the web check model searches, and with which engine
    (``web_check_engine``).

    The role is always on; the model's provider decides whether it can.
    """
    enabled, engine = roles.web_search_for(conf, "filter", provider.model)
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
    return row.generator == _TRICK


def checks_premise(row: QaPair) -> bool:
    """A false premise the web check asks whether the web corrects."""
    return row.generator == _PREMISE


def checks_control(row: QaPair) -> bool:
    """A control question the web check asks."""
    return row.generator in _CONTROLS_CHECKED


def recheck_due(row: QaPair, conf: Settings, now: datetime | None = None) -> bool:
    """Its last graded web check is ``web_check_recheck_days`` old or more.

    The web catches up with a story: a detail absent at the check (a referee
    named later) can be public by the time the question is asked.
    """
    days = conf.web_check_recheck_days
    record = (row.meta or {}).get("web_check") or {}
    if not days or not record.get("verdict") or record.get("error"):
        return False
    try:
        checked = datetime.fromisoformat(str(record.get("checked_at")))
    except ValueError:
        return False
    if checked.tzinfo is None:
        checked = checked.replace(tzinfo=UTC)
    return (now or datetime.now(UTC)) - checked >= timedelta(days=days)


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
    return conf.manual_status_priority == ManualStatusPriority.MANUAL


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
    model = conf.filter_model or ""
    if not web_checked(row, model):
        return False
    verdict = ((row.meta or {}).get("web_check") or {}).get("verdict")
    return verdict != Verdict.CORRECT.value


def _graded(
    row: QaPair,
    answer: str,
    conf: Settings,
    judge: Provider,
    citations: list[dict[str, str]] | None = None,
) -> Grade:
    """The main run's grading for this pair's kind (runs.judge.grade_item).

    An explanation is checked against its key facts only: a web answer brings
    in facts the article lacks, and only "correct" matters here. A trick
    question gets the behaviour judge, told the answer's citations; a false
    premise, the free-text judge against its correction: the web knows the
    fact that refutes it.
    """
    meta = row.meta or {}
    if checks_premise(row):
        return grade(row.question, row.answer, answer, settings=conf, judge=judge)
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


def _host(url: str) -> str:
    return urlsplit(url.strip()).netloc.lower().removeprefix("www.")


def cited_domains(citations: list[dict[str, str]]) -> list[str]:
    """The sites the citations point to, sorted, without repeats."""
    return sorted({h for c in citations if (h := _host(str(c.get("url") or "")))})


def _is_mirror(url: str, mirrors: list[str]) -> bool:
    """The page is on one of the mirror domains (a subdomain counts; a
    domain with a path matches that path and below)."""
    parts = urlsplit(url.strip())
    host = parts.netloc.lower().removeprefix("www.")
    page = f"{host}{parts.path}"
    for mirror in mirrors:
        site, _, path = mirror.removeprefix("www.").partition("/")
        on_site = host == site or host.endswith(f".{site}")
        if on_site and (not path or page.startswith(f"{host}/{path}")):
            return True
    return False


def mirror_only(citations: list[dict[str, str]], mirrors: list[str]) -> bool:
    """Every citation is a reprint of the publisher: the answer is the
    publisher's text, not public knowledge. False with no citations."""
    urls = [str(c.get("url") or "") for c in citations]
    return bool(mirrors and urls) and all(_is_mirror(u, mirrors) for u in urls)


def _language_line(row: QaPair) -> str:
    """The question's language for the prompt; empty — not told."""
    found = detect_language(row.context or "") or detect_language(row.question)
    name = _LANGUAGE_NAMES.get(found or "")
    return f"\nThe question is in {name}: search in {name} first.\n" if name else ""


def _history(row: QaPair) -> list[dict[str, Any]]:
    """The pair's earlier checks, the last one included, each with its date."""
    previous = (row.meta or {}).get("web_check") or {}
    earlier = [h for h in previous.get("history") or [] if isinstance(h, dict)]
    if previous.get("checked_at"):
        keys = ("checked_at", "model", "verdict", "behavior", "cited_domains", "error")
        earlier.append({k: previous[k] for k in keys if previous.get(k) is not None})
    return earlier[-_HISTORY_KEPT:]


def check_pair(
    row: QaPair,
    provider: Provider,
    judge: Provider,
    conf: Settings,
    *,
    searching: bool = True,
    engine: str = "",
) -> WebVerdict:
    """Ask the web check model one bare question and grade its answer."""
    record: dict[str, Any] = {
        "model": provider.model,
        "judge": judge.model,
        "judge_temperature": conf.judge_temperature,
        "judge_reasoning_effort": conf.judge_reasoning_effort.value,
        "search": (engine or str(conf.web_check_engine)) if searching else "none",
        "checked_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "attempts": _attempts(row),
    }
    if searching:
        record["max_calls"] = conf.web_check_max_calls
    else:
        record["note"] = NO_SEARCH_NOTE
    history = _history(row)
    if history:
        record["history"] = history
    record["system"] = (
        WEB_CHECK_SYSTEM + _language_line(row) if searching else OWN_KNOWLEDGE_SYSTEM
    )
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
            web_search_engine=engine,
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
    record["cited_domains"] = cited_domains(citations)
    record["web_search"] = usage.get("web_search", searching)
    for key in (
        "web_search_via",
        "web_search_forced",
        "web_search_requests",
        "web_search_exclusion",
    ):
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
    public = checks_public(row)
    if public:
        answerable = verdict.behavior == ControlOutcome.WEB_SOURCED.value
    else:
        answerable = verdict.verdict is Verdict.CORRECT
    if answerable and mirror_only(citations, conf.web_check_mirror_domains):
        answerable = False
        record["mirror_only"] = True
        record["note"] = MIRROR_NOTE
    note = (PUBLIC_KNOWLEDGE if public else WEB_ANSWERABLE) if answerable else ""
    return WebVerdict(answerable, note, {"web_check": record})


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

    def __init__(self, conf: Settings) -> None:
        self.conf = conf
        self.summary = WebCheckSummary()
        self.provider = roles.filter_provider(conf)
        self.judge = roles.filter_judge_provider(conf)
        self.searching, self.engine = (
            search_for(conf, self.provider) if self.provider else (False, "")
        )
        self.stopped = ""
        self._streak = 0
        self._warned = False
        self._lock = threading.Lock()

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
