"""Console routes under a session token, scoped to its one target: the probe
layer, generated pairs, verdicts and launching.

Run reports live in ``report_routes``.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query, status

from syft_benchmark.config import JobKind, Settings
from syft_benchmark.control import jobs as job_queue
from syft_benchmark.control import targets as registry
from syft_benchmark.control.auth import ConsoleAuth, ConsoleGuard
from syft_benchmark.control.compose import (
    effective_defaults,
    target_panel,
)
from syft_benchmark.control.formfields import catalogue
from syft_benchmark.control.refusals import (
    job_or_404,
    refuse_run_clash,
    require_enabled,
    target_or_404,
)
from syft_benchmark.control.schemas import (
    FilterRequest,
    JobView,
    JudgeRequest,
    PairPage,
    PairResponse,
    PairStatusUpdate,
    Probe,
    ResultPage,
    ResultResponse,
    RunRequest,
    VerdictOverride,
)
from syft_benchmark.db.session import session_scope
from syft_benchmark.generation import delete_pair, get_pair, list_pairs, override_status
from syft_benchmark.report import run_questions
from syft_benchmark.runs import (
    get_result,
    list_results,
    override_verdict,
    withdraw_override,
)
from syft_benchmark.runs.result_views import ResultView

router = APIRouter(prefix="/console")


def _probe_payload(probe: Probe, conf: Settings) -> dict[str, Any]:
    """The target's own probe layer, its fields, and what an unset one resolves to."""
    return {
        "probe": probe.overrides(),
        "inherited": effective_defaults(conf)["probe"],
        "fields": catalogue()["probe"],
    }


@router.get("/probe")
def console_get_probe(auth: ConsoleGuard) -> dict[str, Any]:
    """This target's own probe layer.

    The instrument is not here: it is shared by every target of one connection,
    and one endpoint's session must not change what makes them comparable.
    """
    with session_scope(auth.settings) as session:
        probe = registry.view(target_or_404(session, auth.target_key)).probe
    return _probe_payload(probe, auth.settings)


@router.put("/probe")
def console_save_probe(body: Probe, auth: ConsoleGuard) -> dict[str, Any]:
    with session_scope(auth.settings) as session:
        row = registry.update_probe(session, auth.target_key, body)
        if row is None:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND, f"there is no target {auth.target_key}"
            )
        probe = registry.view(row).probe
    return _probe_payload(probe, auth.settings)


@router.get("/pairs", response_model=PairPage)
def console_list_pairs(
    auth: ConsoleGuard,
    status_value: Annotated[str | None, Query(alias="status")] = None,
    cohort: str | None = None,
    generator: str | None = None,
    job: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> PairPage:
    items, total = list_pairs(
        auth.target_key,
        status=status_value,
        cohort=cohort,
        generator=generator,
        job=job,
        limit=limit,
        offset=offset,
        settings=auth.settings,
    )
    return PairPage(items=[PairResponse.model_validate(v) for v in items], total=total)


@router.patch("/pairs/{pair_id}", response_model=PairResponse)
def console_update_pair(
    pair_id: str, body: PairStatusUpdate, auth: ConsoleGuard
) -> PairResponse:
    """Override one pair's status by hand, whatever its status is now."""
    changed = override_status(
        pair_id,
        body.status,
        note=body.note,
        target_key=auth.target_key,
        settings=auth.settings,
    )
    if not changed:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"there is no pair {pair_id}")
    view = get_pair(pair_id, target_key=auth.target_key, settings=auth.settings)
    assert view is not None  # just written, under the same target
    return PairResponse.model_validate(view)


@router.delete("/pairs/{pair_id}", status_code=status.HTTP_204_NO_CONTENT)
def console_delete_pair(pair_id: str, auth: ConsoleGuard) -> None:
    """Remove a pair outright — only when nothing has measured it yet."""
    outcome = delete_pair(pair_id, target_key=auth.target_key, settings=auth.settings)
    if outcome == "not_found":
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"there is no pair {pair_id}")
    if outcome == "has_results":
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "this pair already has results — change its status instead "
            "of deleting it, or its measurement history would go with it",
        )


@router.get("/results", response_model=ResultPage)
def console_list_results(
    auth: ConsoleGuard,
    verdict: str | None = None,
    qa_id: str | None = None,
    model: str | None = None,
    job: str | None = None,
    limit: int = 50,
    offset: int = 0,
    prompts: bool = False,
) -> ResultPage:
    """This target's verdicts, filterable and paged.

    ``prompts`` adds the audit trail and the chunks found: whole prompts and
    replies, with the arm C context cut at ``audit_max_chars``, so ask for it
    with ``qa_id``. With ``job``, each row says whether that job's figures
    count it.
    """
    items, total = list_results(
        auth.target_key,
        verdict=verdict,
        qa_id=qa_id,
        model=model,
        job=job,
        limit=limit,
        offset=offset,
        prompts=prompts,
        settings=auth.settings,
    )
    if job and items:
        _mark_counted(auth, job, items)
    return ResultPage(
        items=[ResultResponse.model_validate(v) for v in items], total=total
    )


def _mark_counted(auth: ConsoleAuth, job_id: str, items: list[ResultView]) -> None:
    """Set ``counted`` on each row: whether the job's figures count it."""
    with session_scope(auth.settings) as session:
        job = job_or_404(session, auth.target_key, job_id)
        target = target_or_404(session, auth.target_key)
        counted = run_questions.counted_ids(
            session,
            job,
            {item.qa_id for item in items},
            configured=lambda: target_panel(target, auth.settings),
        )
    for item in items:
        item.counted = item.id in counted


@router.post("/results/{result_id}/verdict", response_model=ResultResponse)
def console_override_verdict(
    result_id: str, body: VerdictOverride, auth: ConsoleGuard
) -> ResultResponse:
    """Record a verdict by hand — inserted, never a rewrite of the original."""
    new_id = override_verdict(
        result_id,
        body.verdict,
        reasoning=body.reasoning,
        owner="console",
        target_key=auth.target_key,
        settings=auth.settings,
    )
    if new_id is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, f"there is no result {result_id}"
        )
    overridden = get_result(new_id, target_key=auth.target_key, settings=auth.settings)
    assert overridden is not None  # just written, under the same target
    return ResultResponse.model_validate(overridden)


@router.delete("/results/{result_id}/verdict", status_code=204)
def console_withdraw_verdict(result_id: str, auth: ConsoleGuard) -> None:
    """Take back a verdict recorded by hand — the panel's stands again."""
    if not withdraw_override(
        result_id, target_key=auth.target_key, settings=auth.settings
    ):
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            f"there is no hand-recorded verdict {result_id}",
        )


@router.post("/runs", response_model=JobView, status_code=202)
def console_start_run(request: RunRequest, auth: ConsoleGuard) -> JobView:
    """Preparation and Testing both launch here, with different ``RunRequest`` flags."""
    with session_scope(auth.settings) as session:
        row = target_or_404(session, auth.target_key)
        require_enabled(row)
        refuse_run_clash(row, request, auth.settings)
        job = job_queue.enqueue(session, row, request)
        return JobView.model_validate(job)


@router.post("/filter", response_model=JobView, status_code=202)
def console_start_filter(request: FilterRequest, auth: ConsoleGuard) -> JobView:
    with session_scope(auth.settings) as session:
        row = target_or_404(session, auth.target_key)
        require_enabled(row)
        job = job_queue.enqueue(session, row, request, kind=JobKind.FILTER)
        return JobView.model_validate(job)


@router.post("/judge", response_model=JobView, status_code=202)
def console_start_judge(request: JudgeRequest, auth: ConsoleGuard) -> JobView:
    with session_scope(auth.settings) as session:
        row = target_or_404(session, auth.target_key)
        require_enabled(row)
        job = job_queue.enqueue(session, row, request, kind=JobKind.JUDGE)
        return JobView.model_validate(job)


@router.get("/jobs", response_model=list[JobView])
def console_jobs(auth: ConsoleGuard) -> list[JobView]:
    with session_scope(auth.settings) as session:
        return [
            JobView.model_validate(row)
            for row in job_queue.recent_jobs(session, auth.target_key)
        ]
