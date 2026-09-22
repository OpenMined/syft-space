"""Stage 5: aggregating verdicts into metrics and a report."""

from syft_benchmark.report.audit import (
    AuditExport,
    audit_records,
    export_audit,
    render_audit_markdown,
)
from syft_benchmark.report.document import build_docx
from syft_benchmark.report.metrics import (
    Metrics,
    abstention_discrimination,
    context_effect,
    context_effect_pairs,
    discrimination_pairs,
    judges_seen,
    models_seen,
    render_markdown,
    summarize,
)
from syft_benchmark.report.narrative import Finding, findings
from syft_benchmark.report.slices import (
    AGREEMENT_FLOOR,
    GeneratorSlice,
    JudgePair,
    average_agreement,
    by_generator,
    judge_agreement,
)

__all__ = [
    "AGREEMENT_FLOOR",
    "AuditExport",
    "GeneratorSlice",
    "JudgePair",
    "average_agreement",
    "by_generator",
    "judge_agreement",
    "Finding",
    "Metrics",
    "abstention_discrimination",
    "audit_records",
    "build_docx",
    "context_effect",
    "context_effect_pairs",
    "discrimination_pairs",
    "export_audit",
    "findings",
    "judges_seen",
    "models_seen",
    "render_audit_markdown",
    "render_markdown",
    "summarize",
]
