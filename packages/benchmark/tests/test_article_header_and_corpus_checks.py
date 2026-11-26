"""The article header in the grounding check, the archive check and arm C; a
corpus that contradicts itself; the publisher's mirrors kept out of the
searches and flagged in the report. No database, models stubbed."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from test_web_search import SEARCHED

from syft_benchmark.config import (
    ContextSource,
    PairStatus,
    Settings,
    SpaceConfig,
    StatusReason,
)
from syft_benchmark.db import QaPair
from syft_benchmark.generation import control, filter_stage
from syft_benchmark.generation.article_dates import (
    article_stamp,
    header_words,
    pair_header,
)
from syft_benchmark.generation.generators import GENERATORS
from syft_benchmark.llm import Provider, chat
from syft_benchmark.report import export_xlsx, run_questions
from syft_benchmark.runs import endpoint as run_endpoint
from syft_benchmark.runs.execute import build_context

from fakes import OPENROUTER, openrouter_settings

VIANA = {
    "title": "Brazil's platform bill stalls",
    "author": "Natalia Viana",
    "source": "local_file",
    "doc_source": "Tech Policy Press",
    "url": "https://www.techpolicy.press/brazil-platform-bill/",
    "published": "2026-11-20T09:00:00+00:00",
    "file_name": "2026-11-20-brazil.md",
}
JUDGE = Provider("judge", OPENROUTER, "k", "google/gemini-3.1-pro-preview")


def _doc(**kwargs: Any) -> SimpleNamespace:
    base: dict[str, Any] = {
        "doc_id": "d1",
        "url": "https://www.techpolicy.press/brazil-platform-bill/",
        "source": "Tech Policy Press",
        "author": "Natalia Viana",
        "published_at": datetime(2026, 11, 20, 9, tzinfo=UTC),
        "indexed_at": None,
        "ingested_at": None,
    }
    return SimpleNamespace(**{**base, **kwargs})


def _pair(generator: str, *, answer: str, meta: dict[str, Any]) -> QaPair:
    spec = GENERATORS[generator]
    return QaPair(
        id=uuid.uuid4().hex,
        space="pytest-header",
        generator=generator,
        task_type=spec.task_type,
        expected_behavior=spec.expected.value,
        doc_id="d1",
        document_title="Brazil's platform bill stalls",
        cohort="c1",
        question="Which statement is false?",
        answer=answer,
        context=(
            "The bill would oblige platforms to remove illegal content within "
            "24 hours. Lobbying by large platforms delayed the vote twice."
        ),
        meta={"grading": spec.grading, **meta},
        status=PairStatus.PENDING.value,
        model="test-model",
        question_hash=uuid.uuid4().hex,
    )


# --- The header -------------------------------------------------------------


def test_a_found_chunk_is_headed_by_its_article() -> None:
    assert run_endpoint.fragment_header(VIANA) == (
        "Title: Brazil's platform bill stalls | Author: Natalia Viana | "
        "Outlet: Tech Policy Press | Published: 2026-11-20"
    )
    # The Space returns its connector as ``source``: the address names the site.
    bare = {k: v for k, v in VIANA.items() if k not in ("doc_source", "author")}
    assert run_endpoint.fragment_header(bare) == (
        "Title: Brazil's platform bill stalls | Outlet: techpolicy.press | "
        "Published: 2026-11-20"
    )
    assert run_endpoint.fragment_header({"file_name": "x.md"}) == ""


def test_the_question_keeps_its_outlet_and_author() -> None:
    stamp = article_stamp(_doc())
    assert stamp["article_outlet"] == "Tech Policy Press"
    assert stamp["article_author"] == "Natalia Viana"
    assert "article_author" not in article_stamp(_doc(author=""))
    assert pair_header("T", stamp) == (
        "Title: T | Author: Natalia Viana | Outlet: Tech Policy Press | "
        "Published: 2026-11-20"
    )
    assert header_words("T", stamp).endswith("(20 November 2026)")
    # A date that is not the publication date is not offered as one.
    added = {**stamp, "article_dated_by": "added"}
    assert "Published" not in pair_header("T", added)


def test_arm_c_shows_each_fragment_under_its_header() -> None:
    found = [
        {"header": run_endpoint.fragment_header(VIANA), "content": "Text one."},
        {"file_name": "b.md", "content": "Text two."},
    ]
    context = build_context(found, "", source=ContextSource.ENDPOINT_FRAGMENTS, limit=5)
    assert context.startswith(
        "[1] Title: Brazil's platform bill stalls | Author: Natalia Viana"
    )
    assert "[2] b.md\nText two." in context
    oracle = build_context(
        [],
        "",
        source=ContextSource.ORACLE_CHUNK,
        limit=5,
        oracle="Text one.",
        oracle_header="Title: T | Outlet: Tempo",
    )
    assert oracle == "[1] Title: T | Outlet: Tempo\nText one."


def test_the_archive_check_reads_the_header_with_the_chunk(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        run_endpoint,
        "ask_endpoint",
        lambda *_a, **_k: {
            "answer": "x",
            "failed": False,
            "documents": [
                {"content": "Lobbying delayed the vote.", "metadata": VIANA},
                {"content": "No header here.", "metadata": {}},
            ],
        },
    )
    space = SpaceConfig(key="s", url="http://space:8080", endpoint="ep")
    found = run_endpoint.endpoint_retriever(space, Settings())("q")
    assert found[0].startswith("Title: Brazil's platform bill stalls | Author:")
    assert found[0].endswith("\nLobbying delayed the vote.")
    assert found[1] == "No header here."


def test_a_claim_attributed_to_the_author_is_grounded_by_the_header() -> None:
    conf = openrouter_settings()
    claims = [
        "Tech Policy Press's Natalia Viana argued that lobbying by large "
        "platforms delayed the vote twice.",
        "In a November 2026 Tech Policy Press piece, Natalia Viana wrote that "
        "the bill would oblige platforms to remove illegal content within 24 "
        "hours.",
    ]
    stamped = article_stamp(_doc())
    spec = GENERATORS["two_truths_one_lie"]
    headed = _pair("two_truths_one_lie", answer="C", meta={"claims": claims, **stamped})
    bare = _pair("two_truths_one_lie", answer="C", meta={"claims": claims})

    status, _, _, _ = filter_stage._screen_pair(headed, spec, None, conf, JUDGE)
    assert status is PairStatus.ACTIVE
    status, reason, _, _ = filter_stage._screen_pair(bare, spec, None, conf, JUDGE)
    assert (status, reason) == (PairStatus.REJECTED, StatusReason.GROUNDING)


# --- A corpus that contradicts itself --------------------------------------


def _judge_says(monkeypatch: pytest.MonkeyPatch, reply: str) -> list[str]:
    prompts: list[str] = []

    def fake(system: str, user: str, **_: Any) -> tuple[str, dict[str, Any]]:
        prompts.append(f"{system}\n{user}")
        return reply, {}

    monkeypatch.setattr(control, "chat", fake)
    return prompts


TEMPO = [
    "Pemerintah menyiapkan Rp 833,4 miliar untuk diskon transportasi.",
    "Anggaran diskon transportasi mencapai Rp 883,4 miliar.",
]


def test_a_fragment_contradicting_the_gold_rejects_the_question(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prompts = _judge_says(
        monkeypatch,
        '{"answered": true, "where": "Rp 833,4 miliar", "contradicted": true, '
        '"conflict": "Rp 883,4 miliar", "reasoning": "two figures"}',
    )
    row = _pair("qa", answer="Rp 833,4 miliar", meta={"claims": []})
    row.context = TEMPO[0]
    status, reason, note, meta = filter_stage._screen_pair(
        row, GENERATORS["qa"], lambda _q: TEMPO, openrouter_settings(), JUDGE
    )

    assert (status, reason) == (
        PairStatus.REJECTED,
        StatusReason.CORPUS_CONTRADICTION,
    )
    assert note == "contradiction in corpus: Rp 883,4 miliar"
    assert meta["gate_checked"] is True
    # One call: the contradiction is asked with the archive check.
    assert len(prompts) == 1 and "Does another contradict it?" in prompts[0]


def test_a_found_answer_nothing_contradicts_stays(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _judge_says(
        monkeypatch,
        '{"answered": true, "where": "Rp 833,4 miliar", "contradicted": false}',
    )
    row = _pair("qa", answer="Rp 833,4 miliar", meta={"claims": []})
    row.context = TEMPO[0]
    status, reason, _, _ = filter_stage._screen_pair(
        row, GENERATORS["qa"], lambda _q: TEMPO[:1], openrouter_settings(), JUDGE
    )
    assert (status, reason) == (PairStatus.ACTIVE, None)


def test_a_false_premise_the_archive_states_as_true_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prompts = _judge_says(
        monkeypatch,
        '{"answered": true, "where": "US$ 3 miliar", "contradicted": true, '
        '"conflict": "US$ 5 miliar"}',
    )
    row = _pair(
        "false_premise",
        answer="US$ 3 miliar",
        meta={"premise": "PSEL needs US$ 5 billion", "claims": ["US$ 3 miliar"]},
    )
    status, reason, note, _ = filter_stage._screen_pair(
        row,
        GENERATORS["false_premise"],
        lambda _q: ["US$ 3 miliar", "US$ 5 miliar"],
        openrouter_settings(),
        JUDGE,
    )
    assert (status, reason) == (
        PairStatus.REJECTED,
        StatusReason.CORPUS_CONTRADICTION,
    )
    assert note.startswith("contradiction in corpus")
    assert "Does another state the premise as true?" in prompts[0]


# --- The publisher's mirrors ------------------------------------------------


MIRRORS = ["linkedin.com/company/tech-policy-press", "nationalcybersecurity.com"]


def test_the_mirrors_are_left_out_of_the_searches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bodies: list[dict[str, Any]] = []

    def post(url: str, **kwargs: Any) -> httpx.Response:
        bodies.append(kwargs["json"])
        return httpx.Response(
            200,
            json={"choices": [{"message": dict(SEARCHED), "finish_reason": "stop"}]},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx, "post", post)
    conf = Settings(
        ollama_url=OPENROUTER,
        llm_api_key="sk-or-test",
        allow_external_models=True,
        external_hosts=["openrouter.ai"],
        web_search_excluded_domains=["techpolicy.press"],
        web_check_mirror_domains=MIRRORS,
    )
    assert conf.search_exclusions() == sorted(["techpolicy.press", *MIRRORS])
    for role in ("subjects", "web_check", "judges"):
        chat(
            "s",
            "u",
            model="meta-llama/llama-4",
            settings=conf,
            web_search=True,
            role=role,
        )
    sent = [b["tools"][0]["parameters"].get("excluded_domains") for b in bodies]
    assert sent == [conf.search_exclusions(), conf.search_exclusions(), None]
    assert conf.measurement_params()["web_check_mirror_domains"] == sorted(MIRRORS)
    assert "web_check_mirror_domains" not in Settings().measurement_params()


def test_the_report_flags_citations_on_a_mirror() -> None:
    citations = [
        {"url": "https://www.linkedin.com/company/tech-policy-press/posts/1"},
        {"url": "https://www.linkedin.com/in/someone"},
        {"url": "https://nationalcybersecurity.com/copy"},
    ]
    assert export_xlsx._cites_mirror(citations, MIRRORS) is True
    assert export_xlsx._cites_mirror(citations[1:2], MIRRORS) is False
    assert export_xlsx._cites_mirror(citations, []) is None
    job = SimpleNamespace(
        params={"settings_snapshot": {"web_check_mirror_domains": MIRRORS[:1]}}
    )
    target = SimpleNamespace(instrument={"web_check_mirror_domains": MIRRORS[1:]})
    assert export_xlsx._mirrors(job, target) == sorted(MIRRORS)  # type: ignore[arg-type]
    assert run_questions._job_mirrors(job) == MIRRORS[:1]  # type: ignore[arg-type]
