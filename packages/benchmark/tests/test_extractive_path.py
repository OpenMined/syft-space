"""Fill-in-the-blank: the LLM writes the items, and older spaCy-made ones
still name their path."""

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
from syft_benchmark.generation.extractive import parse_combined
from syft_benchmark.report.export_xlsx import _masked_by
from syft_benchmark.sources import Chunk, Document

SPACE = "pytest-extractive-path"
KINDS = ("named_entity_masking", "numeric_masking", "temporal_masking")
GERMAN = (
    "Die Stadt Hamburg hat am Montag das neue Rathaus eröffnet, und der "
    "Bürgermeister war sehr stolz auf das Gebäude. Es wurde in nur zwei Jahren "
    "gebaut und kostet die Stadt mehr als zehn Millionen Euro."
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


def test_one_item_per_sentence() -> None:
    """A second blank in the same sentence tests the same passage again."""
    sentence = "Apple opened a new office in ______ on 5 October 2026."
    data = {
        "named_entity": [{"question": sentence, "answer": "Berlin"}],
        "temporal": [
            {
                "question": "Apple opened a new office in Berlin on ______.",
                "answer": "5 October 2026",
            }
        ],
    }
    masked = parse_combined(data, ("named_entity", "temporal"))
    assert [m.answer for m in masked["named_entity"]] == ["Berlin"]
    assert masked["temporal"] == []


def test_relative_dates_are_not_blanked() -> None:
    """ "This year" is given away by the date of the story, not learnt from it."""
    data = {
        "temporal": [
            {
                "question": "______ the company opened three new offices in Europe.",
                "answer": "This year",
            },
            {
                "question": "The plant closed ______ after the floods in the valley.",
                "answer": "two years ago",
            },
        ]
    }
    assert parse_combined(data, ("temporal",))["temporal"] == []


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
    assert _masked_by({"mode": "llm"}) == "LLM"
    # Older rows: cut by spaCy, or written by the LLM with a reason.
    spacy = {"mode": "spacy", "spacy_model": "en_core_web_sm"}
    assert _masked_by(spacy) == "spaCy en_core_web_sm"
    assert _masked_by({"mode": "llm", "llm_why": "llm mode"}) == "LLM"
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


@pytest.mark.skipif(not _db_ready(), reason="the benchmark database is unavailable")
def test_the_llm_writes_every_masking_kind(
    clean: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    documents = [_doc("de", GERMAN, added_at=datetime(2026, 10, 7, 9, tzinfo=UTC))]

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
    )

    report = pipeline.generate_for_space(
        SpaceConfig(key=SPACE, url="http://space:8080", endpoint="ep"),
        generators=KINDS,
        settings=conf,
    )

    with session_scope() as session:
        rows = session.scalars(select(QaPair).where(QaPair.space == SPACE)).all()
        pairs = [(r.generator, r.model, dict(r.meta)) for r in rows]
    assert sorted(p[0] for p in pairs) == ["named_entity_masking", "numeric_masking"]
    for _, model, meta in pairs:
        assert model == conf.generator_model
        assert meta["mode"] == "llm" and "llm_why" not in meta
        assert meta["article_date"] == "2026-10-07"
        assert meta["article_dated_by"] == "added"
    assert sum("system" in meta.get("writer", {}) for *_, meta in pairs) == 1

    names = report.kinds["named_entity_masking"].as_dict()
    assert names["written"] == 1 and "spacy" not in names
    assert report.kinds["temporal_masking"].as_dict()["written"] == 0
