"""The privacy invariants as executable checks.

Each of them is a condition whose violation robs the whole pipeline of meaning.
Keeping them in the README is not enough: a README does not fail on commit.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from syft_benchmark.config import (
    ExternalCallBlocked,
    Settings,
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
        SRC / "cli" / "diagnostics.py",
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

    If a chat request appears outside llm/client.py, the host check
    becomes optional — and an optional check is not a check.
    """
    sources = [path for path in SRC.rglob("*.py") if path != SRC / "llm" / "client.py"]
    offenders = [
        path
        for path in sources
        if "chat/completions" in path.read_text(encoding="utf-8")
    ]
    assert not offenders, "a model called directly, past the client: " + ", ".join(
        str(p.relative_to(SRC)) for p in offenders
    )


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
    """Invariant 4: there are no SyftHub credentials here; results stay in the Space."""
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
