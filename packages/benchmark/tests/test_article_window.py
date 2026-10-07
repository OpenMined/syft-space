"""Which articles are in the time window: one rule for generation and the page.

An article's date is its publication date; without one, the time its file was
added to the Space. A date without a time counts as its whole day.
"""

from __future__ import annotations

from datetime import UTC, datetime
from importlib import import_module
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from syft_benchmark.config import Settings, get_settings
from syft_benchmark.control.app import create_app
from syft_benchmark.control.schemas import Probe, TargetSpec
from syft_benchmark.db.models import Target
from syft_benchmark.db.session import session_scope
from syft_benchmark.generation.rotation import fresh_ids, window_count
from syft_benchmark.sources.chroma import (
    Chunk,
    Document,
    article_date,
    load_documents,
    parse_day,
)

# The module, not the function of the same name the package re-exports.
control_check = import_module("syft_benchmark.control.check")

_NOW = datetime(2026, 10, 6, 12, 0, tzinfo=UTC)
_ONE_DAY = Settings(document_window_days=1)  # type: ignore[call-arg]


def _doc(doc_id: str = "d", **dates: Any) -> Document:
    return Document(
        doc_id=doc_id, title="", url="", source="", file_name="", chunks=[], **dates
    )


def _in_window(doc: Document) -> bool:
    kept, _ = fresh_ids({doc.doc_id: doc.dated_at}, _ONE_DAY, now=_NOW)
    return doc.doc_id in kept


# --- the rule ---------------------------------------------------------------


def test_publication_date_wins_over_the_add_time() -> None:
    doc = _doc(
        published_at=datetime(2026, 9, 1, 8, tzinfo=UTC),
        added_at=datetime(2026, 10, 6, 9, tzinfo=UTC),
    )
    assert article_date(doc) == datetime(2026, 9, 1, 8, tzinfo=UTC)
    assert not _in_window(doc)


def test_without_a_publication_date_the_add_time_counts() -> None:
    doc = _doc(
        added_at=datetime(2026, 10, 6, 9, tzinfo=UTC),
        ingested_at=datetime(2026, 4, 1, tzinfo=UTC),
    )
    assert article_date(doc) == datetime(2026, 10, 6, 9, tzinfo=UTC)
    assert _in_window(doc)


def test_the_scrape_time_is_the_last_resort() -> None:
    doc = _doc(ingested_at=datetime(2026, 10, 6, 1, tzinfo=UTC))
    assert article_date(doc) == datetime(2026, 10, 6, 1, tzinfo=UTC)
    assert article_date(_doc()) is None


# --- the whole day ----------------------------------------------------------


def test_a_date_without_a_time_counts_as_the_whole_day() -> None:
    """Window of one day at noon: yesterday's date counts, the day before not."""
    found = parse_day("2026-10-05")
    assert found == (datetime(2026, 10, 5, tzinfo=UTC), True)
    yesterday = _doc(published_at=found[0], published_whole_day=True)
    assert _in_window(yesterday)

    before = parse_day("2026-10-04")
    assert before is not None
    assert not _in_window(_doc(published_at=before[0], published_whole_day=True))


def test_a_date_with_a_time_is_a_moment() -> None:
    found = parse_day("2026-10-05T10:00:00Z")
    assert found == (datetime(2026, 10, 5, 10, tzinfo=UTC), False)
    assert not _in_window(_doc(published_at=found[0]))


def test_human_formats_are_whole_days() -> None:
    found = parse_day("Oct 5, 2026")
    assert found is not None and found[1] is True


# --- where the dates come from ----------------------------------------------


class _Client:
    """A collection of one chunk per document, with the given metadata."""

    def __init__(self, rows: list[tuple[str, str, dict[str, Any]]]) -> None:
        self.rows = rows

    def iter_chunks(self, collection_id: str) -> Any:
        from syft_benchmark.sources.chroma import _added_at

        for doc_id, text, meta in self.rows:
            yield Chunk(
                chunk_id=f"{doc_id}_0",
                doc_id=doc_id,
                chunk_index=0,
                text=text,
                file_name=f"{doc_id}.md",
                headings="",
                published=str(meta.get("published") or ""),
                added_at=_added_at(meta),
            )


def _load(rows: list[tuple[str, str, dict[str, Any]]]) -> dict[str, Document]:
    docs = load_documents(_Client(rows), "c", min_chars=0)  # type: ignore[arg-type]
    return {d.doc_id: d for d in docs}


def test_dates_are_read_from_the_header_and_the_space_metadata() -> None:
    header = (
        'title: "T"\npublished_date: "2026-10-05"\ningested_at: "2026-04-01"\n---\nBody'
    )
    docs = _load(
        [
            ("etl", header, {"added_at": "2026-10-06T09:00:00+00:00"}),
            ("feed", "Body", {"published": "2026-10-06T07:00:00+00:00"}),
            ("stamped", "Body", {"added_at": "2026-10-06T09:00:00+00:00"}),
            ("file", "Body", {"source": "local_file", "updated": "2026-09-15T10:53"}),
            ("post", "Body", {"source": "wordpress", "updated": "2026-10-06T10:00"}),
        ]
    )
    assert docs["etl"].published_whole_day is True
    assert docs["etl"].dated_at == datetime(2026, 10, 5, 23, 59, 59, 999999, tzinfo=UTC)
    assert docs["feed"].dated_at == datetime(2026, 10, 6, 7, tzinfo=UTC)
    assert docs["stamped"].dated_at == datetime(2026, 10, 6, 9, tzinfo=UTC)
    # Indexed before the Space stamped added_at: the file's modification time.
    assert docs["file"].dated_at == datetime(2026, 9, 15, 10, 53, tzinfo=UTC)
    # A post's edit date is not an add time.
    assert docs["post"].dated_at is None


def test_the_count_includes_the_undated() -> None:
    dated = {
        "new": datetime(2026, 10, 6, 9, tzinfo=UTC),
        "old": datetime(2026, 9, 1, tzinfo=UTC),
        "none": None,
    }
    counted = window_count(dated, _ONE_DAY, now=_NOW)
    assert (counted.count, counted.undated, counted.total) == (2, 1, 3)
    assert counted.window_days == 1


# --- the route --------------------------------------------------------------

TOKEN = "test-window-token"
KEY = "pytest-window-target"
AUTH = {"Authorization": f"Bearer {TOKEN}"}


def _db_ready() -> bool:
    try:
        with session_scope() as session:
            session.execute(delete(Target).where(Target.key == KEY))
        return True
    except Exception:  # noqa: BLE001 - the database may simply not be at hand
        return False


@pytest.mark.skipif(not _db_ready(), reason="the benchmark database is unavailable")
def test_the_route_counts_by_the_same_rule(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Chroma:
        def __init__(self, *args: Any) -> None:
            pass

        def collection_id(self, name: str) -> str | None:
            return "c" if name == "atlantic" else None

    now = datetime.now(UTC)
    docs = [
        _doc("fresh", added_at=now),
        _doc("stale", added_at=datetime(2026, 1, 1, tzinfo=UTC)),
        _doc("undated"),
    ]
    monkeypatch.setattr(control_check, "ChromaClient", _Chroma)
    monkeypatch.setattr(control_check, "load_documents", lambda client, cid: docs)

    client = TestClient(
        create_app(get_settings().model_copy(update={"control_token": TOKEN}))
    )
    spec = TargetSpec(
        key=KEY,
        url="http://space.invalid",
        collection="atlantic",
        probe=Probe(document_window_days=1),
    )
    try:
        assert (
            client.put(
                f"/targets/{KEY}", json=spec.model_dump(mode="json"), headers=AUTH
            ).status_code
            == 200
        )
        reply = client.get(f"/targets/{KEY}/window", headers=AUTH)
        assert reply.status_code == 200, reply.text
        assert reply.json() == {
            "count": 2,
            "undated": 1,
            "total": 3,
            "window_days": 1,
        }
        # The page counts with its unsaved window: no window keeps everything.
        wide = client.get(f"/targets/{KEY}/window?days=0", headers=AUTH).json()
        assert (wide["count"], wide["undated"], wide["window_days"]) == (3, 0, 0)
        assert client.get("/targets/nope/window", headers=AUTH).status_code == 404
    finally:
        with session_scope() as session:
            session.execute(delete(Target).where(Target.key == KEY))
