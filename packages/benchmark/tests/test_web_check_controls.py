"""The web check of control questions, reprints of the publisher and checks
repeated as a question ages, with the models stubbed."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import select

from syft_benchmark.config import (
    PairStatus,
    Settings,
    SpaceConfig,
    StatusReason,
    WebCheckEngine,
)
from syft_benchmark.db import QaPair, session_scope
from syft_benchmark.generation import control, filter_stage, web_check
from syft_benchmark.generation.generators import GENERATORS
from syft_benchmark.llm.roles import web_search_for
from syft_benchmark.runs import judge as run_judge

from fakes import OPENROUTER, openrouter_settings

SPACE = "pytest-web-check-controls"
COHORT = "c1"
MIRROR = "https://www.iberonoticias.com/articulo/abc"
OTHER = "https://www.elpais.com.uy/informacion/x"
TRICK = "unanswerable_property"
PREMISE = "false_premise"


def _settings(**kwargs: Any) -> Settings:
    base: dict[str, Any] = {
        "filter_model": "openai/gpt-5.1",
        "judge_url": OPENROUTER,
        "judge_key": "sk-test",
        "judge_model": "anthropic/claude-opus-5",
        "concurrency": 2,
        "web_check_mirror_domains": ["iberonoticias.com", "elnotero.com"],
    }
    return openrouter_settings(**{**base, **kwargs})


def _space() -> SpaceConfig:
    return SpaceConfig(key=SPACE, url="http://space:8080", endpoint="ep")


def _pair(
    pair_id: str,
    generator: str = "qa",
    *,
    answer: str = "Harbourton council",
    status: str = PairStatus.PENDING.value,
    meta: dict[str, Any] | None = None,
) -> QaPair:
    spec = GENERATORS[generator]
    return QaPair(
        id=pair_id,
        space=SPACE,
        generator=generator,
        task_type=spec.task_type,
        expected_behavior=spec.expected.value,
        doc_id="d1",
        cohort=COHORT,
        question=f"Question {pair_id}?",
        answer=answer,
        context=f"Harbourton council restored the lighthouse. {answer}",
        meta={"grading": spec.grading, **(meta or {})},
        status=status,
        model="test-model",
        question_hash=uuid.uuid4().hex,
    )


def _rows() -> dict[str, QaPair]:
    with session_scope() as session:
        rows = list(
            session.execute(select(QaPair).where(QaPair.space == SPACE)).scalars()
        )
        for row in rows:
            session.expunge(row)
    return {row.id: row for row in rows}


def _archive(question: str) -> list[str]:
    """Live retrieval: nothing on a trick question, the answer otherwise."""
    return [] if "tr" in question else ["Harbourton council restored it."]


class _Web:
    """The web check model and its judges, stubbed per pair id."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.cites: dict[str, list[str]] = {}
        self.right: set[str] = set()
        self.behavior = "declined"
        # The behaviour judge's reading per pair id; ``behavior`` otherwise.
        self.behaviors: dict[str, str] = {}
        self.calls: list[dict[str, Any]] = []
        monkeypatch.setattr(web_check, "chat", self.web_chat)
        monkeypatch.setattr(run_judge, "chat", self.judge_chat)
        monkeypatch.setattr(
            control, "chat", lambda *_a, **_k: ('{"answered": true}', {})
        )

    def web_chat(
        self, system: str, user: str, **kwargs: Any
    ) -> tuple[str, dict[str, Any]]:
        self.calls.append({"system": system, "user": user, **kwargs})
        pair_id = user.removeprefix("Question ").removesuffix("?")
        citations = [{"url": url, "title": "t"} for url in self.cites.get(pair_id, [])]
        return f"web answer for {pair_id}", {
            "web_search": "plugin",
            "citations": citations,
        }

    def judge_chat(
        self, system: str, user: str, **_: Any
    ) -> tuple[str, dict[str, Any]]:
        if "How did the model handle the question?" in user:
            behavior = next(
                (b for pid, b in self.behaviors.items() if f"for {pid}\n" in user),
                self.behavior,
            )
            return f'{{"behavior": "{behavior}", "reasoning": "stub"}}', {}
        right = any(f"web answer for {pid}" in user for pid in self.right)
        return f'{{"correct": {"true" if right else "false"}}}', {}


needs_db = pytest.mark.needs_db


@needs_db
def test_a_false_premise_the_web_corrects_or_confirms_is_rejected(
    clean: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Graded by behaviour, as the run grades it: a correction makes it web
    answerable; specifics its search backs mean the "false" detail is true
    elsewhere (Tempo, Danantara's US$ 5 billion)."""
    correction = "The council restored the lighthouse."
    ids = ("fp1", "fp2", "fp3", "fp4")
    with session_scope() as session:
        session.add_all(
            [
                _pair(i, PREMISE, answer=correction, meta={"premise": "razed"})
                for i in ids
            ]
        )
    web = _Web(monkeypatch)
    web.behaviors = {
        "fp1": "corrected",
        "fp2": "made_up",
        "fp3": "web_sourced",
        "fp4": "web_sourced",
    }
    web.cites = {"fp1": [OTHER], "fp2": [], "fp3": [OTHER], "fp4": [MIRROR]}

    report = filter_stage.filter_pending(
        _space(), settings=_settings(), retrieve=_archive
    )
    rows = _rows()

    assert {call["user"] for call in web.calls} == {f"Question {i}?" for i in ids}
    assert (rows["fp1"].status, rows["fp1"].status_reason) == (
        PairStatus.REJECTED.value,
        StatusReason.WEB_ANSWERABLE.value,
    )
    assert rows["fp1"].meta["web_check"]["verdict"] == "correct"
    assert rows["fp2"].status == PairStatus.ACTIVE.value
    assert (rows["fp3"].status, rows["fp3"].status_reason) == (
        PairStatus.REJECTED.value,
        StatusReason.PREMISE_CONFIRMED.value,
    )
    assert rows["fp3"].status_note == web_check.PREMISE_CONFIRMED
    assert rows["fp3"].meta["web_check"]["behavior"] == "web_sourced"
    # Backed by a reprint of the publisher only: not public.
    assert rows["fp4"].status == PairStatus.ACTIVE.value
    assert rows["fp4"].meta["web_check"]["mirror_only"] is True
    assert report.web is not None and report.web.removed == 2


@needs_db
def test_an_answer_citing_only_reprints_keeps_the_question(
    clean: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    with session_scope() as session:
        session.add_all([_pair("qa1"), _pair("qa2"), _pair("tr1", TRICK, answer="")])
    web = _Web(monkeypatch)
    web.right = {"qa1", "qa2"}
    web.behavior = "web_sourced"
    web.cites = {
        "qa1": [MIRROR, "https://elnotero.com/civila/"],
        "qa2": [MIRROR, OTHER],
        "tr1": [MIRROR],
    }

    filter_stage.filter_pending(_space(), settings=_settings(), retrieve=_archive)
    rows = _rows()

    for kept in ("qa1", "tr1"):
        record = rows[kept].meta["web_check"]
        assert rows[kept].status == PairStatus.ACTIVE.value, kept
        assert record["mirror_only"] is True
        assert record["note"] == web_check.MIRROR_NOTE
    assert rows["qa1"].meta["web_check"]["cited_domains"] == [
        "elnotero.com",
        "iberonoticias.com",
    ]
    # One independent source is enough to make it public.
    assert rows["qa2"].status_reason == StatusReason.WEB_ANSWERABLE.value
    assert rows["qa2"].meta["web_check"]["cited_domains"] == [
        "elpais.com.uy",
        "iberonoticias.com",
    ]


@needs_db
def test_the_web_check_searches_with_its_own_engine_cap_and_language(
    clean: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    spanish = (
        "El consejo de Harbourton restauró el faro después de la tormenta y "
        "lo reabrió en marzo para los vecinos de la ciudad."
    )
    pair = _pair("qa1", answer="El consejo de Harbourton")
    pair.context = spanish
    with session_scope() as session:
        session.add(pair)
    web = _Web(monkeypatch)
    conf = _settings(web_search_engine="native", web_check_max_calls=5)

    filter_stage.filter_pending(_space(), settings=conf, retrieve=_archive)

    (call,) = web.calls
    assert call["web_search_engine"] == "plugin"
    assert "search in Spanish first" in call["system"]
    record = _rows()["qa1"].meta["web_check"]
    assert (record["search"], record["max_calls"]) == ("plugin", 5)
    assert record["judge"] == "anthropic/claude-sonnet-5"


@needs_db
def test_an_aged_check_is_repeated_and_the_earlier_one_kept(
    clean: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    old = (datetime.now(UTC) - timedelta(days=10)).isoformat(timespec="seconds")
    fresh = (datetime.now(UTC) - timedelta(days=2)).isoformat(timespec="seconds")
    model = "openai/gpt-5.1"

    def checked(at: str, **extra: Any) -> dict[str, Any]:
        return {
            "web_check": {"model": model, "verdict": "abstain", "checked_at": at}
            | extra
        }

    active = PairStatus.ACTIVE.value
    with session_scope() as session:
        session.add_all(
            [
                _pair("old-qa", status=active, meta=checked(old)),
                _pair("new-qa", status=active, meta=checked(fresh)),
                _pair(
                    "old-tr",
                    TRICK,
                    answer="",
                    status=active,
                    meta=checked(old, behavior="declined"),
                ),
            ]
        )
    web = _Web(monkeypatch)
    web.behavior = "web_sourced"
    web.cites = {"old-tr": [OTHER]}
    web.right = {"old-qa"}

    off = filter_stage.filter_pending(
        _space(), settings=_settings(), recheck_cohort=COHORT
    )
    assert web.calls == [] and off.web is None

    filter_stage.filter_pending(
        _space(),
        settings=_settings(web_check_recheck_days=7),
        recheck_cohort=COHORT,
        job_id="job-recheck",
    )
    rows = _rows()

    assert {call["user"] for call in web.calls} == {
        "Question old-qa?",
        "Question old-tr?",
    }
    assert rows["old-qa"].status_reason == StatusReason.WEB_ANSWERABLE.value
    assert rows["old-tr"].status_reason == StatusReason.PUBLIC_KNOWLEDGE.value
    assert rows["new-qa"].status == active
    history = rows["old-tr"].meta["web_check"]["history"]
    assert history == [
        {
            "checked_at": old,
            "model": model,
            "verdict": "abstain",
            "behavior": "declined",
        }
    ]
    assert rows["old-tr"].meta["web_check"]["checked_at"] > old
    assert rows["old-tr"].meta["screening"][-1]["job_id"] == "job-recheck"


# --- the pieces --------------------------------------------------------------


def _row(meta: dict[str, Any] | None = None) -> QaPair:
    return QaPair(id="x", generator="qa", question="Q?", answer="A", meta=meta or {})


def test_mirror_only_needs_every_citation_on_a_mirror() -> None:
    mirrors = ["iberonoticias.com", "example.org/reprints"]

    def cite(*urls: str) -> list[dict[str, str]]:
        return [{"url": url, "title": ""} for url in urls]

    assert web_check.mirror_only(cite(MIRROR), mirrors)
    assert web_check.mirror_only(cite("https://news.iberonoticias.com/a"), mirrors)
    assert web_check.mirror_only(cite("https://example.org/reprints/1"), mirrors)
    assert not web_check.mirror_only(cite("https://example.org/news/1"), mirrors)
    assert not web_check.mirror_only(cite(MIRROR, OTHER), mirrors)
    assert not web_check.mirror_only(cite("https://notiberonoticias.com/a"), mirrors)
    # No citations: an answer from the model's own knowledge stays public.
    assert not web_check.mirror_only([], mirrors)
    assert not web_check.mirror_only(cite(MIRROR), [])


def test_a_recheck_is_due_only_when_on_and_old_enough() -> None:
    now = datetime(2026, 11, 22, tzinfo=UTC)

    def at(days: int, **extra: Any) -> QaPair:
        stamp = (now - timedelta(days=days)).isoformat()
        return _row({"web_check": {"verdict": "abstain", "checked_at": stamp} | extra})

    on = Settings(web_check_recheck_days=7)
    assert web_check.recheck_due(at(7), on, now)
    assert not web_check.recheck_due(at(6), on, now)
    assert not web_check.recheck_due(at(30), Settings(), now)
    assert not web_check.recheck_due(at(30, error="down"), on, now)
    assert not web_check.recheck_due(_row({"web_check": {"skipped": "x"}}), on, now)


def test_the_web_check_names_its_engine_whatever_the_tested_models_use() -> None:
    conf = Settings(web_search_engine="native")
    native = "openai/gpt-5.1"

    assert conf.web_check_engine is WebCheckEngine.PLUGIN
    assert web_search_for(conf, "filter", native) == (True, "plugin")
    assert web_search_for(conf, "closed_book", native) == (True, "native")
    own = Settings(web_check_engine="native", web_search_engine="plugin")
    assert web_search_for(own, "filter", native) == (True, "native")
    with pytest.raises(ValueError):
        Settings(web_check_engine="auto")


def test_the_web_check_defaults() -> None:
    conf = Settings()

    assert conf.filter_judge_model == "anthropic/claude-sonnet-5"
    assert conf.web_check_max_calls == 3
    assert conf.web_check_recheck_days == 0
    assert conf.web_check_mirror_domains == []
    assert Settings(
        web_check_mirror_domains=["https://www.Elnotero.com/"]
    ).web_check_mirror_domains == ["www.elnotero.com"]


def test_a_mirror_given_with_www_matches_its_pages() -> None:
    mirrors = Settings(web_check_mirror_domains=["www.elnotero.com"])
    cited = [{"url": "https://elnotero.com/civila/", "title": ""}]

    assert web_check.mirror_only(cited, mirrors.web_check_mirror_domains)
