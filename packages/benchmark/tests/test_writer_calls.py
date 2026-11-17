"""Writer calls that dropped drafts or failed are kept per job, one row per call,
and listed per kind."""

from __future__ import annotations

import dataclasses
import json
import uuid
from collections import Counter
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from syft_benchmark.config import JobState, Settings, SpaceConfig
from syft_benchmark.control.jobs import discard_run
from syft_benchmark.db import (
    Job,
    QaPair,
    WriterCall,
    session_scope,
)
from syft_benchmark.generation import pipeline, recorded, writer_log
from syft_benchmark.generation.generators import GENERATORS
from syft_benchmark.generation.pair import Dropped, Pair
from syft_benchmark.llm import LLMError
from syft_benchmark.report import writing_view
from syft_benchmark.sources import Chunk, Document

from fakes import ChromaStub, openrouter_settings
from support import console_auth

KEY = "pytest-writer-calls"
JOB = "pytest-writer-calls-job"


def _settings(**kwargs: Any) -> Settings:
    base: dict[str, Any] = {
        "concurrency": 1,
        "document_window_days": 0,
        "entity_check": False,
    }
    return openrouter_settings(**{**base, **kwargs})


def _documents(text: str, count: int = 1) -> list[Document]:
    return [
        Document(
            doc_id=f"doc{d}",
            title=f"Doc {d}",
            url="",
            source="",
            file_name=f"doc{d}.md",
            chunks=[
                Chunk(
                    chunk_id=f"doc{d}_0",
                    doc_id=f"doc{d}",
                    chunk_index=0,
                    text=f"{text} ({d})",
                    file_name=f"doc{d}.md",
                    headings="",
                )
            ],
        )
        for d in range(count)
    ]


def _generate(
    monkeypatch: pytest.MonkeyPatch,
    chat: Any,
    *,
    generators: tuple[str, ...] = ("qa",),
    documents: list[Document] | None = None,
    **conf: Any,
) -> pipeline.GenerationReport:
    monkeypatch.setattr(pipeline, "ChromaClient", ChromaStub)
    monkeypatch.setattr(
        pipeline,
        "load_documents",
        lambda *_: documents or _documents("The council restored the lighthouse."),
    )
    monkeypatch.setattr(pipeline, "chat", chat)
    return pipeline.generate_for_space(
        SpaceConfig(key=KEY, url="http://space:8080", endpoint="ep"),
        generators=generators,
        settings=_settings(**conf),
        job=JOB,
    )


def _kept() -> list[dict[str, Any]]:
    with session_scope() as session:
        return list(
            writing_view.job_writing(session, JOB, limit=200)["items"]  # type: ignore[arg-type]
        )


def _reply(system: str, user: str, **_: Any) -> tuple[str, dict[str, Any]]:
    return '[{"x": 1}]', {"cost_usd": 0.02, "latency_s": 1.5}


@pytest.mark.needs_db
def test_a_call_that_dropped_drafts_is_kept_with_them(
    clean: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    def clean_items(items: Any, n: int, whole: str) -> tuple[list[Pair], list[Any]]:
        good = [
            Pair(question=f"Q{uuid.uuid4().int}?", answer="A", distractors=[], meta={})
            for _ in range(3)
        ]
        return good, [
            Dropped("a demonstrative without an antecedent", "What did this do?", "X")
        ]

    monkeypatch.setitem(
        GENERATORS, "qa", dataclasses.replace(GENERATORS["qa"], clean=clean_items)
    )
    report = _generate(
        monkeypatch,
        _reply,
        documents=_documents("The council restored the lighthouse.", 2),
        pairs_per_chunk=2,
        chunks_per_run=2,
    )

    kept = _kept()
    assert len(kept) == 2
    first, second = kept
    assert first["generator"] == "qa"
    assert first["dropped"] == [
        {
            "question": "What did this do?",
            "answer": "X",
            "reason": "a demonstrative without an antecedent",
        }
    ]
    # The budget is four: two of the second passage's three go over it.
    assert [d["reason"] for d in second["dropped"]] == [
        "a demonstrative without an antecedent",
        pipeline.OVER_BUDGET,
        pipeline.OVER_BUDGET,
    ]
    dropped = Counter(d["reason"] for call in kept for d in call["dropped"])
    assert dropped == Counter(report.kinds["qa"].dropped)

    with session_scope() as session:
        rows = session.scalars(
            select(QaPair).where(QaPair.space == KEY, QaPair.job_id == JOB)
        ).all()
        stored = {r.meta["writer"]["call"] for r in rows}
        texts = session.scalars(
            select(WriterCall.system).where(WriterCall.job_id == JOB)
        ).all()
    assert first["call"] in stored
    # The system prompt is stored once per build and served on every call.
    assert sorted(texts, key=bool) == ["", first["system"]]
    assert first["system"] == second["system"] != ""
    assert first["user"].count(recorded.PASSAGE_MARK) == 1
    assert first["passage"] not in first["user"]
    assert first["passage"].startswith("The council restored the lighthouse.")
    assert first["reply"] == '[{"x": 1}]'
    assert (first["cost_usd"], first["latency_s"]) == (0.02, 1.5)
    assert first["document_title"] and first["file_name"].endswith(".md")
    assert first["error"] is None and first["at"]


@pytest.mark.needs_db
def test_a_call_that_lost_nothing_is_not_kept(
    clean: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    def clean_items(items: Any, n: int, whole: str) -> tuple[list[Pair], list[Any]]:
        return [
            Pair(question="What was restored?", answer="A", distractors=[], meta={})
        ], []

    monkeypatch.setitem(
        GENERATORS, "qa", dataclasses.replace(GENERATORS["qa"], clean=clean_items)
    )
    _generate(monkeypatch, _reply, pairs_per_chunk=2)
    assert _kept() == []


@pytest.mark.needs_db
def test_a_failed_call_is_kept_with_its_error(
    clean: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    def failing(system: str, user: str, **_: Any) -> tuple[str, dict[str, Any]]:
        raise LLMError("the provider said no")

    report = _generate(monkeypatch, failing, pairs_per_chunk=2)

    assert report.kinds["qa"].failed_units == 1
    (call,) = _kept()
    assert call["error"] == "the provider said no"
    assert call["reply"] == "" and call["dropped"] == []
    assert call["system"] and recorded.PASSAGE_MARK in call["user"]
    assert call["cost_usd"] is None


@pytest.mark.needs_db
def test_an_unparsable_reply_is_kept_with_the_reply(
    clean: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    def prose(system: str, user: str, **_: Any) -> tuple[str, dict[str, Any]]:
        return "no JSON here", {}

    _generate(monkeypatch, prose, pairs_per_chunk=2)

    (call,) = _kept()
    assert call["error"] and call["reply"] == "no JSON here"


@pytest.mark.needs_db
def test_a_build_stores_each_system_prompt_once(clean: None) -> None:
    log = writer_log.WriterLog(JOB)
    drop = [Dropped("r", "q", "a")]
    for system in ("S1", "S1", "S2"):
        log.keep(
            {"system": system, "user": "u"},
            {"qa": drop, "mcq": []},
            document_title="d",
            file_name="f.md",
            passage="p",
        )
    with session_scope() as session:
        rows = session.scalars(
            select(WriterCall)
            .where(WriterCall.job_id == JOB)
            .order_by(WriterCall.created_at)
        ).all()
        assert [r.system for r in rows] == ["S1", "", "S2"]
        assert all(set(r.dropped) == {"qa", "mcq"} for r in rows)
    assert {i["system"] for i in _kept()} == {"S1", "S2"}


@pytest.mark.needs_db
def test_a_call_is_kept_once_and_its_prompt_still_stored(clean: None) -> None:
    """One row per (job, call): a repeat is skipped, and the prompt it would
    have carried goes on the next row."""
    log = writer_log.WriterLog(JOB)
    drop = {"qa": [Dropped("r", "q", "a")]}
    with session_scope() as session:
        session.add(
            WriterCall(
                id="pre-existing",
                job_id=JOB,
                call="c-dup",
                model="m",
                passage="p",
                system="",
                system_digest="d",
                user="u",
                reply="first",
                dropped={},
                created_at=datetime.now(UTC),
            )
        )
    for call, reply in (("c-dup", "second"), ("c-next", "third")):
        log.keep(
            {"call": call, "system": "S1", "user": "u", "reply": reply},
            drop,
            document_title="d",
            file_name="f.md",
            passage="p",
        )
    with session_scope() as session:
        rows = {
            r.call: (r.reply, r.system)
            for r in session.scalars(
                select(WriterCall).where(WriterCall.job_id == JOB)
            ).all()
        }
    assert rows == {"c-dup": ("first", ""), "c-next": ("third", "S1")}

    with pytest.raises(IntegrityError), session_scope() as session:
        session.add(
            WriterCall(
                id="direct-duplicate",
                job_id=JOB,
                call="c-dup",
                model="m",
                passage="p",
                system_digest="d",
                user="u",
                reply="r",
                dropped={},
                created_at=datetime.now(UTC),
            )
        )


def _masking(system: str, user: str, **_: Any) -> tuple[str, dict[str, Any]]:
    data = {
        "named_entity": [
            {
                "question": "The city of ______ opened its new town hall on Monday.",
                "answer": "Hamburg",
            },
            {
                "question": "The mayor ______ cut the ribbon in front of the crowd.",
                "answer": "Tschentscher",
            },
        ],
        "numeric": [
            {
                "question": "It cost the city more than ______ million euros.",
                "answer": "ten",
            }
        ],
        "temporal": [],
    }
    return json.dumps(data), {}


ENGLISH = (
    "The city of Hamburg opened its new town hall on Monday. The mayor "
    "Tschentscher cut the ribbon in front of the crowd. It cost the city more "
    "than ten million euros."
)


@pytest.mark.needs_db
def test_a_masking_call_is_one_row_listed_under_each_kind_that_dropped(
    clean: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    kinds = ("named_entity_masking", "numeric_masking", "temporal_masking")
    report = _generate(
        monkeypatch,
        _masking,
        generators=kinds,
        documents=_documents(ENGLISH),
        pairs_per_chunk=1,
    )

    names, numbers = _kept()
    assert (names["generator"], numbers["generator"]) == kinds[:2]
    assert names["call"] == numbers["call"]
    with session_scope() as session:
        (row,) = session.scalars(select(WriterCall).where(WriterCall.job_id == JOB))
        assert set(row.dropped) == set(kinds[:2])
    assert [d["reason"] for d in names["dropped"]] == [pipeline.OVER_UNIT_LIMIT]
    assert "______" in names["dropped"][0]["question"]
    assert numbers["dropped"][0]["answer"] == "ten"
    for kind, call in zip(kinds, (names, numbers), strict=False):
        assert Counter(d["reason"] for d in call["dropped"]) == Counter(
            report.kinds[kind].dropped
        )


@pytest.mark.needs_db
def test_without_a_job_nothing_is_kept(
    clean: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    def failing(system: str, user: str, **_: Any) -> tuple[str, dict[str, Any]]:
        raise LLMError("down")

    monkeypatch.setattr(pipeline, "ChromaClient", ChromaStub)
    monkeypatch.setattr(
        pipeline, "load_documents", lambda *_: _documents("The council met.")
    )
    monkeypatch.setattr(pipeline, "chat", failing)

    def count() -> int:
        with session_scope() as session:
            return session.execute(select(func.count(WriterCall.id))).scalar_one()

    before = count()
    report = pipeline.generate_for_space(
        SpaceConfig(key=KEY, url="http://space:8080", endpoint="ep"),
        generators=("qa",),
        settings=_settings(),
    )
    assert report.failures == 1
    assert count() == before


# --- the API ------------------------------------------------------------------


def _row(
    dropped: dict[str, list[dict[str, str]]], *, system: str = "S", **extra: Any
) -> WriterCall:
    return WriterCall(
        id=uuid.uuid4().hex,
        job_id=JOB,
        call=uuid.uuid4().hex,
        system=system,
        system_digest=writer_log.digest("S"),
        dropped=dropped,
        **extra,
    )


@pytest.mark.needs_db
def test_the_writing_route_lists_pages_and_filters(
    client: TestClient, clean: None
) -> None:
    auth = console_auth(client, KEY)
    with session_scope() as session:
        session.add(Job(id=JOB, target=KEY, state=JobState.SUCCEEDED.value))
    with session_scope() as session:
        session.add(_row({"qa": []}, reply="late"))
    with session_scope() as session:
        session.add_all(
            [
                _row(
                    {
                        "mcq": [{"question": "q", "answer": "a", "reason": "r"}],
                        "unknown_kind": [],
                    },
                    system="",
                ),
            ]
        )

    url = f"/console/report/runs/{JOB}/writing"
    body = client.get(url, headers=auth).json()
    assert body["total"] == 3
    assert [i["generator"] for i in body["items"]] == ["mcq", "qa", "unknown_kind"]
    assert all(i["system"] == "S" for i in body["items"])
    assert body["items"][0]["dropped"] == [
        {"question": "q", "answer": "a", "reason": "r"}
    ]
    assert body["items"][2]["dropped"] == []
    assert body["items"][0]["call"] == body["items"][2]["call"]

    only = client.get(url, params={"generator": "qa"}, headers=auth).json()
    assert only["total"] == 1 and only["items"][0]["reply"] == "late"
    paged = client.get(url, params={"limit": 1, "offset": 1}, headers=auth).json()
    assert paged["total"] == 3
    assert [i["generator"] for i in paged["items"]] == ["qa"]

    assert (
        client.get("/console/report/runs/nope/writing", headers=auth).status_code == 404
    )


@pytest.mark.needs_db
def test_an_old_job_lists_nothing_and_deleting_a_job_takes_its_calls(
    client: TestClient, clean: None
) -> None:
    auth = console_auth(client, KEY)
    with session_scope() as session:
        session.add(Job(id=JOB, target=KEY, state=JobState.SUCCEEDED.value))
    url = f"/console/report/runs/{JOB}/writing"
    assert client.get(url, headers=auth).json() == {"items": [], "total": 0}

    with session_scope() as session:
        session.add(_row({"qa": []}))
    with session_scope() as session:
        job = session.get(Job, JOB)
        assert job is not None
        discard_run(session, job)
    with session_scope() as session:
        left = session.scalars(select(WriterCall).where(WriterCall.job_id == JOB))
        assert left.all() == []
