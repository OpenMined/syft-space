"""Testing a model, or judging answers, by hand through a chat.

**A console model** answers questions exported as one block of text; the pasted
answers are judged like an ordinary run. It is for reconnaissance of a model
with no API, not for the report: no temperature (so no ``monte_carlo``), no
programmatic dialogue (so no ``denial_loop``), a chat product's system prompt
and tools in the way, and a small sample.

**A console judge** grades answers already recorded (``export-judging`` /
``import-judging``): it needs neither a temperature nor a dialogue, and a
subscription takes the place of the judge's API bill. Answers recorded with
``evaluate --defer-judging`` can be judged this way.
"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sqlalchemy import select

from syft_benchmark.config import (
    ContextMode,
    ContextSource,
    EvalBlock,
    PairStatus,
    Settings,
    Verdict,
    get_settings,
)
from syft_benchmark.db import QaPair, Result, Run, session_scope
from syft_benchmark.llm import judge_provider
from syft_benchmark.runs.execute import CLOSED_BOOK_SYSTEM
from syft_benchmark.runs.gate import evaluable
from syft_benchmark.runs.judge import (
    JUDGE_RULES,
    Gradable,
    Grade,
    VerdictCounts,
    date_note,
    explanation_grade,
    free_text_grade,
    grade_item,
    is_error,
)
from syft_benchmark.runs.judge_stage import Task, pending_tasks
from syft_benchmark.runs.regrade import (
    VerdictRuns,
    answer_audit,
    answer_extra,
    columns,
    copy_result,
)


def _questions_header(count: int) -> str:
    """The closed-book instruction of an API run, put to a list of questions."""
    return (
        f"Below are {count} questions. Follow these instructions for each one.\n\n"
        f"{CLOSED_BOOK_SYSTEM}\n"
        "Return your answers as a JSON array, one object per question, "
        "nothing else:\n"
        '[{"id": "<the id given below>", "answer": "..."}]\n'
    )


# A pasted reply is a JSON array or a numbered list; both are parsed.
_NUMBERED_RE = re.compile(r"^\s*(?:#|№)?\s*([0-9a-f]{6,32})\s*[:.\)]\s*(.+)$")


@dataclass(slots=True, kw_only=True)
class ConsoleReport(VerdictCounts):
    """The result of a manual run."""

    run_id: str = ""
    exported: int = 0
    matched: int = 0
    missing: int = 0
    notes: list[str] = field(default_factory=list)


def export_questions(
    space: str,
    out: Path,
    *,
    limit: int = 20,
    settings: Settings | None = None,
) -> ConsoleReport:
    """Export the questions as one block of text for pasting into a chat.

    Each question carries its pair id: a chat's answers come back in no
    guaranteed order.

    Args:
        space: The Space key
        out: Where to put the text
        limit: How many questions to export
        settings: The process settings

    Returns:
        A ConsoleReport with the number of questions exported
    """
    conf = settings or get_settings()
    with session_scope(conf) as session:
        rows = list(
            session.execute(
                select(QaPair)
                .where(
                    QaPair.space == space,
                    QaPair.status == PairStatus.ACTIVE.value,
                )
                .order_by(QaPair.created_at)
            ).scalars()
        )
        # Only questions that passed the web check are put to a model.
        pairs = [(r.id, r.question) for r in evaluable(rows, conf)][:limit]

    lines = [_questions_header(len(pairs)), ""]
    for pair_id, question in pairs:
        lines.append(f"--- {pair_id}")
        lines.append(question)
        lines.append("")

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    return ConsoleReport(exported=len(pairs))


def _pasted_items(text: str) -> list[dict[str, Any]]:
    """The objects of the JSON array in a pasted reply; empty where there is none.

    The array is taken from the first ``[`` to the last ``]``: a chat wraps it
    in prose and code fences.
    """
    start = text.find("[")
    if start < 0:
        return []
    try:
        parsed = json.loads(text[start : text.rindex("]") + 1])
    except (json.JSONDecodeError, ValueError):
        return []
    if not isinstance(parsed, list):
        return []
    return [item for item in parsed if isinstance(item, dict)]


def parse_answers(text: str) -> dict[str, str]:
    """Pull the answers out of what was pasted: a JSON array or "<id>: answer" lines."""
    answers: dict[str, str] = {}

    for item in _pasted_items(text):
        key = str(item.get("id") or "").strip()
        value = str(item.get("answer") or "").strip()
        if key and value:
            answers[key] = value
    if answers:
        return answers

    for line in text.splitlines():
        match = _NUMBERED_RE.match(line)
        if match:
            answers[match.group(1)] = match.group(2).strip()
    return answers


def import_answers(
    space: str,
    source: Path,
    model: str,
    *,
    settings: Settings | None = None,
) -> ConsoleReport:
    """Parse the pasted answers, judge them and record them as a run.

    The run is recorded as ``direct`` and ``closed_book``: the only block and
    arm manual testing supports.

    Args:
        space: The Space key
        source: The file with the answers
        model: What answered — it goes into the report as the name of the model
            under test
        settings: The process settings

    Returns:
        A ConsoleReport with the parsing and the verdicts
    """
    conf = settings or get_settings()
    judge = judge_provider(conf)
    answers = parse_answers(source.read_text(encoding="utf-8"))

    report = ConsoleReport()
    if not answers:
        report.notes.append("not a single answer was found in the file")
        return report

    run_id = uuid.uuid4().hex
    with session_scope(conf) as session:
        session.add(
            Run(
                id=run_id,
                space=space,
                context_mode=ContextMode.CLOSED_BOOK.value,
                context_source=ContextSource.NONE.value,
                profile=conf.methodology_profile,
                block=EvalBlock.DIRECT.value,
                model=model,
                model_vendor="",
                judge_model=judge.model,
                note="manual testing through a chat",
            )
        )
    report.run_id = run_id

    with session_scope(conf) as session:
        rows = list(
            session.execute(
                select(QaPair).where(QaPair.id.in_(list(answers)))
            ).scalars()
        )
        for row in rows:
            session.expunge(row)
        pairs = rows

    report.missing = len(answers) - len(pairs)
    for pair in pairs:
        answer = answers[pair.id]
        # Graded by the item's kind, as in an ordinary run.
        verdict = grade_item(Gradable.of(pair), answer, settings=conf, judge=judge)

        with session_scope(conf) as session:
            session.add(
                Result(
                    id=uuid.uuid4().hex,
                    run_id=run_id,
                    qa_id=pair.id,
                    space=space,
                    answer=answer[:8000],
                    verdict=verdict.verdict.value,
                    reasoning=verdict.reasoning,
                    expected_behavior=pair.expected_behavior,
                    extra={
                        "source": "console",
                        **({"behavior": verdict.behavior} if verdict.behavior else {}),
                    },
                    model=model,
                    judge_model=judge.model,
                    judge_served_by=verdict.served_by,
                )
            )

        report.matched += 1
        report.count(verdict)

    return report


def _judging_header(count: int) -> str:
    """The API judge's rules, put to a list of items."""
    return (
        f"Below are {count} graded items. For each one you are given a question, "
        "the expected answer (or the facts an explanation must cover), and the "
        "answer a model produced. Decide whether the model answer is correct.\n\n"
        f"{JUDGE_RULES}\n"
        f"{date_note()}\n\n"
        "Return your verdicts as a JSON array, one object per item, nothing else:\n"
        '[{"id": "<the id given below>", "correct": true, "false_claims": false, '
        '"reasoning": "one short sentence"}]\n'
    )


# A pasted verdict line: "<id>: correct — reasoning". A line carries no
# "false_claims", so an incorrect one counts as did not know, as with an API
# judge that leaves the field out.
_VERDICT_RE = re.compile(
    r"^\s*([0-9a-f]{6,32})\s*[:.\)]\s*(correct|incorrect|wrong|yes|no|true|false)"
    r"\s*[—\-:]?\s*(.*)$",
    re.IGNORECASE,
)

_POSITIVE = {"correct", "yes", "true"}


@dataclass(slots=True, kw_only=True)
class JudgingReport(VerdictCounts):
    """The result of exporting or importing console judging."""

    run_ids: list[str] = field(default_factory=list)
    exported: int = 0
    matched: int = 0
    missing: int = 0
    notes: list[str] = field(default_factory=list)


def _task_lines(task: Task) -> list[str]:
    """One exported item: the question, what it is graded against, the answer."""
    meta = task.item.meta or {}
    key_facts = [str(f) for f in meta.get("key_facts", [])]
    hop_facts = [str(f) for f in meta.get("hop_facts") or []]
    lines = [f"--- {task.result_id}", f"Question:\n{task.item.question}"]
    if str(meta.get("grading") or "judge") == "key_facts" and key_facts:
        # A machine judge computes the share of facts covered; a human gives
        # a yes/no over the same list, read as an explanation's verdict.
        facts = "\n".join(f"  {i + 1}. {f}" for i, f in enumerate(key_facts))
        lines.append(f"Facts the explanation must cover:\n{facts}")
    else:
        lines.append(f"Expected answer:\n{task.item.expected}")
        if hop_facts:
            # Connect the facts: what a correct answer must state, every one.
            facts = "\n".join(f"  {i + 1}. {f}" for i, f in enumerate(hop_facts))
            lines.append(f"Required facts:\n{facts}")
    lines.append(f"Model answer:\n{task.answer}")
    lines.append("")
    return lines


def export_judging(
    space: str,
    out: Path,
    judge: str,
    *,
    only_pending: bool = False,
    limit: int | None = None,
    settings: Settings | None = None,
) -> JudgingReport:
    """Export the recorded answers for judging by a human or a chat.

    Args:
        space: The Space key
        out: Where to put the task text
        judge: The name the verdicts will go into the report under
        only_pending: Only the pending answers and those whose judge call
            failed; otherwise every direct-test answer this judge has not
            graded, as a further opinion
        limit: How many to export; empty — all of them
        settings: The process settings

    Returns:
        A JudgingReport with the number of tasks exported
    """
    conf = settings or get_settings()
    tasks = pending_tasks(
        space, judge_name=judge, only_pending=only_pending, limit=limit, settings=conf
    )
    report = JudgingReport(exported=len(tasks))
    if not tasks:
        report.notes.append(
            "there is nothing to judge: either there are no direct-test answers "
            "yet, or this judge has already judged them (pressure and repeats are "
            "judged as they go and are not exported to a console judge)"
        )
        return report

    lines = [_judging_header(len(tasks)), ""]
    for task in tasks:
        lines += _task_lines(task)

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    return report


def parse_verdicts(text: str) -> dict[str, tuple[Verdict, str]]:
    """Pull the verdicts out of what was pasted.

    A JSON array or ``<id>: correct — reasoning`` lines; each is read as the API
    judge's reply is (``free_text_grade``).
    """
    verdicts: dict[str, tuple[Verdict, str]] = {}

    for item in _pasted_items(text):
        key = str(item.get("id") or "").strip()
        if key and "correct" in item:
            verdicts[key] = free_text_grade(item)
    if verdicts:
        return verdicts

    for line in text.splitlines():
        match = _VERDICT_RE.match(line)
        if match:
            verdicts[match.group(1)] = free_text_grade(
                {
                    "correct": match.group(2).lower() in _POSITIVE,
                    "reasoning": match.group(3).strip(),
                }
            )
    return verdicts


def import_judging(
    space: str,
    source: Path,
    judge: str,
    *,
    settings: Settings | None = None,
) -> JudgingReport:
    """Record the console verdicts as the assessment of a separate judge.

    A new run per (arm, source, block, model) carries the verdicts under the
    console judge's name, so they enter the report and judge agreement like a
    machine judge's (``runs.regrade``). Only real direct-test answers take a
    verdict, as in the export: a verdict on a failed call or on a pressure or
    repeats row is skipped and counted in the notes.

    Args:
        space: The Space key
        source: The file with the verdicts
        judge: The judge name — it goes into the report
        settings: The process settings

    Returns:
        A JudgingReport with the parsing and the verdicts
    """
    conf = settings or get_settings()
    verdicts = parse_verdicts(source.read_text(encoding="utf-8"))

    report = JudgingReport()
    if not verdicts:
        report.notes.append("not a single verdict was found in the file")
        return report

    with session_scope(conf) as session:
        rows = session.execute(
            select(Result, Run)
            .join(Run, Run.id == Result.run_id)
            .where(Result.id.in_(list(verdicts)), Result.space == space)
        ).all()
        source_rows = [(columns(result), columns(run)) for result, run in rows]
        # The items graded by key facts: their verdicts are read as such.
        explanations = {
            qa_id
            for qa_id, meta in session.execute(
                select(QaPair.id, QaPair.meta).where(
                    QaPair.id.in_({str(r["qa_id"]) for r, _ in source_rows})
                )
            ).all()
            if str((meta or {}).get("grading") or "judge") == "key_facts"
        }

    report.missing = len(verdicts) - len(source_rows)
    if not source_rows:
        report.notes.append(
            "not a single identifier matched: the verdicts are not from this Space "
            "or the file was assembled from a different export"
        )
        return report

    gradable = [
        (result_row, run_row)
        for result_row, run_row in source_rows
        if run_row["block"] == EvalBlock.DIRECT.value
        and not is_error(str(result_row["answer"] or ""))
    ]
    skipped = len(source_rows) - len(gradable)
    if skipped:
        report.notes.append(
            f"{skipped} verdicts skipped: a failed call or not a direct-test "
            "answer, which only a judge in the loop grades"
        )

    runs = VerdictRuns(space, judge, "console judging")
    for result_row, run_row in gradable:
        verdict, reasoning = verdicts[str(result_row["id"])]
        if str(result_row["qa_id"]) in explanations:
            verdict, reasoning = explanation_grade(
                verdict, reasoning, str(result_row["answer"] or "")
            )
        audit = answer_audit(result_row["audit"])
        audit["judged_by_console"] = judge

        with session_scope(conf) as session:
            session.add(
                copy_result(
                    result_row,
                    run_id=runs.run_id_for(session, run_row),
                    verdict=verdict.value,
                    reasoning=reasoning or "console judge",
                    extra=answer_extra(result_row["extra"]),
                    audit=audit,
                    judge_model=judge,
                )
            )

        report.matched += 1
        report.count(Grade(verdict, reasoning))

    report.run_ids = runs.run_ids
    return report
