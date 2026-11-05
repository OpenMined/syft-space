"""Document-scoped launches, the 409 on a busy queue, and the settings
fingerprint a job keeps.

A launch with ``documents`` builds, screens, revives and asks only those
documents; the job keeps the list, the paths the index lacked, the effective
settings and their methodology hash.
"""

from __future__ import annotations

import dataclasses
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import select
from test_run_view import Seed

from syft_benchmark.config import (
    DOCUMENT_FIELDS,
    SECRET_FIELDS,
    DatasetMode,
    JobState,
    PairStatus,
    Settings,
    SpaceConfig,
    StatusReason,
    get_settings,
    stored_fields,
)
from syft_benchmark.control import jobs
from syft_benchmark.control.schemas import (
    MAX_RUN_DOCUMENTS,
    DocumentSettings,
    Probe,
    RunRequest,
)
from syft_benchmark.db import Job, QaPair, session_scope
from syft_benchmark.generation import pipeline
from syft_benchmark.generation.article_dates import DATE_KEY
from syft_benchmark.generation.filter_stage import _pending_rows
from syft_benchmark.generation.generators import GENERATORS
from syft_benchmark.generation.pair import Dropped, Pair
from syft_benchmark.generation.rotation import rotate
from syft_benchmark.report import job_params
from syft_benchmark.runs import evaluation_gate
from syft_benchmark.runs.execute import _active_pairs
from syft_benchmark.scheduler import Measured
from syft_benchmark.sources import ChromaClient, Chunk, Document

from fakes import ChromaStub, JudgeRecorder, openrouter_settings
from support import AUTH, WEB_CHECK_MODEL, add_rows, console_auth, register_target

KEY = "pytest-document-scope"
JOB = "pytest-document-scope-job"
OTHER_JOB = "pytest-document-scope-job-2"
T0 = datetime(2026, 10, 1, tzinfo=UTC)
PATH_A = "/root/documents/bloomberg/2026-11-04/a.md"
PATH_B = "/root/documents/bloomberg/2026-11-04/b.md"


def _pair(
    pair_id: str,
    doc_id: str,
    *,
    status: str = PairStatus.ACTIVE.value,
    reason: str | None = None,
    cohort: str = "",
    web: bool = True,
) -> QaPair:
    return QaPair(
        id=pair_id,
        space=KEY,
        generator="qa",
        task_type="factual",
        doc_id=doc_id,
        question=f"Question {pair_id}?",
        answer=f"Answer {pair_id}",
        context=f"Context {pair_id}.",
        status=status,
        status_reason=reason,
        cohort=cohort,
        model="gen/model",
        question_hash=pair_id,
        meta=(
            {"web_check": {"model": WEB_CHECK_MODEL, "verdict": "hallucinate"}}
            if web
            else {}
        ),
        created_at=T0,
    )


def _status(pair_id: str) -> str:
    with session_scope() as session:
        row = session.get(QaPair, pair_id)
        assert row is not None
        return row.status


# --- the request -------------------------------------------------------------


@pytest.mark.parametrize(
    "documents", [[], [""], [f"/d/{n}.md" for n in range(MAX_RUN_DOCUMENTS + 1)]]
)
def test_a_documents_list_is_non_empty_and_bounded(documents: list[str]) -> None:
    with pytest.raises(ValidationError):
        RunRequest(documents=documents)


@pytest.mark.parametrize(
    "body",
    [
        {"document_settings": {}},
        {"documents": ["/a.md"], "document_settings": {"passages_per_document": 0}},
        {"documents": ["/a.md"], "document_settings": {"passages_per_document": 21}},
        {"documents": ["/a.md"], "document_settings": {"control_max_share": 1.0}},
        {
            "documents": ["/a.md"],
            "document_settings": {"top_up_passages_per_document": 11},
        },
        {"documents": ["/a.md"], "document_settings": {"unknown": 1}},
    ],
)
def test_document_settings_are_bounded_and_need_documents(
    body: dict[str, Any],
) -> None:
    with pytest.raises(ValidationError):
        RunRequest.model_validate(body)


def test_document_settings_are_not_endpoint_or_installation_settings() -> None:
    assert not DOCUMENT_FIELDS & set(Probe.model_fields)
    assert not DOCUMENT_FIELDS & stored_fields()
    assert set(DocumentSettings.model_fields) == DOCUMENT_FIELDS


@pytest.mark.needs_db
def test_a_scoped_launch_keeps_its_documents_in_the_job(
    client: TestClient, clean: Any
) -> None:
    register_target(client, KEY)
    made = client.post(
        f"/targets/{KEY}/runs", json={"documents": [PATH_A, PATH_B]}, headers=AUTH
    )
    assert made.status_code == 202, made.text
    with session_scope() as session:
        job = session.get(Job, made.json()["id"])
        assert job is not None
        assert job.params[job_params.DOCUMENTS] == [PATH_A, PATH_B]


@pytest.mark.needs_db
def test_a_scoped_launch_on_a_busy_target_is_a_409_naming_the_job(
    client: TestClient, clean: Any
) -> None:
    register_target(client, KEY)
    first = client.post(f"/targets/{KEY}/runs", json={}, headers=AUTH)
    assert first.status_code == 202

    clash = client.post(
        f"/targets/{KEY}/runs", json={"documents": [PATH_A]}, headers=AUTH
    )

    assert clash.status_code == 409
    body = clash.json()
    assert body["active_job_id"] == first.json()["id"]
    assert body["detail"]
    with session_scope() as session:
        assert len(session.scalars(select(Job).where(Job.target == KEY)).all()) == 1
    # Without documents the active job is still the answer.
    again = client.post(f"/targets/{KEY}/runs", json={}, headers=AUTH)
    assert again.status_code == 202
    assert again.json()["id"] == first.json()["id"]


@pytest.mark.needs_db
def test_the_console_launch_answers_the_same_409(
    client: TestClient, clean: Any
) -> None:
    auth = console_auth(client, KEY)
    first = client.post("/console/runs", json={}, headers=auth)
    assert first.status_code == 202, first.text

    clash = client.post("/console/runs", json={"documents": [PATH_A]}, headers=auth)

    assert clash.status_code == 409
    assert clash.json()["active_job_id"] == first.json()["id"]


# --- resolving the paths -----------------------------------------------------


class _Index(ChromaClient):
    """A Chroma client over fixed chunk metadata, answering ``where $in``."""

    def __init__(self, metas: list[tuple[str, dict[str, Any]]], page: int) -> None:
        super().__init__(
            SpaceConfig(key=KEY, url="http://space", endpoint="ep"),
            openrouter_settings(),
        )
        self.metas = metas
        self.page = page
        self.bodies: list[dict[str, Any]] = []

    def request(
        self, method: str, path: str, body: dict[str, Any] | None = None
    ) -> Any:
        assert body is not None
        self.bodies.append(body)
        wanted = set(body["where"]["absolute_path"]["$in"])
        hits = [(i, m) for i, m in self.metas if m.get("absolute_path") in wanted]
        window = hits[body["offset"] : body["offset"] + self.page]
        return {"ids": [i for i, _ in window], "metadatas": [m for _, m in window]}


def test_paths_resolve_to_document_ids_by_absolute_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("syft_benchmark.sources.chroma._PAGE", 2)
    index = _Index(
        [
            ("a_0", {"absolute_path": PATH_A, "doc_id": "doc-a"}),
            ("a_1", {"absolute_path": PATH_A, "doc_id": "doc-a"}),
            ("b_0", {"absolute_path": PATH_B, "doc_id": "doc-b"}),
            ("c_0", {"absolute_path": "/other.md", "doc_id": "doc-c"}),
        ],
        page=2,
    )

    found = index.doc_ids_by_path("cid", [PATH_A, PATH_B, "/missing.md", PATH_A])

    assert found == {PATH_A: "doc-a", PATH_B: "doc-b"}
    assert [body["offset"] for body in index.bodies] == [0, 2]
    assert index.bodies[0]["include"] == ["metadatas"]


# --- the job -----------------------------------------------------------------


def _queue(params: dict[str, Any]) -> None:
    add_rows(Job(id=JOB, target=KEY, state="queued", params=params))


@pytest.mark.needs_db
def test_a_scoped_job_measures_the_found_documents_and_lists_the_missing(
    client: TestClient, clean: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    register_target(client, KEY)
    _queue(
        {
            "documents": [PATH_A, "/missing.md"],
            "generate": False,
            "document_settings": {"passages_per_document": 3, "control_max_share": 0},
        }
    )
    monkeypatch.setattr(jobs, "openrouter_spend", lambda conf: None)
    monkeypatch.setattr(
        jobs, "resolve_documents", lambda space, conf, paths: {PATH_A: "doc-a"}
    )
    seen: dict[str, Any] = {}

    def measured(space: Any, conf: Settings, **kwargs: Any) -> Measured:
        seen.update(kwargs, conf=conf)
        return Measured()

    monkeypatch.setattr(jobs, "measure", measured)

    jobs.execute(JOB)

    assert seen["doc_ids"] == frozenset({"doc-a"})
    conf = seen["conf"]
    assert (conf.passages_per_document, conf.control_max_share) == (3, 0.0)
    assert conf.top_up_passages_per_document == 0
    with session_scope() as session:
        job = session.get(Job, JOB)
        assert job is not None
        assert job.state == JobState.SUCCEEDED.value, job.error
        params = dict(job.params)
    assert params[job_params.DOCUMENTS] == [PATH_A, "/missing.md"]
    assert params[job_params.DOCUMENTS_MISSING] == ["/missing.md"]
    assert params[job_params.WINDOW_DAYS] == 0
    snapshot = params[job_params.SETTINGS_SNAPSHOT]
    assert params[job_params.SETTINGS_HASH] == job_params.settings_hash(snapshot)
    assert snapshot["passages_per_document"] == 3
    assert snapshot["control_max_share"] == 0.0
    assert not SECRET_FIELDS & set(snapshot)
    assert "database_url" not in snapshot


@pytest.mark.needs_db
def test_a_scoped_job_with_no_document_found_fails_without_measuring(
    client: TestClient, clean: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    register_target(client, KEY)
    _queue({"documents": ["/missing.md"]})
    monkeypatch.setattr(jobs, "openrouter_spend", lambda conf: None)
    monkeypatch.setattr(jobs, "resolve_documents", lambda space, conf, paths: {})

    def measured(*_: Any, **__: Any) -> Measured:
        raise AssertionError("nothing should be measured")

    monkeypatch.setattr(jobs, "measure", measured)

    jobs.execute(JOB)

    with session_scope() as session:
        job = session.get(Job, JOB)
        assert job is not None
        assert job.state == JobState.FAILED.value
        assert job.error.startswith(jobs.DOCUMENTS_NOT_FOUND)
        assert job.params[job_params.DOCUMENTS_MISSING] == ["/missing.md"]


# --- the settings fingerprint ------------------------------------------------


def test_the_hash_ignores_scope_volume_and_spending() -> None:
    base = openrouter_settings()
    same = base.model_copy(
        update={
            "document_window_days": 3,
            "max_job_usd": 5.0,
            "chunks_per_run": 7,
            "concurrency": 2,
            "dataset_mode": DatasetMode.REBUILD,
        }
    )
    other = base.model_copy(update={"similarity_threshold": 0.9})

    hashed = job_params.fingerprint(base)[job_params.SETTINGS_HASH]

    assert job_params.fingerprint(same)[job_params.SETTINGS_HASH] == hashed
    assert job_params.fingerprint(other)[job_params.SETTINGS_HASH] != hashed


def test_the_snapshot_holds_every_setting_but_the_secrets() -> None:
    snapshot = job_params.settings_snapshot(openrouter_settings())
    assert set(snapshot) == set(Settings.model_fields) - job_params._SECRETS
    assert snapshot["subject_url"]
    assert "subject_key" not in snapshot


def test_excluded_hash_fields_are_settings_or_request_fields() -> None:
    """A misspelt name would silently keep its field in the hash."""
    known = set(Settings.model_fields) | {"documents", "limit"}
    assert job_params.HASH_EXCLUDED - known == {"schedule", "schedule_at"}


# --- building ----------------------------------------------------------------


def _document(name: str, chunks: int = 2) -> Document:
    return Document(
        doc_id=f"doc-{name}",
        title=name,
        url="",
        source="",
        file_name=f"{name}.md",
        chunks=[
            Chunk(
                chunk_id=f"doc-{name}_{n}",
                doc_id=f"doc-{name}",
                chunk_index=n,
                text=f"The council restored the {name} lighthouse, part {n}.",
                file_name=f"{name}.md",
                headings="",
            )
            for n in range(chunks)
        ],
        # Long outside any window.
        published_at=datetime(2020, 1, 1, tzinfo=UTC),
    )


def _clean(items: Any, n: int, whole: str) -> tuple[list[Pair], list[Dropped]]:
    # Digits only: the letters of a hex id read now and then as French or
    # Italian function words, and the language check drops the question.
    return [
        Pair(question=f"Q{uuid.uuid4().int}?", answer="A", distractors=[], meta={})
    ], []


@pytest.mark.needs_db
def test_a_scoped_build_reads_only_its_documents_whatever_the_window_and_mode(
    clean: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    documents = [_document("a"), _document("b"), _document("c")]
    writer = JudgeRecorder('[{"x": 1}]')
    monkeypatch.setattr(pipeline, "ChromaClient", ChromaStub)
    monkeypatch.setattr(pipeline, "load_documents", lambda *_: documents)
    monkeypatch.setattr(pipeline, "chat", writer)
    monkeypatch.setitem(
        GENERATORS, "qa", dataclasses.replace(GENERATORS["qa"], clean=_clean)
    )
    add_rows(_pair("old-b", "doc-b", cohort="2026-10-01"))
    conf = openrouter_settings(
        concurrency=1,
        entity_check=False,
        document_window_days=1,
        dataset_mode=DatasetMode.REBUILD,
        pairs_per_chunk=1,
        chunks_per_run=50,
        passages_per_document=2,
    )

    made = pipeline.generate_for_space(
        SpaceConfig(key=KEY, url="http://space", endpoint="ep"),
        generators=("qa",),
        settings=conf,
        doc_ids=frozenset({"doc-a", "doc-c"}),
    )

    with session_scope() as session:
        rows = session.scalars(select(QaPair).where(QaPair.space == KEY)).all()
        built = {row.doc_id for row in rows if row.id != "old-b"}
        cohorts = {row.cohort for row in rows if row.id != "old-b"}
    assert built == {"doc-a", "doc-c"}
    # A rebuild-mode target tops up its current cohort: no new one is minted.
    assert cohorts == {"2026-10-01"}
    # Two documents giving two passages each: every passage read once, the
    # budget their share, whatever chunks_per_run says.
    assert len(writer.sent) == 4
    stats = made.kinds["qa"]
    assert (stats.units_read, stats.budget, stats.units_available) == (4, 4, 4)
    assert stats.stopped == pipeline.BUDGET_REACHED
    assert _status("old-b") == PairStatus.ACTIVE.value


# --- screening, the set, and asking ------------------------------------------


@pytest.mark.needs_db
def test_screening_takes_only_the_scope_pending_pairs(clean: Any) -> None:
    add_rows(
        _pair("p-a", "doc-a", status=PairStatus.PENDING.value),
        _pair("p-b", "doc-b", status=PairStatus.PENDING.value),
    )
    conf = get_settings()
    scoped = _pending_rows(KEY, conf, None, None, None, frozenset({"doc-a"}))
    everything = _pending_rows(KEY, conf, None, None, None)
    assert [row.id for row in scoped] == ["p-a"]
    assert {row.id for row in everything} == {"p-a", "p-b"}


@pytest.mark.needs_db
def test_a_scoped_recompute_revives_its_own_pairs_and_retires_nothing(
    clean: Any,
) -> None:
    rotation = StatusReason.ROTATION.value
    add_rows(
        _pair("in-retired", "doc-a", status="retired", reason=rotation),
        _pair("in-owner", "doc-a", status="retired", reason=StatusReason.OWNER.value),
        _pair("in-old", "doc-a", status="retired", reason=rotation, cohort="0"),
        _pair("out-active", "doc-b"),
        _pair("out-retired", "doc-b", status="retired", reason=rotation),
    )
    conf = get_settings().model_copy(
        update={"dataset_mode": DatasetMode.ROLLING, "dataset_max_pairs": 1}
    )

    report = rotate(KEY, {}, cohort="", settings=conf, scope=frozenset({"doc-a"}))

    assert report.revived == 1
    assert report.retired == 0
    assert _status("in-retired") == PairStatus.ACTIVE.value
    assert _status("in-owner") == PairStatus.RETIRED.value
    assert _status("in-old") == PairStatus.RETIRED.value
    assert _status("out-active") == PairStatus.ACTIVE.value
    assert _status("out-retired") == PairStatus.RETIRED.value


@pytest.mark.needs_db
def test_a_scoped_evaluation_asks_only_its_documents_that_passed_the_gate(
    clean: Any,
) -> None:
    add_rows(
        _pair("a-1", "doc-a"),
        _pair("a-unchecked", "doc-a", web=False),
        _pair("b-1", "doc-b"),
        _pair("c-unchecked", "doc-c", web=False),
    )
    conf = get_settings().model_copy(update={"filter_model": WEB_CHECK_MODEL})

    asked = _active_pairs(KEY, None, conf, doc_ids=frozenset({"doc-a"}))

    assert [row.id for row in asked] == ["a-1"]
    assert {row.id for row in _active_pairs(KEY, None, conf)} == {"a-1", "b-1"}
    # Only the scope decides whether nothing passed the gate.
    assert evaluation_gate(KEY, conf, doc_ids=frozenset({"doc-c"}))
    assert evaluation_gate(KEY, conf, doc_ids=frozenset({"doc-a"})) == ""


def test_the_scope_overrides_a_frozen_question_set(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    rows = [_pair("a-1", "doc-a"), _pair("b-1", "doc-b")]
    monkeypatch.setattr(
        "syft_benchmark.runs.execute.active_pairs", lambda space, conf: rows
    )
    conf = openrouter_settings(
        filter_model=WEB_CHECK_MODEL, question_set=tmp_path / "absent.json"
    )
    asked = _active_pairs(KEY, None, conf, doc_ids=frozenset({"doc-b"}))
    assert [row.id for row in asked] == ["b-1"]


def test_a_scoped_job_records_no_article_window() -> None:
    conf = openrouter_settings(document_window_days=7)
    assert job_params.dataset_snapshot(conf) == {job_params.WINDOW_DAYS: 7}
    assert job_params.dataset_snapshot(conf, scoped=True) == {job_params.WINDOW_DAYS: 0}


# --- the article period of the report ----------------------------------------


def _scoped_run(job: str, days: dict[str, str], created: datetime) -> None:
    seed = Seed(job, space=KEY)
    for qa, day in days.items():
        seed.pair(qa, job_id=job, meta={DATE_KEY: day})
        seed.answer(qa, "vendor/model", "with", "correct")
    seed.save(
        params={
            job_params.DOCUMENTS: [PATH_A],
            job_params.WINDOW_DAYS: 0,
            job_params.SETTINGS_HASH: "h1",
            job_params.JUDGE_PANEL: ["judge/primary"],
        },
        created_at=created,
    )


def _method(client: TestClient, auth: dict[str, str], job: str) -> Any:
    got = client.get(f"/console/report/runs/{job}", headers=auth)
    assert got.status_code == 200, got.text
    return got.json()["method"]


@pytest.mark.needs_db
def test_a_scoped_run_and_their_combination_span_their_articles(
    client: TestClient, clean: Any
) -> None:
    auth = console_auth(client, KEY)
    _scoped_run(JOB, {"ds-1": "2026-10-03", "ds-2": "2026-09-28"}, T0)
    _scoped_run(OTHER_JOB, {"ds-3": "2026-10-07"}, T0 + timedelta(hours=2))

    first = _method(client, auth, JOB)
    assert (first["articles_from"], first["articles_to"]) == (
        "2026-09-28",
        "2026-10-03",
    )

    made = client.post(
        "/console/report/combined", json={"job_ids": [JOB, OTHER_JOB]}, headers=auth
    )
    assert made.status_code == 201, made.text
    both = _method(client, auth, made.json()["job_id"])
    assert (both["articles_from"], both["articles_to"]) == (
        "2026-09-28",
        "2026-10-07",
    )
