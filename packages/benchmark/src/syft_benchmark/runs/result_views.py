"""Stored verdicts read back for the console: one result, or a page of them.

Each view says whether its row is the verdict that stands: an owner override
stands over the whole panel; failing that, each judge's freshest verdict
stands for that judge.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy import func, select

from syft_benchmark.config import Settings, get_settings
from syft_benchmark.db import QaPair, Result, Run, session_scope
from syft_benchmark.question_order import answer_order, pair_order
from syft_benchmark.runs.judge_stage import OWNER_OVERRIDE, citations_of

# A page any larger stops being something a person reviews.
MAX_PAGE = 200


@dataclass(slots=True)
class DenialView:
    """How the pressure on one answer ended.

    ``rounds`` is how many objections were put: the loop stops at the one the
    model gives in on, so a flipped outcome has ``rounds == flip_round``.
    """

    rounds: int
    flipped: bool
    flip_round: int | None
    note: str
    # The objections configured for the run: without it "held 4 rounds"
    # cannot be told from "the run stopped after 4".
    limit: int
    # Round by round: the objection put and the answer it drew.
    log: list[dict[str, Any]]


@dataclass(slots=True)
class RepeatsView:
    """How far one answer repeated when the question was asked again.

    ``consistency`` is the share of repeats that gave the most frequent answer,
    not the share that were correct.
    """

    trials: int
    accuracy: float
    consistency: float
    by_temperature: dict[str, float]
    note: str
    # Every repeat: its temperature, what came back, whether it counted.
    log: list[dict[str, Any]]


@dataclass(slots=True)
class FragmentView:
    """One chunk the endpoint's retrieval returned for a question."""

    file_name: str
    score: float
    content: str


@dataclass(slots=True)
class PromptsView:
    """What was actually sent — for the answer, and for the verdict on it.

    Straight out of ``Result.audit``. Any field can be empty: the record is
    absent with ``audit_log`` off, the judge fields wherever the verdict cost
    no call. SENSITIVE: in arm C ``responder_prompt`` carries the chunks found.
    """

    responder_system: str
    responder_prompt: str
    # The material mixed into the arm C prompt, on its own as well.
    context: str
    judge_system: str
    judge_prompt: str
    judge_raw: str
    # The verdict was reached without asking a model (an option letter or
    # fill-in span matched, an abstention recognised): an empty judge prompt
    # then means nothing was asked, not that nothing was kept.
    judged_without_model: bool


@dataclass(slots=True)
class CallView:
    """How the call that produced an answer ended.

    The budget doubles until the answer fits or reaches ``answer_max_tokens``,
    so ``truncated`` means it reached that ceiling and still did not finish.
    Absent with ``audit_log`` off.
    """

    truncated: bool
    finish_reason: str
    # The budget the call ended on, after any doubling — the number to raise.
    max_tokens: int | None
    length_retries: int


@dataclass(slots=True)
class ResultView:
    """One verdict, as an owner reviewing judging needs to see it."""

    id: str
    qa_id: str
    question: str
    answer: str
    generator: str
    verdict: str
    reasoning: str
    judge_model: str
    context_mode: str
    block: str
    model: str
    created_at: datetime
    # Whether this verdict stands for its (arm, source, block, model,
    # question) and judge. Overriding only ever makes sense for one.
    is_latest: bool
    # Whether the job's figures count this row for its answer; set by the
    # report layer (``run_questions.counted_ids``), None outside one job.
    counted: bool | None = None

    # What the block did. The answer stored on a block row is the one the
    # block STARTED from, so without these the verdict looks unaccountable.
    denial: DenialView | None = None
    repeats: RepeatsView | None = None

    # Whether the chunk the question grew from was found, and where: an
    # abstention on a miss is correct, on a hit it is blindness. NULL where
    # nothing was retrieved, as in closed book.
    retrieval_hit: bool | None = None
    retrieval_rank: int | None = None

    # How the call ended, and the two ceilings of its run.
    call: CallView | None = None
    context_docs: int | None = None
    fragment_max_chars: int | None = None

    # Web search evidence: what the answer cited, and whether it was offered
    # search and cited nothing.
    citations: list[dict[str, str]] = field(default_factory=list)
    web_search_unused: bool = False
    # A control question's outcome (``ControlOutcome``); None elsewhere.
    behavior: str | None = None
    # BLEU / ROUGE / BERTScore against the gold answer; None — not computed.
    text_metrics: dict[str, float] | None = None

    # Asked for by name, one question at a time: over a page of rows the
    # trail is megabytes.
    prompts: PromptsView | None = None
    fragments: list[FragmentView] | None = None


def _log_of(block: dict[str, Any]) -> list[dict[str, Any]]:
    """A block's transcript; empty where none was recorded."""
    log = block.get("log")
    return (
        [entry for entry in log if isinstance(entry, dict)]
        if isinstance(log, list)
        else []
    )


def _denial_of(extra: Any) -> DenialView | None:
    """The denial block's outcome out of ``Result.extra``, if it ran."""
    block = extra.get("denial") if isinstance(extra, dict) else None
    if not isinstance(block, dict):
        return None
    flip_round = block.get("flip_round")
    return DenialView(
        rounds=int(block.get("rounds") or 0),
        flipped=bool(block.get("flipped")),
        flip_round=int(flip_round) if flip_round is not None else None,
        note=str(block.get("note") or ""),
        limit=int(block.get("limit") or 0),
        log=_log_of(block),
    )


def _repeats_of(extra: Any) -> RepeatsView | None:
    """The monte carlo block's outcome out of ``Result.extra``, if it ran."""
    block = extra.get("monte_carlo") if isinstance(extra, dict) else None
    if not isinstance(block, dict):
        return None
    by_temperature = block.get("by_temperature")
    return RepeatsView(
        trials=int(block.get("trials") or 0),
        accuracy=float(block.get("accuracy") or 0.0),
        consistency=float(block.get("consistency") or 0.0),
        by_temperature={
            str(key): float(value)
            for key, value in (
                by_temperature.items() if isinstance(by_temperature, dict) else ()
            )
        },
        note=str(block.get("note") or ""),
        log=_log_of(block),
    )


def behavior_of(extra: Any) -> str | None:
    """A control answer's ``extra.behavior``; None — not one, or graded before it."""
    value = extra.get("behavior") if isinstance(extra, dict) else None
    return str(value) if value else None


def _text_metrics_of(extra: Any) -> dict[str, float] | None:
    """``Result.extra["text_metrics"]``, the numeric scores only; None — absent."""
    scores = (extra or {}).get("text_metrics") if isinstance(extra, dict) else None
    if not isinstance(scores, dict):
        return None
    numeric = {
        str(key): float(value)
        for key, value in scores.items()
        if isinstance(value, int | float) and not isinstance(value, bool)
    }
    return numeric or None


def _unused_search(audit: Any) -> bool:
    """Search was offered and nothing was cited."""
    return isinstance(audit, dict) and bool(audit.get("web_search_unused"))


def _call_of(audit: Any) -> CallView | None:
    """How the answerer's call ended, where the record was kept."""
    call = audit.get("call") if isinstance(audit, dict) else None
    if not isinstance(call, dict):
        return None
    tokens = call.get("max_tokens")
    return CallView(
        truncated=bool(call.get("truncated")),
        finish_reason=str(call.get("finish_reason") or ""),
        max_tokens=int(tokens) if isinstance(tokens, int) else None,
        length_retries=int(call.get("length_retries") or 0),
    )


def _params_int(params: Any, name: str) -> int | None:
    """One number out of a run's settings snapshot; None where it has none.

    A default here would be a claim about how that run was measured.
    """
    value = params.get(name) if isinstance(params, dict) else None
    return int(value) if isinstance(value, int) else None


def _prompts_of(audit: Any) -> PromptsView | None:
    """The audit trail of one row, or None where none was kept."""
    if not isinstance(audit, dict) or not audit:
        return None
    return PromptsView(
        responder_system=str(audit.get("responder_system") or ""),
        responder_prompt=str(audit.get("responder_prompt") or ""),
        context=str(audit.get("context") or ""),
        judge_system=str(audit.get("judge_system") or ""),
        judge_prompt=str(audit.get("judge_prompt") or ""),
        judge_raw=str(audit.get("judge_raw") or ""),
        judged_without_model=bool(audit.get("judged_without_model")),
    )


def _fragments_of(result: Result) -> list[FragmentView] | None:
    """What the endpoint found for this row, or None where nothing was asked.

    None rather than an empty list: in closed book "0 fragments" would read as
    a retrieval that came back empty, which is a different fact.
    """
    rows = result.retrieved if isinstance(result.retrieved, list) else []
    if not rows and result.retrieval_hit is None:
        return None
    return [
        FragmentView(
            file_name=str(doc.get("file_name") or ""),
            score=float(doc.get("score") or 0.0),
            content=str(doc.get("content") or ""),
        )
        for doc in rows
        if isinstance(doc, dict)
    ]


def _view(
    result: Result,
    run: Run,
    pair: QaPair | None,
    *,
    is_latest: bool,
    prompts: bool = False,
) -> ResultView:
    """One row as a view; read while its session is open."""
    return ResultView(
        id=result.id,
        qa_id=result.qa_id,
        question=pair.question if pair else "",
        answer=result.answer,
        generator=pair.generator if pair else "",
        verdict=result.verdict,
        reasoning=result.reasoning,
        judge_model=result.judge_model,
        context_mode=run.context_mode,
        block=run.block,
        model=run.model,
        created_at=result.created_at,
        is_latest=is_latest,
        denial=_denial_of(result.extra),
        repeats=_repeats_of(result.extra),
        retrieval_hit=result.retrieval_hit,
        retrieval_rank=result.retrieval_rank,
        call=_call_of(result.audit),
        citations=citations_of(result.audit),
        web_search_unused=_unused_search(result.audit),
        behavior=behavior_of(result.extra),
        text_metrics=_text_metrics_of(result.extra),
        context_docs=_params_int(run.params, "context_docs"),
        fragment_max_chars=_params_int(run.params, "fragment_max_chars"),
        prompts=_prompts_of(result.audit) if prompts else None,
        fragments=_fragments_of(result) if prompts else None,
    )


def get_result(
    result_id: str, *, target_key: str | None = None, settings: Settings | None = None
) -> ResultView | None:
    """One result's full detail, or None if there is no such result.

    Args:
        result_id: The result to read
        target_key: If given, a result belonging to a different target counts
            as not found
        settings: The process settings
    """
    conf = settings or get_settings()
    with session_scope(conf) as session:
        query = (
            select(Result, Run)
            .join(Run, Run.id == Result.run_id)
            .where(Result.id == result_id)
        )
        if target_key is not None:
            query = query.where(Result.space == target_key)
        row = session.execute(query).first()
        if row is None:
            return None
        result, run = row

        pair = session.get(QaPair, result.qa_id)
        same_answer = (
            Result.space == result.space,
            Result.qa_id == result.qa_id,
            Run.context_mode == run.context_mode,
            Run.context_source == run.context_source,
            Run.block == run.block,
            Run.model == run.model,
        )

        def freshest(judge_model: str) -> str | None:
            return session.execute(
                select(Result.id)
                .join(Run, Run.id == Result.run_id)
                .where(*same_answer, Result.judge_model == judge_model)
                .order_by(Result.created_at.desc())
                .limit(1)
            ).scalar_one_or_none()

        stands = freshest(OWNER_OVERRIDE) or freshest(result.judge_model)
        return _view(result, run, pair, is_latest=stands == result.id)


def list_results(
    target_key: str,
    *,
    verdict: str | None = None,
    qa_id: str | None = None,
    model: str | None = None,
    job: str | None = None,
    limit: int = 50,
    offset: int = 0,
    prompts: bool = False,
    settings: Settings | None = None,
) -> tuple[list[ResultView], int]:
    """This target's results in the question order.

    Args:
        target_key: The node under test
        verdict: Only results with this verdict; None — every verdict
        qa_id: Only results for this pair; None — every pair
        model: Only this model's answers; None — every model
        job: Only what this launch asked; None — everything the node has
        limit: Page size, capped at ``MAX_PAGE``
        offset: How many to skip, for paging
        prompts: Also return the audit trail and the chunks found. Meant for
            one question at a time (``qa_id``): the prompts and replies are
            kept whole (only ``context`` is cut at ``audit_max_chars``), so a
            page of it is a download
        settings: The process settings

    Returns:
        The page of results, and the total count the filters match
    """
    conf = settings or get_settings()
    page = max(1, min(limit, MAX_PAGE))

    with session_scope(conf) as session:
        base = (
            select(Result, Run)
            .join(Run, Run.id == Result.run_id)
            .where(Result.space == target_key)
        )
        if verdict:
            base = base.where(Result.verdict == verdict)
        if qa_id:
            base = base.where(Result.qa_id == qa_id)
        if model:
            base = base.where(Run.model == model)
        if job:
            base = base.where(Run.job_id == job)

        total = session.execute(
            select(func.count()).select_from(base.subquery())
        ).scalar_one()

        # The question order of the report API; a result whose pair is gone
        # sorts last.
        ordered = base.outerjoin(QaPair, QaPair.id == Result.qa_id).order_by(
            *pair_order(QaPair.generator, QaPair.created_at, Result.qa_id),
            *answer_order(
                Run.context_mode,
                Run.block,
                Run.model,
                Result.judge_model,
                Result.created_at,
                Result.id,
            ),
        )
        rows = session.execute(ordered.limit(page).offset(offset)).all()
        if not rows:
            return [], total

        on_page = {result.qa_id for result, _ in rows}
        pairs = {
            pair.id: pair
            for pair in session.execute(
                select(QaPair).where(QaPair.id.in_(on_page))
            ).scalars()
        }

        # The freshest row per answer and judge over the whole history of the
        # page's questions, so ``is_latest`` holds on every page. The judge is
        # part of the key: a second judge's verdict replaces nothing of the
        # first's.
        freshest: dict[tuple[str, ...], str] = {}
        overridden: dict[tuple[str, ...], str] = {}
        history = session.execute(
            select(
                Result.id,
                Result.qa_id,
                Result.judge_model,
                Run.context_mode,
                Run.context_source,
                Run.block,
                Run.model,
            )
            .join(Run, Run.id == Result.run_id)
            .where(Result.space == target_key, Result.qa_id.in_(on_page))
            .order_by(Result.created_at)
        ).all()
        for row in history:
            answer = (
                row.context_mode,
                row.context_source,
                row.block,
                row.model,
                row.qa_id,
            )
            freshest[(*answer, row.judge_model)] = row.id
            if row.judge_model == OWNER_OVERRIDE:
                overridden[answer] = row.id

        views = []
        for result, run in rows:
            answer = (
                run.context_mode,
                run.context_source,
                run.block,
                run.model,
                result.qa_id,
            )
            stands = overridden.get(answer) or freshest.get(
                (*answer, result.judge_model)
            )
            views.append(
                _view(
                    result,
                    run,
                    pairs.get(result.qa_id),
                    is_latest=stands == result.id,
                    prompts=prompts,
                )
            )
    return views, total
