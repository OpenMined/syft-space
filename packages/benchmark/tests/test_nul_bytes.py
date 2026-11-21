"""U+0000 in provider or web text is dropped on the way to Postgres.

On 2026-11-19 a web-search citation titled with a mis-decoded PDF title
("Decl DÃ\\x00...") failed the ``jsonb`` write of the results it belonged to,
and two models' with-context passes stopped. Postgres stores neither the byte
in ``text`` nor its ``\\u0000`` escape in ``jsonb``; the connection drops it
from every string and JSON document it sends, whoever wrote them.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy import select, text, update
from sqlalchemy.dialects.postgresql import insert

from syft_benchmark.db import QaPair, Result, Run, WriterCall, session_scope
from syft_benchmark.db.nul_guard import dumps_without_nul, strip_nul

from support import add_rows

SPACE = "pytest-nul-bytes"
JOB = "pytest-nul-bytes-job"

TITLE = "Decl DÃ\x00 Laicidad 2019"
CITATION = {
    "url": "https://example.org/Declaracion-\x00Laicidad-2019.pdf",
    "title": TITLE,
}


def test_strip_nul_reaches_every_string_in_a_structure() -> None:
    value: Any = {
        "a\x00": ["x\x00y", ("z\x00",), {"deep": "q\x00"}],
        "n": 1,
        "none": None,
        "flag": True,
    }
    assert strip_nul(value) == {
        "a": ["xy", ["z"], {"deep": "q"}],
        "n": 1,
        "none": None,
        "flag": True,
    }


def test_dumps_never_emits_the_nul_escape_but_keeps_a_literal_backslash() -> None:
    assert "\\u0000" not in dumps_without_nul({"title": TITLE})
    # Six characters of text, not a NUL: escaped to \\u0000, which jsonb takes.
    literal = "see \\u0000 in the spec"
    assert json.loads(dumps_without_nul({"t": literal})) == {"t": literal}


def _pair(pair_id: str) -> QaPair:
    return QaPair(
        id=pair_id,
        space=SPACE,
        generator="qa",
        question="Which year is the declaration\x00 from?",
        answer="2019\x00",
        context="",
        status="active",
        model="m",
        question_hash=pair_id,
        meta={"source_title": TITLE},
    )


def _run(run_id: str) -> Run:
    return Run(
        id=run_id,
        space=SPACE,
        job_id=JOB,
        context_mode="web_search",
        block="direct",
        model="m",
        params={"note": "x\x00"},
    )


@pytest.mark.needs_db
@pytest.mark.usefixtures("clean")
def test_a_result_with_a_nul_citation_title_is_stored_and_read_back() -> None:
    pair_id, run_id = f"{SPACE}-pair", f"{SPACE}-run"
    result_id = f"{SPACE}-result"
    add_rows(
        _pair(pair_id),
        _run(run_id),
        Result(
            id=result_id,
            run_id=run_id,
            qa_id=pair_id,
            space=SPACE,
            answer="It is from 2019\x00.",
            verdict="correct",
            reasoning="Matches\x00 the gold answer.",
            judge_model="t",
            extra={"citations": [CITATION], "search_trail": [["q\x00", 1]]},
            audit={"judge_raw": '{"verdict": "correct\x00"}'},
        ),
    )

    with session_scope() as session:
        row = session.get(Result, result_id)
        assert row is not None
        assert row.answer == "It is from 2019."
        assert row.reasoning == "Matches the gold answer."
        assert row.extra["citations"] == [
            {
                "url": "https://example.org/Declaracion-Laicidad-2019.pdf",
                "title": "Decl DÃ Laicidad 2019",
            }
        ]
        assert row.extra["search_trail"] == [["q", 1]]
        assert row.audit == {"judge_raw": '{"verdict": "correct"}'}
        pair = session.get(QaPair, pair_id)
        assert pair is not None
        assert (pair.question, pair.answer) == (
            "Which year is the declaration from?",
            "2019",
        )
        assert pair.meta == {"source_title": "Decl DÃ Laicidad 2019"}


@pytest.mark.needs_db
@pytest.mark.usefixtures("clean")
def test_core_insert_update_and_raw_sql_drop_nul_too() -> None:
    pair_id, run_id = f"{SPACE}-pair", f"{SPACE}-run"
    add_rows(_pair(pair_id), _run(run_id))
    call_id = uuid.uuid4().hex

    with session_scope() as session:
        # A Core insert with a JSONB column, as the writer log does.
        session.execute(
            insert(WriterCall)
            .values(
                id=call_id,
                job_id=JOB,
                call="c1",
                model="m",
                passage="p\x00",
                system_digest="",
                reply="r\x00",
                error="boom\x00",
                dropped={"qa": [{"question": "q\x00", "why": "w\x00"}]},
                created_at=datetime.now(UTC),
            )
            .on_conflict_do_nothing(index_elements=["job_id", "call"])
        )
        # An ORM-enabled update, as the filter stage does.
        session.execute(
            update(QaPair)
            .where(QaPair.id == pair_id)
            .values(status_note="web\x00 check", meta={"why": "w\x00"})
        )
        # A raw statement with bound parameters.
        session.execute(
            text("update runs set note = :note where id = :id"),
            {"note": "raw\x00 note", "id": run_id},
        )

    with session_scope() as session:
        call = session.execute(
            select(WriterCall).where(WriterCall.id == call_id)
        ).scalar_one()
        assert (call.passage, call.reply, call.error) == ("p", "r", "boom")
        assert call.dropped == {"qa": [{"question": "q", "why": "w"}]}
        pair = session.get(QaPair, pair_id)
        assert pair is not None
        assert (pair.status_note, pair.meta) == ("web check", {"why": "w"})
        run = session.get(Run, run_id)
        assert run is not None
        assert run.note == "raw note"
        assert run.params == {"note": "x"}
        session.delete(call)
