"""Questions of one article that ask the same fact: the later one is rejected
as written (``repeated_fact``), the earlier one stays.

The la diaria review of 17.11 found 7 repeats in 93 questions (19, 20, 34, 47,
61, 66, 70): a fill-in, a choice question and an open question built on one
figure of one sentence. The fixtures below are written after that pattern.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy import select

from syft_benchmark.config import PairStatus, Settings, SpaceConfig, StatusReason
from syft_benchmark.db import Job, QaPair, session_scope
from syft_benchmark.generation import decisions, gold, pipeline, repeats
from syft_benchmark.generation.extractive import FILL_IN_PREFIX
from syft_benchmark.generation.generators import GENERATORS
from syft_benchmark.generation.pair import Pair
from syft_benchmark.report import filter_view
from syft_benchmark.sources import Chunk, Document

from fakes import ChromaStub

SPACE = "pytest-repeated-facts"
JOB = "pytest-repeated-facts-job"

VOTES = (
    "El Frente Amplio obtuvo 450.000 votos en Montevideo en las elecciones "
    "departamentales de 2025, según la Corte Electoral."
)
RAMBLA = (
    "Carolina Cosse, intendenta de Montevideo, anunció que la rambla se cerrará "
    "al tránsito los domingos de 2026."
)
ARTICLE = f"{VOTES} {RAMBLA}"

QA_VOTES = (
    "¿Cuántos votos obtuvo el Frente Amplio en Montevideo en las elecciones "
    "departamentales de 2025, según la Corte Electoral?"
)
QA_RAMBLA = "¿Qué anunció Carolina Cosse, intendenta de Montevideo, sobre la rambla?"
MCQ_VOTES = (
    "¿Cuántos votos obtuvo el Frente Amplio en Montevideo en las elecciones "
    "departamentales de 2025?"
)
MCQ_PARTY = (
    "¿Qué partido obtuvo 450.000 votos en Montevideo en las elecciones "
    "departamentales de 2025?"
)

CHUNK = Chunk(
    chunk_id="ladiaria_0",
    doc_id="ladiaria",
    chunk_index=0,
    text=ARTICLE,
    file_name="ladiaria.md",
    headings="",
)
DOCUMENT = Document(
    doc_id="ladiaria",
    title="Elecciones en Montevideo",
    url="",
    source="la diaria",
    file_name="ladiaria.md",
    chunks=[CHUNK],
    published_at=datetime(2026, 11, 10, tzinfo=UTC),
)


def _fact(generator: str, question: str, answer: str, **meta: Any) -> repeats.Fact:
    evidence = gold.build_gold(
        generator, question, answer, meta, DOCUMENT, CHUNK.chunk_id, control=False
    )["evidence"]
    fact = repeats.fact_of(generator, question, answer, meta, evidence)
    assert fact is not None
    return fact


# --- what counts as the same fact --------------------------------------------


def test_one_figure_asked_three_ways_is_one_fact() -> None:
    qa = _fact("qa", QA_VOTES, "450.000 votos.")
    fill_in = _fact(
        "numeric_masking",
        f"{FILL_IN_PREFIX} El Frente Amplio obtuvo ______ votos en Montevideo en "
        "las elecciones departamentales de 2025, según la Corte Electoral.",
        "450.000",
    )
    mcq = _fact(
        "mcq",
        f"{MCQ_VOTES}\n  A) 450.000 votos\n  B) 350.000 votos",
        "A) 450.000 votos",
    )
    assert repeats.repeated(fill_in, qa)
    assert repeats.repeated(mcq, qa)
    assert repeats.repeated(mcq, fill_in)


def test_another_fact_of_the_same_sentence_is_not_a_repeat() -> None:
    votes = _fact("qa", QA_VOTES, "450.000 votos.")
    party = _fact("mcq", f"{MCQ_PARTY}\n  A) El Frente Amplio", "A) El Frente Amplio")
    assert not repeats.repeated(party, votes)


def test_the_same_words_in_another_sentence_are_not_a_repeat() -> None:
    votes = _fact("qa", QA_VOTES, "450.000 votos.")
    rambla = _fact(
        "qa", QA_RAMBLA, "Que la rambla se cerrará al tránsito los domingos de 2026."
    )
    assert not repeats.repeated(rambla, votes)


def test_unlocated_facts_repeat_only_when_near_equal() -> None:
    a = repeats.Fact("qa", "q1", frozenset({"450", "000", "votos"}), frozenset())
    b = repeats.Fact("qa", "q2", frozenset({"450", "000", "votos"}), frozenset())
    c = repeats.Fact("qa", "q3", frozenset({"450", "rambl", "cerra"}), frozenset())
    assert repeats.repeated(a, b)
    assert not repeats.repeated(c, a)


def test_kinds_without_a_fact_of_their_own_are_not_compared() -> None:
    for kind in ("unanswerable_property", "tiered_explanation"):
        assert repeats.fact_of(kind, QA_VOTES, "450.000 votos.", {}, []) is None


def test_a_year_alone_does_not_make_two_facts_one() -> None:
    first = _fact("qa", QA_VOTES, "450.000 votos, en 2025.")
    assert "2025" not in first.words


# --- through a build ----------------------------------------------------------


class _NoRotation:
    notes: list[str] = []

    def line(self) -> str:
        return ""


def _settings() -> Settings:
    return Settings(
        document_window_days=0,
        pairs_per_chunk=2,
        max_consecutive_failures=5,
        entity_check=False,
        concurrency=1,
    )


def _written(system: str) -> str:
    if system == GENERATORS["qa"].system.format(n=2):
        return json.dumps(
            [
                {"question": QA_VOTES, "answer": "450.000 votos."},
                {
                    "question": QA_RAMBLA,
                    "answer": "Que la rambla se cerrará al tránsito los domingos.",
                },
            ]
        )
    if system == GENERATORS["mcq"].system.format(n=2):
        return json.dumps(
            [
                {
                    "question": MCQ_VOTES,
                    "options": {
                        "A": "450.000 votos",
                        "B": "350.000 votos",
                        "C": "500.000 votos",
                        "D": "300.000 votos",
                    },
                    "correct": "A",
                },
                {
                    "question": MCQ_PARTY,
                    "options": {
                        "A": "El Frente Amplio",
                        "B": "El Partido Nacional",
                        "C": "El Partido Colorado",
                        "D": "Cabildo Abierto",
                    },
                    "correct": "A",
                },
            ]
        )
    # Any other check fails and keeps the questions.
    return "[]"


@pytest.mark.needs_db
def test_a_build_rejects_the_later_question_on_a_fact(
    monkeypatch: pytest.MonkeyPatch, clean: None
) -> None:
    monkeypatch.setattr(pipeline, "ChromaClient", ChromaStub)
    monkeypatch.setattr(pipeline, "load_documents", lambda *_: [DOCUMENT])
    monkeypatch.setattr(
        pipeline, "chat", lambda system, user, **_: (_written(system), {})
    )
    monkeypatch.setattr(pipeline, "rotate", lambda *a, **k: _NoRotation())

    report = pipeline.generate_for_space(
        SpaceConfig(key=SPACE, url="http://space:8080", endpoint="ep"),
        generators=("qa", "mcq"),
        settings=_settings(),
        job=JOB,
    )

    assert report.kinds["qa"].written == 2
    assert report.kinds["mcq"].written == 1
    assert report.kinds["mcq"].dropped == {"repeated fact": 1}
    with session_scope() as session:
        rows = list(
            session.execute(select(QaPair).where(QaPair.space == SPACE)).scalars()
        )
        for row in rows:
            session.expunge(row)
    by_stem = {row.question.split("\n", 1)[0]: row for row in rows}
    repeat = by_stem[MCQ_VOTES]
    original = by_stem[QA_VOTES]
    assert repeat.status == PairStatus.REJECTED.value
    assert repeat.status_reason == StatusReason.REPEATED_FACT.value
    assert repeat.status_note.startswith('repeated fact: the answer of qa "¿Cuántos')
    # The open question's unit was stored first: the repeat points at its row.
    assert repeat.meta[repeats.META] == {
        "qa_id": original.id,
        "generator": "qa",
        "question": QA_VOTES,
    }
    assert by_stem[MCQ_PARTY].status == PairStatus.PENDING.value
    assert original.status == PairStatus.PENDING.value

    with session_scope() as session:
        listed = filter_view.job_filter(session, Job(id=JOB, target=SPACE))
    (decision,) = [
        d
        for d in listed["items"]
        if d["reason_code"] == StatusReason.REPEATED_FACT.value
    ]
    assert decision["stage"] == decisions.WRITING
    assert decision["outcome"] == decisions.REMOVED


def _stored(question: str, answer: str, status: PairStatus) -> QaPair:
    meta = {
        gold.META: gold.build_gold(
            "qa", question, answer, {}, DOCUMENT, CHUNK.chunk_id, control=False
        )
    }
    return QaPair(
        id=uuid.uuid4().hex,
        space=SPACE,
        cohort="c1",
        collection="col",
        generator="qa",
        task_type="abstractive",
        doc_id=DOCUMENT.doc_id,
        chunk_id=CHUNK.chunk_id,
        document_title=DOCUMENT.title,
        file_name=DOCUMENT.file_name,
        question=question,
        answer=answer,
        distractors=[],
        context=ARTICLE,
        expected_behavior="answer",
        meta=meta,
        status=status.value,
        model="w",
        question_hash=pipeline.question_hash(question),
    )


@pytest.mark.needs_db
@pytest.mark.parametrize(
    ("status", "dropped"),
    [
        (PairStatus.PENDING, True),
        (PairStatus.ACTIVE, True),
        (PairStatus.REJECTED, False),
    ],
)
def test_a_question_stored_earlier_counts_unless_rejected(
    clean: None, status: PairStatus, dropped: bool
) -> None:
    from support import add_rows

    stored = _stored(QA_VOTES, "450.000 votos.", status)
    stored_id = stored.id
    add_rows(stored)
    fill_in = Pair(
        question=f"{FILL_IN_PREFIX} El Frente Amplio obtuvo ______ votos en "
        "Montevideo en las elecciones departamentales de 2025, según la Corte "
        "Electoral.",
        answer="450.000",
        distractors=[],
        meta={},
    )
    outcome = pipeline._Outcome(pairs={"numeric_masking": ([fill_in], [])})

    pipeline._drop_repeats(SPACE, "c1", DOCUMENT, CHUNK.chunk_id, outcome, Settings())

    kept, reasons = outcome.pairs["numeric_masking"]
    if not dropped:
        assert kept == [fill_in] and reasons == [] and not outcome.rejected
        return
    assert kept == [] and reasons == [pipeline.REPEATED_FACT]
    (item,) = outcome.rejected["numeric_masking"]
    assert item.reason is StatusReason.REPEATED_FACT
    assert item.pair.meta[repeats.META]["qa_id"] == stored_id
