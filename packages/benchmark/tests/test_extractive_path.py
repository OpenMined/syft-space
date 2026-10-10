"""Fill-in-the-blank: spaCy cuts what its model can label; the LLM writes the
rest, and the path is visible per question and per kind."""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy import delete, select

from syft_benchmark.config import Settings, SpaceConfig
from syft_benchmark.db import ProcessedUnit, QaPair, session_scope
from syft_benchmark.generation import pipeline
from syft_benchmark.generation.article_dates import article_stamp, backfill
from syft_benchmark.generation.extractive import mask_with_spacy
from syft_benchmark.generation.language import (
    LANGUAGE_UNKNOWN,
    choose_spacy_model,
    load_model,
    no_model_for,
)
from syft_benchmark.report.export_xlsx import _masked_by
from syft_benchmark.sources import Chunk, Document

SPACE = "pytest-extractive-path"
KINDS = ("named_entity_masking", "numeric_masking", "temporal_masking")
ENGLISH = (
    "Apple opened a new office in Berlin on 5 October 2026, the company said. "
    "The building cost 120 million euros and will employ about 400 people from "
    "across Germany. Tim Cook visited the site with the mayor of the city on "
    "Monday and spoke to the staff there."
)
GERMAN = (
    "Die Stadt Hamburg hat am Montag das neue Rathaus eröffnet, und der "
    "Bürgermeister war sehr stolz auf das Gebäude. Es wurde in nur zwei Jahren "
    "gebaut und kostet die Stadt mehr als zehn Millionen Euro."
)
MODELS = {"en": "en_core_web_sm", "de": "de_core_news_sm"}

needs_english = pytest.mark.skipif(
    load_model("en_core_web_sm") is None, reason="en_core_web_sm is not installed"
)


def _db_ready() -> bool:
    try:
        with session_scope() as session:
            session.execute(delete(QaPair).where(QaPair.space == SPACE))
        return True
    except Exception:  # noqa: BLE001 - the database may simply not be at hand
        return False


@pytest.fixture
def clean() -> Iterator[None]:
    def wipe() -> None:
        with session_scope() as session:
            session.execute(delete(QaPair).where(QaPair.space == SPACE))
            session.execute(delete(ProcessedUnit).where(ProcessedUnit.space == SPACE))

    wipe()
    yield
    wipe()


def _doc(doc_id: str, text: str, **dates: Any) -> Document:
    return Document(
        doc_id=doc_id,
        title=f"Article {doc_id}",
        url="",
        source="",
        file_name=f"{doc_id}.md",
        chunks=[
            Chunk(
                chunk_id=f"{doc_id}_0",
                doc_id=doc_id,
                chunk_index=0,
                text=text,
                file_name=f"{doc_id}.md",
                headings="",
            )
        ],
        **dates,
    )


@needs_english
def test_spacy_masks_an_english_passage() -> None:
    choice = choose_spacy_model(ENGLISH, Settings().spacy_models)
    assert (choice.model, choice.language, choice.why) == ("en_core_web_sm", "en", "")
    masked = mask_with_spacy(
        ENGLISH, choice.nlp, ("named_entity", "numeric", "temporal")
    )
    answers = {c: {m.answer for m in items} for c, items in masked.items()}
    assert {"Apple", "Berlin", "Tim Cook"} <= answers["named_entity"]
    assert "120 million" in answers["numeric"]
    assert "5 October 2026" in answers["temporal"]
    assert all("______" in m.question for items in masked.values() for m in items)


@needs_english
def test_why_the_llm_takes_a_passage() -> None:
    assert choose_spacy_model("Hub stores", MODELS).why == LANGUAGE_UNKNOWN
    if load_model("de_core_news_sm") is None:
        choice = choose_spacy_model(GERMAN, MODELS)
        assert choice.nlp is None and choice.why == no_model_for("de")


def test_article_stamp_follows_the_article_date_rule() -> None:
    day = datetime(2026, 10, 5, tzinfo=UTC)
    later = datetime(2026, 10, 8, 12, tzinfo=UTC)
    assert article_stamp(_doc("a", "", published_at=day, added_at=later)) == {
        "article_date": "2026-10-05",
        "article_dated_by": "published",
    }
    assert article_stamp(_doc("a", "", added_at=later)) == {
        "article_date": "2026-10-08",
        "article_dated_by": "added",
    }
    assert article_stamp(_doc("a", "")) == {}


@pytest.mark.skipif(not _db_ready(), reason="the benchmark database is unavailable")
def test_older_questions_get_their_article_date(clean: None) -> None:
    with session_scope() as session:
        for qa, doc in (("old-1", "a"), ("old-2", "b")):
            session.add(
                QaPair(
                    id=qa,
                    space=SPACE,
                    generator="qa",
                    doc_id=doc,
                    question=f"{qa}?",
                    answer="x",
                    model="gen/model",
                    question_hash=qa,
                    meta={"article_date": "2026-01-01"} if doc == "b" else {},
                )
            )
    day = datetime(2026, 10, 5, tzinfo=UTC)
    stamped = backfill(SPACE, [_doc("a", "", published_at=day), _doc("b", "")])
    assert stamped == 1
    with session_scope() as session:
        meta = {
            r.id: r.meta
            for r in session.scalars(select(QaPair).where(QaPair.space == SPACE))
        }
    assert meta["old-1"]["article_date"] == "2026-10-05"
    assert meta["old-2"]["article_date"] == "2026-01-01"


def test_masked_by_names_the_path() -> None:
    spacy = {"mode": "spacy", "spacy_model": "en_core_web_sm"}
    assert _masked_by(spacy) == "spaCy en_core_web_sm"
    llm = {"mode": "llm", "llm_why": "no spaCy model for 'de'"}
    assert _masked_by(llm) == "LLM: no spaCy model for 'de'"
    assert _masked_by({}) == ""


def _llm_reply(system: str, user: str, **_: Any) -> tuple[str, dict[str, Any]]:
    data = {
        "named_entity": [
            {
                "question": "Die Stadt ______ hat am Montag das neue Rathaus eröffnet.",
                "answer": "Hamburg",
                "entity_type": "GPE",
            }
        ],
        "numeric": [
            {
                "question": "Es kostet die Stadt mehr als ______ Millionen Euro.",
                "answer": "zehn",
                "entity_type": "CARDINAL",
            }
        ],
        "temporal": [],
    }
    return json.dumps(data), {}


@needs_english
@pytest.mark.skipif(not _db_ready(), reason="the benchmark database is unavailable")
def test_the_path_is_kept_per_question_and_per_kind(
    clean: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    documents = [
        _doc("en", ENGLISH, published_at=datetime(2026, 10, 5, tzinfo=UTC)),
        _doc("de", GERMAN, added_at=datetime(2026, 10, 7, 9, tzinfo=UTC)),
    ]

    class _Chroma:
        def __init__(self, *_: Any) -> None: ...

        def collection_id(self, _name: str) -> str:
            return "cid"

    monkeypatch.setattr(pipeline, "ChromaClient", _Chroma)
    monkeypatch.setattr(pipeline, "load_documents", lambda *_: documents)
    monkeypatch.setattr(pipeline, "chat", _llm_reply)
    conf = Settings(
        subject_url="https://openrouter.ai/api/v1",
        subject_key="sk-test",
        allow_external_models=True,
        external_hosts=["openrouter.ai"],
        document_window_days=0,
        pairs_per_chunk=3,
        chunks_per_run=5,
        concurrency=1,
        spacy_models=MODELS,
    )

    report = pipeline.generate_for_space(
        SpaceConfig(key=SPACE, url="http://space:8080", endpoint="ep"),
        generators=KINDS,
        settings=conf,
    )

    with session_scope() as session:
        rows = session.scalars(select(QaPair).where(QaPair.space == SPACE)).all()
        pairs = [(r.doc_id, r.generator, r.model, dict(r.meta)) for r in rows]
    english = [p for p in pairs if p[0] == "en"]
    german = [p for p in pairs if p[0] == "de"]
    assert english and german
    for _, _, model, meta in english:
        assert model == "spacy:en_core_web_sm"
        assert meta["mode"] == "spacy" and meta["spacy_model"] == "en_core_web_sm"
        assert meta["language"] == "en" and "writer" not in meta
        assert meta["article_date"] == "2026-10-05"
    why = no_model_for("de")
    for _, _, model, meta in german:
        assert model.startswith("llm:")
        assert meta["mode"] == "llm" and meta["llm_why"] == why
        assert meta["article_date"] == "2026-10-07"
        assert meta["article_dated_by"] == "added"

    names = report.kinds["named_entity_masking"].as_dict()
    spacy_names = sum(1 for p in english if p[1] == "named_entity_masking")
    assert names["spacy"] == spacy_names > 0
    assert names["llm"] == 1 and names["llm_why"] == {why: 1}
    temporal = report.kinds["temporal_masking"].as_dict()
    assert temporal["llm"] == 0 and temporal["llm_why"] == {why: 1}
