"""The audit export: the raw records of the measurement.

The benchmark metrics are shares computed from a judge model verdicts. They
cannot be checked against the shares themselves: to say whether a measurement is
honest you need to see what exactly was asked, with what prompt, what was
answered in each arm and how the judge justified its sentence. Hence this export
— it hands over exactly the raw records, one record per question:

  * the question and the gold answer, together with their provenance: which
    document and chunk it grew from, by which generator, whether it passed
    screening and with what note;
  * the answer in each arm — A, B, C — side by side rather than in three
    different exports: the comparison of the arms is the subject of the check;
  * the prompts: system and user, and for arm C together with the material mixed
    in, verbatim;
  * each judge verdict with its prompt and its raw answer before parsing;
  * the settings the run was obtained with: the similarity threshold, the number
    of chunks, the methodology profile.

The format is JSON Lines: one record per line, read line by line and requiring
nothing to be loaded into memory whole. The second format, Markdown, is for
reading by eye.

**The export contains corpus text.** Arm C prompt carries the retrieved chunks
in full, and gold answers not infrequently quote the source verbatim. This is not
a side effect but the point of the export: an auditor has nothing to check
without the original text. The file should be handled like the corpus itself, and
handed only to someone who has access to the corpus anyway.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select

from syft_benchmark.config import ARM_LETTER
from syft_benchmark.db import QaPair, Result, Run, session_scope


@dataclass(frozen=True, slots=True)
class AuditExport:
    """What came out of one export."""

    path: Path
    questions: int
    answers: int
    arms: tuple[str, ...]
    judges: tuple[str, ...]
    with_prompts: int


def _stamp(moment: datetime | None) -> str | None:
    return moment.isoformat() if moment else None


def _answer_record(
    result: Result, run: Run, *, include_context: bool
) -> dict[str, Any]:
    """One answer in one arm, with the full trace of how it was obtained."""
    audit = dict(result.audit or {})
    if not include_context:
        # A trimmed export: without the text of the chunks. It will do for
        # showing the design of the measurement to someone not entitled to the
        # corpus — but a verdict cannot be checked against it, and that is said
        # outright in the record itself.
        audit.pop("context", None)
        audit["responder_prompt"] = "[cut out: --no-context]"
        audit["judge_prompt"] = "[cut out: --no-context]"

    return {
        "arm": ARM_LETTER.get(run.context_mode, "?"),
        "context_mode": run.context_mode,
        "context_source": run.context_source,
        "block": run.block,
        "responder": result.model,
        "endpoint_response_type": result.endpoint_response_type,
        "answer": result.answer,
        "verdict": result.verdict,
        "reasoning": result.reasoning,
        "judge": result.judge_model,
        "grounded": result.grounded,
        "grounded_note": result.grounded_note,
        "retrieval": {
            "hit": result.retrieval_hit,
            "rank": result.retrieval_rank,
            "fragments": (
                result.retrieved
                if include_context
                else [
                    {k: v for k, v in doc.items() if k != "content"}
                    for doc in (result.retrieved or [])
                ]
            ),
        },
        "blocks": result.extra or {},
        "prompts": audit,
        "run": {
            "id": run.id,
            "profile": run.profile,
            "params": run.params or {},
            "started_at": _stamp(run.started_at),
        },
        "latency_s": result.latency_s,
        "at": _stamp(result.created_at),
    }


def audit_records(
    space: str,
    *,
    judge: str | None = None,
    include_context: bool = True,
    job: str | None = None,
) -> Iterator[dict[str, Any]]:
    """The raw records of the measurement, one per question.

    The answers of all the arms are gathered into one record: the comparison of
    A, B and C is the subject of the check, and laying them out in different
    files would mean making the auditor stitch the export together themselves.

    The LATEST answer is taken for each combination of arm, block, answerer and
    judge — by the same rule the metrics are computed with. Otherwise the audit
    would be looking at one set of records and the report at another.

    ``job`` narrows the export to one launch. That is what makes an audit a check
    of a measurement rather than of a node: a verdict is examined together with
    the settings it was obtained under, and those change between launches. Mixing
    two launches into one export would put answers obtained at different
    similarity thresholds side by side under one heading.

    Args:
        space: The key of the node under test
        judge: Keep one judge verdicts; None — all of them
        include_context: Whether to include the chunk text and the whole prompts
        job: Keep the records of one launch; None — the whole history of the node

    Yields:
        One record per question: the item, its provenance and the answers by arm
    """
    where = [Result.space == space]
    if judge:
        where.append(Result.judge_model == judge)
    if job:
        where.append(Run.job_id == job)

    with session_scope() as session:
        rows = session.execute(
            select(Result, Run, QaPair)
            .join(Run, Run.id == Result.run_id)
            .join(QaPair, QaPair.id == Result.qa_id)
            .where(*where)
            .order_by(QaPair.created_at, Result.created_at)
        ).all()

        by_question: dict[str, dict[str, Any]] = {}
        # The latest answer for each combination: the same selection as the metrics.
        newest: dict[tuple[str, str, str, str, str], dict[str, Any]] = {}

        for result, run, pair in rows:
            record = by_question.get(pair.id)
            if record is None:
                record = {
                    "qa_id": pair.id,
                    "space": pair.space,
                    "collection": pair.collection,
                    "generator": pair.generator,
                    "task_type": pair.task_type,
                    "expected_behavior": pair.expected_behavior,
                    "question": pair.question,
                    "gold": pair.answer,
                    "distractors": pair.distractors,
                    "source": {
                        "doc_id": pair.doc_id,
                        "chunk_id": pair.chunk_id,
                        "document_title": pair.document_title,
                        "file_name": pair.file_name,
                        # The chunk the question grew from. Without it neither
                        # the gold answer nor the control set labelling can be
                        # checked.
                        "fragment": pair.context if include_context else "",
                    },
                    "dataset": {
                        "status": pair.status,
                        "status_note": pair.status_note,
                        "built_by": pair.model,
                        "meta": pair.meta or {},
                        "created_at": _stamp(pair.created_at),
                    },
                    "answers": [],
                }
                by_question[pair.id] = record

            key = (
                pair.id,
                run.context_mode,
                run.block,
                result.model,
                result.judge_model,
            )
            entry = _answer_record(result, run, include_context=include_context)
            previous = newest.get(key)
            if previous is None:
                newest[key] = entry
                record["answers"].append(entry)
            else:
                # A question can be rechecked as many times as you like; the last
                # answer goes into the export, as it does into the metrics.
                previous.clear()
                previous.update(entry)

        yield from by_question.values()


def export_audit(
    space: str,
    path: Path,
    *,
    judge: str | None = None,
    include_context: bool = True,
    job: str | None = None,
) -> AuditExport:
    """Export the raw records to a file.

    The format follows the extension: ``.md`` for reading by eye, anything else
    """
    records = list(
        audit_records(space, judge=judge, include_context=include_context, job=job)
    )
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.suffix.lower() == ".md":
        path.write_text(render_audit_markdown(records), encoding="utf-8")
    else:
        with path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    answers = [a for r in records for a in r["answers"]]
    return AuditExport(
        path=path,
        questions=len(records),
        answers=len(answers),
        arms=tuple(sorted({str(a["arm"]) for a in answers})),
        judges=tuple(sorted({str(a["judge"]) for a in answers if a["judge"]})),
        with_prompts=sum(1 for a in answers if a["prompts"].get("responder_prompt")),
    )


def render_audit_markdown(records: list[dict[str, Any]]) -> str:
    """The same records, but for reading by eye.

    The order within a question is by arm: A, B, C. That shows the main thing the
    export is made for: what the model answered without data, what the endpoint
    returned, and what the same model said once it got the material.
    """
    lines = [
        "# Audit export",
        "",
        "The raw records of the measurement: the question, the gold answer, the",
        "answers by arm and the prompts they were obtained with. Contains corpus",
        "text — handle it as such.",
        "",
    ]
    for record in records:
        lines += [
            f"## {record['qa_id']}  ({record['generator']})",
            "",
            f"**Correct behaviour:** {record['expected_behavior']}",
            "",
            f"**Question:** {record['question']}",
            "",
            f"**Gold answer:** {record['gold']}",
            "",
            f"**Source:** {record['source']['file_name']} "
            f"/ {record['source']['chunk_id']}",
            "",
        ]
        if record["dataset"]["status_note"]:
            lines += [f"**Screened out:** {record['dataset']['status_note']}", ""]

        for answer in sorted(record["answers"], key=lambda a: str(a["arm"])):
            lines += [
                f"### Arm {answer['arm']} — {answer['context_mode']}"
                f" / {answer['block']}",
                "",
                f"* answerer: `{answer['responder']}`",
                f"* context: `{answer['context_source']}`",
                f"* verdict: **{answer['verdict']}** (judge `{answer['judge']}`)",
                f"* reasoning: {answer['reasoning']}",
                "",
                "**Answer:**",
                "",
                "```",
                str(answer["answer"]),
                "```",
                "",
            ]
            prompt = answer["prompts"].get("responder_prompt")
            if prompt:
                lines += ["**Answerer prompt:**", "", "```", str(prompt), "```", ""]
            judge_prompt = answer["prompts"].get("judge_prompt")
            if judge_prompt:
                lines += ["**Judge prompt:**", "", "```", str(judge_prompt), "```", ""]
    return "\n".join(lines) + "\n"
