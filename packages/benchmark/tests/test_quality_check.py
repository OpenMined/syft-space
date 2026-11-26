"""The quality check: one model call per unit, with the article, judges each
question in its own language; a question that fails is rejected as written.

The English patterns of quality.py still drop drafts first; this check is
what screens a Spanish corpus. A failed call keeps the questions.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from sqlalchemy import select

from syft_benchmark.config import PairStatus, Settings, SpaceConfig, StatusReason
from syft_benchmark.db import Job, QaPair, session_scope
from syft_benchmark.generation import decisions, pipeline, quality_check
from syft_benchmark.generation.extractive import FILL_IN_PREFIX
from syft_benchmark.generation.generators import GENERATORS
from syft_benchmark.generation.pair import Pair
from syft_benchmark.generation.quality import reject_reason
from syft_benchmark.llm import LLMError, Provider, cost
from syft_benchmark.report import filter_view
from syft_benchmark.sources import Chunk, Document

from fakes import ChromaStub

SPACE = "pytest-quality-check"
JOB = "pytest-quality-job"

ARTICLE = (
    "El intendente de Montevideo, Mario Bergara, anunció el martes 4 de "
    "noviembre de 2026 un nuevo plan de transporte que reduce el boleto a 30 "
    "pesos para estudiantes. «Es una medida de justicia», dijo Bergara. "
    "«Vamos a ampliar las líneas nocturnas», agregó. El plan comenzará a regir "
    "el 1 de marzo de 2027 y costará 450 millones de pesos al año, según la "
    "Intendencia de Montevideo."
)

# Regression cases of the la diaria review, 17.11.2026.
SOURCE_REF = "Según el artículo, ¿cuánto costará el plan de transporte al año?"
PRONOUN = "¿Qué anunció él el martes sobre el boleto para estudiantes?"
SEVERAL = "¿Qué dijo Mario Bergara, intendente de Montevideo, sobre el plan?"
GOOD = (
    "¿A cuánto reduce el boleto para estudiantes el plan de transporte anunciado "
    "por el intendente de Montevideo, Mario Bergara, en noviembre de 2026?"
)
QUOTE_FILL = f"{FILL_IN_PREFIX} «Es una medida de ______», dijo Bergara."

REPLY = json.dumps(
    [
        {"index": 1, "fails": {"source_reference": "'Según el artículo'"}},
        {"index": 2, "fails": {"unanchored": "'él' names no one"}},
        {
            "index": 3,
            "fails": {"several_answers": "Bergara says two things in the article"},
        },
        {"index": 4, "fails": {}},
    ]
)

PROVIDER = Provider(
    role="generator", url="http://ollama:11434/v1", api_key="", model="w"
)


def _settings(**kwargs: Any) -> Settings:
    base: dict[str, Any] = {
        "document_window_days": 0,
        "pairs_per_chunk": 4,
        "max_consecutive_failures": 5,
        "entity_check": False,
        "quality_check": True,
    }
    return Settings(**{**base, **kwargs})


def _doc(text: str = ARTICLE) -> Document:
    chunk = Chunk(
        chunk_id="ladiaria_0",
        doc_id="ladiaria",
        chunk_index=0,
        text=text,
        file_name="ladiaria.md",
        headings="",
    )
    return Document(
        doc_id="ladiaria",
        title="Nuevo plan de transporte",
        url="",
        source="la diaria",
        file_name="ladiaria.md",
        chunks=[chunk],
    )


def _pair(question: str, answer: str = "30 pesos") -> Pair:
    return Pair(question=question, answer=answer, distractors=[], meta={})


class _Checker:
    """The quality check call, stubbed: what it was asked, what it says."""

    def __init__(self, reply: str | Exception = REPLY) -> None:
        self.reply = reply
        self.calls: list[dict[str, Any]] = []

    def __call__(
        self, system: str, user: str, **kwargs: Any
    ) -> tuple[str, dict[str, Any]]:
        self.calls.append({"system": system, "user": user, **kwargs})
        if isinstance(self.reply, Exception):
            raise self.reply
        return self.reply, {"cost_usd": 0.003, "latency_s": 2.5}


def _screen(
    made: dict[str, list[Pair]], checker: _Checker, **kwargs: Any
) -> tuple[dict[str, list[Pair]], dict[str, list[tuple[Pair, str]]], dict[str, Any]]:
    doc = _doc()
    return quality_check.screen(
        made,
        doc,
        doc.chunks[0],
        language="es",
        conf=_settings(**kwargs),
        provider=PROVIDER,
        chat=checker,
        headroom=100,
    )


# --- the English patterns pass Spanish, which is why the check exists ----------


@pytest.mark.parametrize("question", [SOURCE_REF, PRONOUN, SEVERAL])
def test_the_english_patterns_pass_the_spanish_regressions(question: str) -> None:
    assert reject_reason(question, ARTICLE, task_type="abstractive") is None


# --- the prompt -----------------------------------------------------------------


def test_every_kind_has_its_checks() -> None:
    assert set(quality_check.CHECKS) == set(GENERATORS)
    for checks in quality_check.CHECKS.values():
        assert {quality_check.SOURCE_REFERENCE, quality_check.UNANCHORED} <= set(checks)
        assert set(checks) <= set(quality_check.LABELS)


def test_answer_checks_are_for_ordinary_kinds_only() -> None:
    for key, spec in GENERATORS.items():
        checks = set(quality_check.CHECKS[key])
        if spec.is_control or key in ("two_truths_one_lie", "tiered_explanation"):
            assert not checks & {
                quality_check.UNSUPPORTED,
                quality_check.SEVERAL_ANSWERS,
                quality_check.OBVIOUS,
            }
        if spec.task_type == "extractive":
            assert quality_check.QUOTE in checks
            assert quality_check.UNSUPPORTED not in checks


def test_the_prompt_names_the_language_the_checks_and_the_article() -> None:
    doc = _doc()
    user = quality_check.user_prompt(
        doc,
        doc.chunks[0],
        [("qa", _pair(GOOD)), ("false_premise", _pair(PRONOUN, "not true"))],
        "es",
    )
    assert "Language: Spanish" in user
    assert "Outlet: la diaria" in user
    assert ARTICLE in user
    assert "1. Checks: source_reference, unanchored, unsupported_wording" in user
    assert "Answer: 30 pesos" in user
    # A control question is checked for self-sufficiency only: no answer shown.
    assert "2. Checks: source_reference, unanchored\n" in user
    assert "Answer: not true" not in user
    for code in quality_check.LABELS:
        assert f"- {code}:" in quality_check.SYSTEM


def test_a_passage_past_the_cut_is_still_shown() -> None:
    long_text = "x " * 7000 + "Pasaje final con el dato."
    doc = _doc(long_text)
    shown = quality_check.article(doc, doc.chunks[0])
    assert shown.endswith(doc.chunks[0].text[:6000])


# --- the reply -----------------------------------------------------------------


def test_the_reply_is_parsed_by_question() -> None:
    asked = [quality_check.CHECKS["qa"]] * 4
    verdicts = quality_check.parse(REPLY, asked)
    assert [verdicts[i].ok for i in range(4)] == [False, False, False, True]
    assert verdicts[1].note() == "quality check: no antecedent ('él' names no one)"


def test_a_check_not_asked_is_ignored() -> None:
    reply = '[{"index": 1, "fails": {"obvious": "general knowledge"}}]'
    verdicts = quality_check.parse(reply, [quality_check.CHECKS["false_premise"]])
    assert verdicts[0].ok


def test_an_unreadable_reply_is_no_verdict() -> None:
    with pytest.raises(LLMError):
        quality_check.parse("No puedo evaluar.", [("unanchored",)])
    with pytest.raises(LLMError):
        quality_check.parse('[{"index": 7, "fails": {}}]', [("unanchored",)])


# --- the check on a unit --------------------------------------------------------


def test_the_spanish_regressions_are_rejected_and_the_good_one_is_kept() -> None:
    checker = _Checker()
    kept, rejected, call = _screen(
        {"qa": [_pair(SOURCE_REF), _pair(PRONOUN), _pair(SEVERAL), _pair(GOOD)]},
        checker,
    )
    assert [p.question for p in kept["qa"]] == [GOOD]
    assert [p.question for p, _ in rejected["qa"]] == [SOURCE_REF, PRONOUN, SEVERAL]
    notes = [note for _, note in rejected["qa"]]
    assert notes[0] == "quality check: refers to the source ('Según el artículo')"
    assert notes[2].startswith("quality check: several correct answers")

    record = rejected["qa"][1][0].meta[quality_check.META]
    assert record["outcome"] == decisions.REMOVED
    assert record["language"] == "es"
    assert record["checks"]["unanchored"] == "fail"
    assert record["checks"]["source_reference"] == "pass"
    assert record["reasons"] == {"unanchored": "'él' names no one"}
    good = kept["qa"][0].meta[quality_check.META]
    assert good["outcome"] == decisions.KEPT
    assert set(good["checks"].values()) == {"pass"}

    # One call for the unit, to the writer's provider, charged to the writer.
    (asked,) = checker.calls
    assert asked["provider"] is PROVIDER
    assert asked["role"] == cost.WRITER
    assert asked["max_tokens"] == quality_check.TOKENS_PER_QUESTION * 4 + 100
    assert not asked.get("web_search")
    assert call["model"] == "w" and call["reply"] == REPLY
    assert call["cost_usd"] == 0.003


def test_a_quoted_fill_in_is_rejected() -> None:
    reply = '[{"index": 1, "fails": {"quote": "Bergara\'s own words"}}]'
    kept, rejected, _ = _screen(
        {"named_entity_masking": [_pair(QUOTE_FILL, "justicia")]}, _Checker(reply)
    )
    assert kept["named_entity_masking"] == []
    (pair, note), *_ = rejected["named_entity_masking"]
    assert note == "quality check: a quote (Bergara's own words)"


@pytest.mark.parametrize("reply", [LLMError("down"), "not json at all"])
def test_a_failed_check_keeps_the_questions(reply: str | Exception) -> None:
    kept, rejected, _ = _screen({"qa": [_pair(PRONOUN), _pair(GOOD)]}, _Checker(reply))
    assert len(kept["qa"]) == 2 and rejected["qa"] == []
    for pair in kept["qa"]:
        record = pair.meta[quality_check.META]
        assert record["outcome"] == decisions.FAILED and record["error"]
        assert set(record["checks"].values()) == {"unchecked"}


def test_the_setting_turns_the_check_off() -> None:
    checker = _Checker()
    kept, rejected, call = _screen(
        {"qa": [_pair(PRONOUN)]}, checker, quality_check=False
    )
    assert checker.calls == [] and call == {}
    assert kept["qa"][0].meta == {} and rejected["qa"] == []


def test_the_model_setting_swaps_the_model_not_the_address() -> None:
    chosen = quality_check.provider(
        _settings(quality_check_model="google/gemini-flash-lite"), PROVIDER
    )
    assert chosen.model == "google/gemini-flash-lite"
    assert (chosen.url, chosen.role) == (PROVIDER.url, PROVIDER.role)
    assert quality_check.provider(_settings(), PROVIDER) is PROVIDER


# --- through a build -------------------------------------------------------------


@pytest.mark.needs_db
def test_a_build_stores_the_rejects_with_their_verdicts(
    monkeypatch: pytest.MonkeyPatch, clean: None
) -> None:
    written = json.dumps(
        [
            {"question": SOURCE_REF, "answer": "450 millones de pesos al año."},
            {"question": GOOD, "answer": "A 30 pesos."},
        ]
    )
    reply = json.dumps(
        [
            {"index": 1, "fails": {"source_reference": "'Según el artículo'"}},
            {"index": 2, "fails": {}},
        ]
    )
    checker = _Checker(reply)

    def chat(system: str, user: str, **kwargs: Any) -> tuple[str, dict[str, Any]]:
        if system == quality_check.SYSTEM:
            return checker(system, user, **kwargs)
        return written, {"cost_usd": 0.01}

    monkeypatch.setattr(pipeline, "ChromaClient", ChromaStub)
    monkeypatch.setattr(pipeline, "load_documents", lambda *_: [_doc()])
    monkeypatch.setattr(pipeline, "chat", chat)
    monkeypatch.setattr(pipeline, "rotate", lambda *a, **k: _NoRotation())

    report = pipeline.generate_for_space(
        SpaceConfig(key=SPACE, url="http://space:8080", endpoint="ep"),
        generators=("qa",),
        settings=_settings(),
        job=JOB,
    )

    assert len(checker.calls) == 1
    assert "Language: Spanish" in checker.calls[0]["user"]
    assert report.kinds["qa"].written == 1
    assert report.kinds["qa"].dropped == {"quality check": 1}
    with session_scope() as session:
        rows = {
            row.question: row
            for row in session.execute(
                select(QaPair).where(QaPair.space == SPACE)
            ).scalars()
        }
        for row in rows.values():
            session.expunge(row)
    bad, good = rows[SOURCE_REF], rows[GOOD]
    assert bad.status == PairStatus.REJECTED.value
    assert bad.status_reason == StatusReason.QUALITY.value
    assert bad.status_note == (
        "quality check: refers to the source ('Según el artículo')"
    )
    assert bad.meta[quality_check.META]["checks"]["source_reference"] == "fail"
    assert good.status == PairStatus.PENDING.value
    # The call's texts sit on one pair of the unit, its id on both.
    records = [r.meta[quality_check.META] for r in (bad, good)]
    assert records[0]["call"] == records[1]["call"]
    assert sum("system" in r for r in records) == 1

    with session_scope() as session:
        listed = filter_view.job_filter(session, Job(id=JOB, target=SPACE))
    (decision,) = listed["items"]
    assert decision["reason_code"] == StatusReason.QUALITY.value
    assert decision["stage"] == decisions.WRITING
    assert decision["outcome"] == decisions.REMOVED


class _NoRotation:
    notes: list[str] = []

    def line(self) -> str:
        return ""
