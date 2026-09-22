"""The report as a document: the sections, the charts and the boundary of what gets in.

What is tested is not the layout. What is tested is what could make the report
lie: halves of the set mixed in one table; "not measured" drawn as a measured
zero; a prose paragraph indistinguishable from a computed one; and corpus text
that ended up in the document that travels furthest of all.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from docx import Document as read_docx

from syft_benchmark.config import ContextMode, EvalBlock, ExpectedBehavior, Settings
from syft_benchmark.report import Metrics, build_docx, findings
from syft_benchmark.report import document as document_module
from syft_benchmark.report.narrative import numbers_block


def _settings(**kwargs: object) -> Settings:
    return Settings(spaces_file="config/spaces.json", **kwargs)  # type: ignore[arg-type]


def _metrics(
    mode: ContextMode,
    expected: ExpectedBehavior,
    correct: int,
    abstain: int,
    wrong: int,
    **kwargs: object,
) -> Metrics:
    return Metrics(
        space="docs",
        context_mode=mode,
        block=EvalBlock.DIRECT,
        model=str(kwargs.pop("model", "gemma3-4b-gpu")),
        endpoint="syft-knowledge-base",
        graded=correct + abstain + wrong,
        correct=correct,
        abstain=abstain,
        hallucinate=wrong,
        failed=int(kwargs.pop("failed", 0)),  # type: ignore[arg-type]
        retrieval_hits=int(kwargs.pop("hits", 0)),  # type: ignore[arg-type]
        retrieval_checked=int(kwargs.pop("checked", 0)),  # type: ignore[arg-type]
        checked_at=datetime(2026, 9, 13, tzinfo=UTC),
        judge="anthropic/claude-sonnet-4",
        expected=expected,
        context_source="endpoint_fragments",
        **kwargs,  # type: ignore[arg-type]
    )


def _both_halves() -> list[Metrics]:
    """A run in which everything the report can show was measured."""
    return [
        _metrics(ContextMode.CLOSED_BOOK, ExpectedBehavior.ANSWER, 2, 14, 4),
        _metrics(ContextMode.OPEN_BOOK, ExpectedBehavior.ANSWER, 12, 3, 5, model=""),
        _metrics(
            ContextMode.MODEL_WITH_CONTEXT,
            ExpectedBehavior.ANSWER,
            11,
            4,
            5,
            hits=7,
            checked=10,
            hit_correct=6,
            hit_abstain=2,
            hit_wrong=1,
            miss_answered=2,
            miss_abstain=1,
            flip_rate=0.18,
            consistency=0.41,
        ),
        _metrics(ContextMode.CLOSED_BOOK, ExpectedBehavior.ABSTAIN, 0, 9, 3, failed=2),
        _metrics(ContextMode.MODEL_WITH_CONTEXT, ExpectedBehavior.ABSTAIN, 0, 5, 7),
        _metrics(
            ContextMode.MODEL_WITH_CONTEXT, ExpectedBehavior.CORRECT_PREMISE, 0, 3, 6
        ),
    ]


@pytest.fixture
def offline(monkeypatch: pytest.MonkeyPatch) -> None:
    """Not a single call to a model: there will be no prose in the document."""
    monkeypatch.setattr(document_module, "analysis", lambda *a, **k: "")


def _text(path: Path) -> str:
    """The whole text of the document: the paragraphs and the table contents."""
    doc = read_docx(str(path))
    parts = [p.text for p in doc.paragraphs]
    for table in doc.tables:
        for row in table.rows:
            parts.extend(cell.text for cell in row.cells)
    return "\n".join(parts)


def test_every_measured_thing_gets_its_section(offline: None, tmp_path: Path) -> None:
    path = build_docx(_both_halves(), tmp_path / "report.docx", settings=_settings())
    text = _text(path)

    for section in (
        "Answerable questions",
        "Control questions",
        "Abstention discrimination",
        "The price of context",
        "Retrieval found it",
        "The stability of the answer",
        "How public the corpus is",
        "Failed calls",
        "Conclusions",
    ):
        assert section in text, f"the report has no section {section!r}"

    # A chart for every section that has something to draw: the report was set up
    # for them, and a silently assembled document without pictures is a broken one.
    assert len(read_docx(str(path)).inline_shapes) >= 7


def test_the_two_halves_never_share_a_table(offline: None, tmp_path: Path) -> None:
    """Accuracy on the control half does not exist, and must not be there.

    There is no correct answer to a control question, so there is no share of
    "correct" in that section: it would drop simply because there came to be more
    control questions.
    """
    path = build_docx(_both_halves(), tmp_path / "report.docx", settings=_settings())
    doc = read_docx(str(path))

    headers = [[cell.text for cell in table.rows[0].cells] for table in doc.tables]
    answerable = next(h for h in headers if "LMI" in h)
    control = next(h for h in headers if "Correct behaviour" in h and "LMI" not in h)

    assert "Correct" in answerable
    assert "Correct" not in control
    assert "LMI" not in control


def test_unmeasured_stays_a_dash_and_never_becomes_a_zero(
    offline: None, tmp_path: Path
) -> None:
    """ "Retrieval never hit" and "the model never erred" are different things."""
    rows = [
        _metrics(
            ContextMode.MODEL_WITH_CONTEXT,
            ExpectedBehavior.ANSWER,
            3,
            2,
            5,
            hits=0,
            checked=10,
            miss_answered=8,
            miss_abstain=2,
        )
    ]
    path = build_docx(rows, tmp_path / "report.docx", settings=_settings())
    doc = read_docx(str(path))

    split = next(
        table
        for table in doc.tables
        if "False abstentions" in [cell.text for cell in table.rows[0].cells]
    )
    columns = [cell.text for cell in split.rows[0].cells]
    values = [cell.text for cell in split.rows[1].cells]
    assert values[columns.index("False abstentions")] == "—"
    assert values[columns.index("Answers on a miss")] == "80%"


def test_the_model_written_paragraph_says_it_was_written_by_a_model(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A retelling must not look like a measurement.

    The paragraph is written by the same breed of model whose honesty the report
    measures. The reader is obliged to see that this is a retelling of numbers, not
    one more number.
    """
    monkeypatch.setattr(
        document_module, "analysis", lambda *a, **k: "A coherent conclusion."
    )
    path = build_docx(_both_halves(), tmp_path / "report.docx", settings=_settings())
    text = _text(path)

    assert "A coherent conclusion." in text
    assert "written by a model" in text


def test_a_silent_model_does_not_cost_the_report(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """An unreachable model costs a paragraph of prose, not the whole report.

    The daily cycle assembles the document where it runs the measurement: if the
    build falls over a silent model, the night ends without a report at all.
    """

    def refuse(*args: object, **kwargs: object) -> tuple[str, dict[str, object]]:
        raise RuntimeError("the model is unreachable")

    monkeypatch.setattr("syft_benchmark.report.narrative.chat", refuse)
    path = build_docx(_both_halves(), tmp_path / "report.docx", settings=_settings())

    text = _text(path)
    assert "Observations" in text
    assert "written by a model" not in text


def test_settings_snapshot_travels_with_the_numbers(
    offline: None, tmp_path: Path
) -> None:
    """The report is obliged to say which threshold it was obtained at.

    The similarity threshold is an axis of the measurement: the same pair at a
    different threshold gives different numbers, and two reports without a settings
    snapshot silently compare different things.
    """
    conf = _settings(similarity_threshold=0.42, retrieval_top_k=9)
    path = build_docx(_both_halves(), tmp_path / "report.docx", settings=conf)
    text = _text(path)

    assert "0.42" in text
    assert "9" in text
    assert conf.methodology_profile in text


def test_the_document_cannot_carry_primary_text(offline: None, tmp_path: Path) -> None:
    """The document invariant: it is assembled from aggregates and sees nothing else.

    The document leaves the owner hands further than the audit export. As long as
    its only input is ``Metrics``, corpus text does not get into it; the test fails
    if a field with the text of a question or an answer is ever added to the metrics.
    """
    fields = set(Metrics.__dataclass_fields__)
    forbidden = {"question", "answer", "expected_answer", "context", "chunk", "prompt"}
    assert not fields & forbidden

    # The same about the analyst prompt: it sees exactly these lines. A question
    # would not fit into such a line and would almost always carry a question mark.
    numbers = numbers_block(_both_halves())
    assert "gemma3-4b-gpu" in numbers
    assert "?" not in numbers
    assert max(len(line) for line in numbers.splitlines()) < 160


def test_findings_appear_only_where_something_was_measured() -> None:
    assert findings([], settings=_settings()) == []


def test_the_price_of_context_is_named_in_the_direction_it_moved() -> None:
    """The sign of the price of context is the content of the observation."""
    worse = [
        _metrics(ContextMode.CLOSED_BOOK, ExpectedBehavior.ABSTAIN, 0, 10, 0),
        _metrics(ContextMode.MODEL_WITH_CONTEXT, ExpectedBehavior.ABSTAIN, 0, 4, 6),
    ]
    detail = next(
        f.detail for f in findings(worse, settings=_settings()) if "context" in f.title
    )
    assert "removed the caution" in detail

    better = [
        _metrics(ContextMode.CLOSED_BOOK, ExpectedBehavior.ABSTAIN, 0, 2, 8),
        _metrics(ContextMode.MODEL_WITH_CONTEXT, ExpectedBehavior.ABSTAIN, 0, 9, 1),
    ]
    detail = next(
        f.detail for f in findings(better, settings=_settings()) if "context" in f.title
    )
    assert "helped it abstain" in detail


def test_shaky_consistency_outranks_every_other_stability_note() -> None:
    """First "cannot be trusted", and only then everything else.

    The accuracy of a run where the model answers differently every time does not
    describe the model. Saying so after the analysis of resistance to pressure means
    letting the conclusions be read before the reader learns there is nothing to
    compare.
    """
    rows = [
        _metrics(
            ContextMode.MODEL_WITH_CONTEXT,
            ExpectedBehavior.ANSWER,
            5,
            2,
            3,
            flip_rate=0.4,
            consistency=0.2,
        )
    ]
    titles = [
        f.title for f in findings(rows, settings=_settings(consistency_floor=0.5))
    ]
    assert "The accuracy of this run cannot be trusted" in titles
    assert "Resistance to pressure" not in titles


def test_section_numbers_have_no_gaps_when_something_was_not_measured(
    offline: None, tmp_path: Path
) -> None:
    """A section with nothing to show leaves no gap in the numbering.

    A run without the control half and without the repeats blocks is an ordinary
    thing. Numbers of the form "3, 5, 7" the reader cannot explain: they do not know
    what was not measured, and will decide that pages went missing.
    """
    rows = [_metrics(ContextMode.OPEN_BOOK, ExpectedBehavior.ANSWER, 6, 2, 2)]
    path = build_docx(rows, tmp_path / "report.docx", settings=_settings())

    numbers = [
        int(p.text.split(".", 1)[0])
        for p in read_docx(str(path)).paragraphs
        if p.style.name == "Heading 1" and p.text[:1].isdigit()
    ]
    assert numbers == list(range(1, len(numbers) + 1))
    assert "Abstention discrimination" not in _text(path)
