"""The privacy invariants as executable checks.

Each of them is a condition whose violation robs the whole pipeline of meaning.
Keeping them in the README is not enough: a README does not fail on commit.
"""

from __future__ import annotations

import ast
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest

from syft_benchmark.config import (
    ContextMode,
    EvalBlock,
    ExpectedBehavior,
    ExternalCallBlocked,
    Settings,
    SpaceConfig,
)
from syft_benchmark.publish import payload_for, publish
from syft_benchmark.report import Metrics
from syft_benchmark.report.card import (
    ANSWERING,
    CARD_VERSION,
    Card,
    DatasetInfo,
    Instrument,
    ModelRow,
    SkillRow,
    Trust,
)

SRC = Path(__file__).resolve().parents[1] / "src" / "syft_benchmark"


def _imports_of(path: Path) -> set[str]:
    """The modules a file imports."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
        elif isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
    return found


def test_the_target_check_returns_counts_and_nothing_else() -> None:
    """The target check reads the corpus — and so is obliged to return none of it.

    It is exposed in the API and is called from a foreign UI. One text field in
    its response — a document title, a sample chunk, "here is what was found" —
    and a diagnostic route becomes a hole outwards, through which goes exactly
    what the whole pipeline was built for.

    By a list of fields rather than by reading the code: a field gets added in
    passing, and here it will break the build.
    """
    from syft_benchmark.control.check import Check

    numbers = {"chunks", "usable", "documents"}
    identifiers = {"target", "transport", "collection", "available", "response_type"}
    flags = {"corpus", "endpoint"}
    # Problems and blocked arms are our own wordings about configuration, not
    # corpus material.
    ours = {"problems", "blocked_arms"}
    assert set(Check.__dataclass_fields__) == numbers | identifiers | flags | ours


def test_only_sources_reads_the_corpus() -> None:
    """Invariant 1: source text is seen only by the sources package.

    Checked by the import graph rather than by agreement: understanding leaves
    along with the person, while an import stays in the file.
    """
    corpus_readers = {
        "syft_benchmark.sources",
        "syft_benchmark.sources.chroma",
    }
    allowed = {
        # The generation pipeline needs the chunk: the question grows out of it
        # and the gold answer is checked against it.
        SRC / "generation" / "pipeline.py",
        SRC / "generation" / "generators.py",
        # The CLI holds the diagnostic command chunks.
        SRC / "cli.py",
        # The target check counts chunks but returns none of them —
        # see test_the_target_check_returns_counts_and_nothing_else.
        SRC / "control" / "check.py",
        SRC / "sources" / "__init__.py",
        SRC / "sources" / "chroma.py",
    }

    offenders = [
        path
        for path in SRC.rglob("*.py")
        if path not in allowed and _imports_of(path) & corpus_readers
    ]
    assert not offenders, "these modules read the corpus but must not: " + ", ".join(
        str(p.relative_to(SRC)) for p in offenders
    )


def test_only_the_llm_client_reaches_a_model() -> None:
    """Invariant 2: a model is called through a client that checks the perimeter.

    If an httpx.post to Ollama appears outside llm/ollama.py, the host check
    becomes optional — and an optional check is not a check.
    """
    sources = [path for path in SRC.rglob("*.py") if path != SRC / "llm" / "ollama.py"]
    offenders = [
        path
        for path in sources
        if "chat/completions" in path.read_text(encoding="utf-8")
    ]
    assert not offenders, "a model called directly, past the client: " + ", ".join(
        str(p.relative_to(SRC)) for p in offenders
    )


def _leaves(value: object, path: str = "") -> list[tuple[str, object]]:
    """All the leaves of a nested structure, each with its path."""
    if isinstance(value, dict):
        found: list[tuple[str, object]] = []
        for key, item in value.items():
            found.extend(_leaves(item, f"{path}.{key}" if path else str(key)))
        return found
    if isinstance(value, list):
        found = []
        for i, item in enumerate(value):
            found.extend(_leaves(item, f"{path}[{i}]"))
        return found
    return [(path, value)]


def _card() -> Card:
    """A card with everything there can be: nothing fuller ever gets published."""
    answerable = Metrics(
        space="docs",
        context_mode=ContextMode.OPEN_BOOK,
        block=EvalBlock.DIRECT,
        model="",
        endpoint="syft-knowledge-base",
        graded=40,
        correct=28,
        abstain=5,
        hallucinate=7,
        failed=1,
        retrieval_hits=33,
        retrieval_checked=40,
        checked_at=datetime(2026, 9, 9, tzinfo=UTC),
        judge="gemma3-4b-gpu",
    )
    control = Metrics(
        space="docs",
        context_mode=ContextMode.OPEN_BOOK,
        block=EvalBlock.DIRECT,
        model="",
        endpoint="syft-knowledge-base",
        graded=10,
        correct=0,
        abstain=9,
        hallucinate=1,
        failed=0,
        retrieval_hits=0,
        retrieval_checked=0,
        checked_at=datetime(2026, 9, 9, tzinfo=UTC),
        judge="gemma3-4b-gpu",
        expected=ExpectedBehavior.ABSTAIN,
    )
    return Card(
        space="docs",
        endpoint="syft-knowledge-base",
        kind=ANSWERING,
        arm=ContextMode.OPEN_BOOK.value,
        checked_at=datetime(2026, 9, 9, tzinfo=UTC),
        score=0.7,
        fabrication=0.1,
        answerable=answerable,
        control=control,
        discrimination=0.775,
        retrieval=0.825,
        models=[
            ModelRow(
                model="anthropic/claude-sonnet-4",
                samples=40,
                accuracy=0.78,
                fabrication=0.02,
                lmi=0.2,
                context_gain=0.05,
            )
        ],
        skills=[SkillRow(generator="mcq", samples=8, accuracy=0.9)],
        trust=Trust(
            samples=50,
            judges=3,
            agreement=0.86,
            consistency=0.91,
            even_coverage=True,
            failed=1,
            pending=0,
        ),
        dataset=DatasetInfo(
            mode="rolling", window_days=7, cohort="20260914-0300", questions=50
        ),
        instrument=Instrument(
            version=CARD_VERSION,
            profile="default",
            judge="gemma3-4b-gpu",
            judges=3,
            subjects=9,
        ),
    )


def test_the_published_card_carries_only_aggregates() -> None:
    """Invariant 3: shares, counters and names leave — and nothing else.

    The composition of the payload is the boundary between internal analytics
    and the outside world, and it cannot be widened by accident: the test breaks.
    """
    payload = payload_for(_card())

    assert set(payload) == {
        "version",
        "kind",
        "arm",
        "checked_at",
        "score",
        "fabrication_rate",
        "reliable",
        "samples",
        "answerable",
        "unanswerable",
        "discrimination",
        "retrieval",
        "models",
        "skills",
        "trust",
        "dataset",
        "instrument",
    }


def test_no_published_string_can_hold_a_sentence() -> None:
    """Invariant 3, the strong form: there is never any text in the payload.

    Checking for forbidden words is not enough — such a list is never complete.
    What is checked here is the form: everything that leaves is a number, a flag
    or ONE word — the identifier of a model, a generator, a mode, a profile, a
    cohort. A chunk of the corpus, a question or an answer always has spaces in
    it, and such a leaf will fail the check whatever it is called.
    """
    payload = payload_for(_card())

    for path, value in _leaves(payload):
        if value is None or isinstance(value, bool | int | float):
            continue
        assert isinstance(value, str), f"{path}: unexpected type {type(value)}"
        assert " " not in value, f"{path}: text ended up in the payload — {value!r}"
        assert len(value) <= 120, f"{path}: too long for an identifier"


def test_a_card_without_verdicts_is_not_published() -> None:
    """An empty measurement is not published: zero questions is not zero quality."""
    empty = replace(_card(), trust=None)
    outcome = publish(
        SpaceConfig(key="docs", url="http://localhost:0", endpoint="e"), empty
    )
    assert not outcome.ok
    assert "nothing to publish" in outcome.detail


def test_the_audit_trail_never_reaches_the_publish_path() -> None:
    """The audit export and publishing are different sides of the perimeter.

    The log holds whole prompts, that is, corpus text. It exists for the owner
    and the auditor they bring in; only aggregates leave the perimeter. If the
    publishing module ever reaches for the log, that will be visible here rather
    than after a leak.
    """
    publish_sources = [
        path for path in (SRC / "publish").rglob("*.py") if path.is_file()
    ]
    for path in publish_sources:
        imports = _imports_of(path)
        assert (
            "syft_benchmark.report.audit" not in imports
        ), f"{path.name} reaches for the audit log"
        text = path.read_text(encoding="utf-8")
        for leak in ("audit", "responder_prompt", "retrieved"):
            assert leak not in text, f"{path.name} mentions {leak}"


def test_the_document_report_sees_only_aggregates() -> None:
    """The document is assembled from metrics and reaches for nothing else.

    It leaves the owner hands further than the audit export does: it is shown to
    the endpoint consumer. As long as the builder sees only ``Metrics``, there is
    no corpus text in it by design rather than by the author attentiveness. An
    import of the database or of the sources package removes that guarantee
    silently — which is why it is checked here.
    """
    forbidden = {
        "syft_benchmark.db",
        "syft_benchmark.db.models",
        "syft_benchmark.sources",
        "syft_benchmark.sources.chroma",
        "syft_benchmark.report.audit",
    }
    for name in ("document.py", "narrative.py", "charts.py"):
        path = SRC / "report" / name
        assert (
            not _imports_of(path) & forbidden
        ), f"{name} reaches for the raw records, though it builds a report from shares"


def test_benchmark_holds_no_hub_credentials() -> None:
    """Invariant 5: there are no SyftHub credentials here.

    If they were needed, the construction is broken: metrics are put out by the
    Space under its own account, not by the benchmark under someone else.
    """
    fields = set(Settings.model_fields)
    for forbidden in ("hub_url", "hub_email", "hub_password", "hub_token"):
        assert forbidden not in fields

    offenders = [
        path
        for path in SRC.rglob("*.py")
        if "/api/v1/endpoints/quality" in path.read_text(encoding="utf-8")
    ]
    assert not offenders, "the benchmark calls the hub directly: " + ", ".join(
        str(p.relative_to(SRC)) for p in offenders
    )


def test_perimeter_check_is_wired_into_every_model_call() -> None:
    """The host check sits in the client, not in the callers."""
    from syft_benchmark.llm import chat

    outside = Settings(ollama_url="https://openrouter.ai/api/v1")  # type: ignore[call-arg]
    with pytest.raises(ExternalCallBlocked):
        chat("system", "user", settings=outside)
