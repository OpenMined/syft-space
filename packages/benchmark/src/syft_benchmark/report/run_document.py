"""The summary document of one run, built from its aggregate alone.

No question and no corpus text goes in: only the run's figures, as the run
report shows them.
"""

from __future__ import annotations

import io
import re
from datetime import UTC, datetime
from typing import Any

from docx import Document
from docx.shared import Pt

from syft_benchmark.report import charts
from syft_benchmark.report.document import _heading, _image, _note, _para, _table

GROUP_LABEL = {
    "fixed": "Fixed by your data",
    "either": "Right either way",
    "still": "Wrong either way",
    "worse": "Made worse by your data",
}


def _pct(value: float | None) -> str:
    return "—" if value is None else f"{value:.0%}"


def _points(value: int | None) -> str:
    return "—" if value is None else f"{value:+d} pts"


def _count(value: int | None) -> str:
    return "—" if value is None else str(value)


def _stamp(value: str | None) -> str:
    if not value:
        return "—"
    return datetime.fromisoformat(value).astimezone(UTC).strftime("%Y-%m-%d %H:%M UTC")


def filename(slug: str, created_at: datetime | None) -> str:
    """``<slug>-<YYYY-MM-DD-HHMM>.docx``."""
    clean = re.sub(r"[^A-Za-z0-9]+", "-", slug).strip("-").lower() or "run"
    stamp = (
        created_at.astimezone(UTC).strftime("%Y-%m-%d-%H%M")
        if created_at
        else "undated"
    )
    return f"{clean}-{stamp}.docx"


def build_summary(report: dict[str, Any], *, title: str) -> bytes:
    """The .docx of one run report (``run_view`` payload without questions)."""
    run = report["run"]
    models = report["models"]
    funnel = report["funnel"]
    method = report["method"]

    doc = Document()
    doc.styles["Normal"].font.size = Pt(10)
    doc.add_heading(f"Benchmark results: {title}", level=0)
    _para(
        doc,
        f"Run of {_stamp(run['created_at'])}, finished {_stamp(run['finished_at'])}",
    )
    lifts = (
        f" Your data moved accuracy by {_points(run['lift_lo'])} to "
        f"{_points(run['lift_hi'])}."
        if run["lift_lo"] is not None
        else ""
    )
    _para(
        doc,
        f"{_count(run['questions'])} questions from {_count(run['articles'])} "
        f"articles, asked to {len(models)} "
        f"{'model' if len(models) == 1 else 'models'} on their own and with "
        f"passages from your archive.{lifts}",
    )

    _heading(doc, "Accuracy by model")
    _table(
        doc,
        [
            "Model",
            "Questions",
            "Right on its own",
            "Right with your data",
            "Lift",
            "Made up on its own",
            "Made up with your data",
            "Awaiting a verdict",
            "Technical failures",
        ],
        [
            [
                m["model"],
                str(m["asked"]),
                _pct(m["rate_alone"]),
                _pct(m["rate_with"]),
                _points(m["lift"]),
                _pct(m["made_up_alone"]),
                _pct(m["made_up_with"]),
                str(m["pending"]),
                str(m["technical"]),
            ]
            for m in models
        ],
    )
    if models:
        _image(
            doc,
            charts.grouped(
                [m["model"] for m in models],
                [
                    ("On its own", [m["rate_alone"] for m in models], charts.NEUTRAL),
                    ("With your data", [m["rate_with"] for m in models], charts.GOOD),
                ],
                title="Share of right answers",
            ),
        )
    _note(
        doc,
        "Rates are over graded answers. Answers awaiting a verdict and technical "
        "failures are counted apart and are not in any rate. Trick questions "
        "(no answer exists) are only in the trick check.",
    )

    _heading(doc, "What your data changed")
    _table(
        doc,
        ["Model", *GROUP_LABEL.values()],
        [[m["model"], *(str(m["groups"][g]) for g in GROUP_LABEL)] for m in models],
    )

    _heading(doc, "By kind of question")
    _table(
        doc,
        ["Model", "Kind", "Questions", "On its own", "With your data", "Lift"],
        [
            [
                m["model"],
                k["generator"],
                str(k["asked"]),
                _pct(k["rate_alone"]),
                _pct(k["rate_with"]),
                _points(k["lift"]),
            ]
            for m in models
            for k in m["kinds"]
        ],
    )

    _heading(doc, "Reliability checks")
    _table(
        doc,
        [
            "Model",
            "Kept a right answer when challenged",
            "Same answer when asked again",
            "Trick questions answered (with data)",
            "Trick questions answered (on its own)",
            "Search found the passage",
            "Judges agreed",
        ],
        [
            [
                m["model"],
                _pct(c["kept_right"]),
                _pct(c["same_answer"]),
                f"{c['trick_answered']} of {c['trick_asked']}",
                f"{c['trick_alone_answered']} of {c['trick_alone_asked']}",
                _pct(c["search_found"]),
                _pct(c["agreement"]),
            ]
            for m in models
            for c in [m["checks"]]
        ],
    )

    _heading(doc, "How this was tested")
    removed = ", ".join(f"{k}: {v}" for k, v in sorted(funnel["removed"].items()))
    _table(
        doc,
        ["", ""],
        [
            ["Questions written", _count(funnel["written"])],
            [
                "Removed by quality checks",
                _count(funnel["removed_total"]) + (f" ({removed})" if removed else ""),
            ],
            *(
                [["Not asked: web check pending", _count(funnel["unchecked"])]]
                if funnel.get("unchecked")
                else []
            ),
            ["Questions asked", str(funnel["asked"])],
            ["Trick questions", str(funnel["trick"])],
            ["Questions written by", method["generator_model"] or "—"],
            ["Kinds of question", ", ".join(method["kinds"]) or "—"],
            ["Passages given with your data", _count(method["context_docs"])],
            ["Judges (primary first)", ", ".join(report["judges"]) or "—"],
            ["Method version", method["profile"] or "—"],
        ],
    )

    out = io.BytesIO()
    doc.save(out)
    return out.getvalue()
