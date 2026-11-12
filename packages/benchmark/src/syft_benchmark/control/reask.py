"""Re-asks: the questions finished runs asked, asked again the same way.

A re-ask (a job of kind ``reask``) takes finished, measured pipeline runs of
one target with one ``settings_hash`` (a combined run stands for its runs) and
asks every (question, model, arm, block) they answered again — or those of
some arms and models: the same subjects, judges and settings, read from the
runs' snapshot rather than the target's current settings. Nothing is built,
screened or resumed; a question retired since is asked all the same; answers
are never reused from another job. The re-ask keeps the runs' hash, so it
combines with them and ``repeats`` compares the answers.
"""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from syft_benchmark.config import JobKind, Settings
from syft_benchmark.control import combined
from syft_benchmark.db.models import Job, Result, Run
from syft_benchmark.llm import cost, subject_providers
from syft_benchmark.report import job_params
from syft_benchmark.report.run_view import ARM_OF
from syft_benchmark.runs.judge_stage import OWNER_OVERRIDE

# A pass: (arm, block, model).
PassKey = tuple[str, str, str]
PRIMARY = "primary"
ALL = "all"


class Refused(ValueError):
    """The runs cannot be re-asked; ``differences`` names the settings that
    keep them apart, when that is the reason."""

    def __init__(
        self, detail: str, differences: list[dict[str, Any]] | None = None
    ) -> None:
        super().__init__(detail)
        self.detail = detail
        self.differences = differences

    def body(self) -> dict[str, Any]:
        """The 422 body: ``{detail}``, plus ``differences`` when known."""
        if self.differences is None:
            return {"detail": self.detail}
        return {"detail": self.detail, "differences": self.differences}


@dataclass(frozen=True, slots=True)
class Scope:
    """What of the runs a re-ask takes: arms and models (None — every one)
    and the judges, ``all`` or ``primary``."""

    arms: tuple[str, ...] | None = None
    models: tuple[str, ...] | None = None
    judges: str = ALL

    @classmethod
    def of(cls, values: dict[str, Any]) -> Scope:
        """From a ``ReaskRequest``'s JSON dump or the job's ``params.reask``."""
        arms, models = values.get("arms"), values.get("models")
        return cls(
            arms=tuple(arms) if arms else None,
            models=tuple(models) if models else None,
            judges=str(values.get("judges") or ALL),
        )

    @property
    def primary_only(self) -> bool:
        return self.judges == PRIMARY

    def takes(self, key: PassKey) -> bool:
        mode, _, model = key
        return (self.arms is None or mode in self.arms) and (
            self.models is None or model in self.models
        )


@dataclass(frozen=True, slots=True)
class Plan:
    """What a re-ask asks, and how."""

    # The leaf runs, oldest first.
    sources: list[str]
    # The runs' settings snapshot and its hash.
    snapshot: dict[str, Any]
    settings_hash: str
    scope: Scope
    # (arm, block, model) -> the questions the runs answered in that pass.
    passes: dict[PassKey, frozenset[str]]
    # USD from the runs' spend per answer; None — a run kept no cost.
    estimated_usd: float | None

    @property
    def questions(self) -> int:
        return len(frozenset().union(*self.passes.values()))

    @property
    def answers_planned(self) -> int:
        return sum(len(ids) for ids in self.passes.values())

    def estimate(self, max_job_usd: float) -> dict[str, Any]:
        """The dry run's answer."""
        return {
            "questions": self.questions,
            "answers_planned": self.answers_planned,
            "estimated_usd": self.estimated_usd,
            "max_job_usd": max_job_usd,
        }

    def params(self, label: str | None) -> dict[str, Any]:
        """The job's ``params.reask``."""
        return {
            "jobs": self.sources,
            "label": label,
            "questions": self.questions,
            "answers_planned": self.answers_planned,
            "estimated_usd": self.estimated_usd,
            "arms": list(self.scope.arms) if self.scope.arms else None,
            "models": list(self.scope.models) if self.scope.models else None,
            "judges": self.scope.judges,
        }


def plan(session: Session, target: str, job_ids: Sequence[str], scope: Scope) -> Plan:
    """What re-asking ``job_ids`` of ``target`` within ``scope`` asks.

    Raises:
        Refused: an id is not a run of the target, not a measurement run,
            not finished or measured, has no settings snapshot, the runs
            differ in their hash, the scope names an arm or model the runs
            did not ask, or nothing is left to ask
    """
    try:
        jobs = combined.leaves(session, target, job_ids)
    except combined.UnknownJob as exc:
        raise Refused(f"job {exc.job_id} is not a run of target {target}") from exc
    for job in jobs:
        if (job.kind or JobKind.PIPELINE.value) != JobKind.PIPELINE.value:
            raise Refused(
                f"job {job.id} is a {job.kind} job; only measurement runs are re-asked"
            )
        params = job.params or {}
        if not params.get(job_params.SETTINGS_HASH) or not isinstance(
            params.get(job_params.SETTINGS_SNAPSHOT), dict
        ):
            raise Refused(f"job {job.id} kept no settings snapshot to re-ask it by")
    found = combined.differences(session, jobs)
    if found:
        raise Refused(
            "the runs must be finished, measured and measured the same way", found
        )
    asked = _Asked.of(session, [job.id for job in jobs])
    unknown = sorted(
        {*(scope.arms or ()), *(scope.models or ())}
        - {part for key in asked.passes for part in (key[0], key[2])}
    )
    if unknown:
        raise Refused(f"the runs asked nothing of {', '.join(unknown)}")
    passes = {key: ids for key, ids in asked.passes.items() if scope.takes(key)}
    if not passes:
        raise Refused("the runs asked no questions")
    first = jobs[0].params or {}
    planned = sum(len(ids) for ids in passes.values())
    return Plan(
        sources=[job.id for job in jobs],
        snapshot=dict(first[job_params.SETTINGS_SNAPSHOT]),
        settings_hash=str(first[job_params.SETTINGS_HASH]),
        scope=scope,
        passes=passes,
        estimated_usd=asked.estimate(jobs, planned, primary_only=scope.primary_only),
    )


@dataclass(slots=True)
class _Asked:
    """The runs' answers in the measured arms: per pass, the questions;
    how many answers and how many verdicts."""

    passes: dict[PassKey, frozenset[str]]
    answers: int
    verdicts: int

    @classmethod
    def of(cls, session: Session, job_ids: list[str]) -> _Asked:
        passes: dict[PassKey, set[str]] = defaultdict(set)
        answers: set[tuple[str, str, str, str, str]] = set()
        verdicts = 0
        for job_id, mode, block, model, qa_id in session.execute(
            select(Run.job_id, Run.context_mode, Run.block, Run.model, Result.qa_id)
            .join(Result, Result.run_id == Run.id)
            .where(
                Run.job_id.in_(job_ids),
                Run.context_mode.in_(list(ARM_OF)),
                Run.judge_model != OWNER_OVERRIDE,
            )
        ):
            passes[(mode, block, model or "")].add(qa_id)
            answers.add((job_id, mode, block, model or "", qa_id))
            verdicts += 1
        return cls(
            passes={key: frozenset(ids) for key, ids in passes.items()},
            answers=len(answers),
            verdicts=verdicts,
        )

    def estimate(
        self, jobs: Sequence[Job], planned: int, *, primary_only: bool
    ) -> float | None:
        """USD for ``planned`` answers at the runs' spend on the tested models
        per answer and on the judges per answer — per verdict with one judge."""
        spent = {cost.SUBJECTS: 0.0, cost.JUDGES: 0.0}
        for job in jobs:
            recorded = (job.params or {}).get(job_params.COST)
            by_role = recorded.get("by_role") if isinstance(recorded, dict) else None
            if not isinstance(by_role, dict):
                return None
            for role in spent:
                spent[role] += float(by_role.get(role) or 0.0)
        if not self.answers:
            return None
        judged = self.verdicts if primary_only else self.answers
        usd = planned * (
            spent[cost.SUBJECTS] / self.answers + spent[cost.JUDGES] / max(judged, 1)
        )
        return round(usd, 4)


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def settings_of(node_conf: Settings, found: Plan) -> tuple[Settings, dict[str, Any]]:
    """The target's settings with the runs' methodology laid over them, and
    the snapshot the re-ask keeps.

    Fields left out of the hash (spending cap, concurrency, reuse within the
    launch) stay the target's; nothing is resumed. A field the runs' snapshot
    lacks (added since) must hold its default and stays out of the kept
    snapshot, so the re-ask's hash is the runs'.

    Raises:
        Refused: a setting cannot be what it was for the runs, or a model
            the runs asked is not a tested model under it
    """
    kind = type(node_conf)
    method = {
        key: value
        for key, value in found.snapshot.items()
        if key not in job_params.HASH_EXCLUDED and key in kind.model_fields
    }
    try:
        conf = kind(**{**node_conf.model_dump(), **method, "resume": False})
    except ValidationError as exc:
        raise Refused(f"the runs' settings no longer validate: {exc}") from exc
    snapshot = job_params.settings_snapshot(conf)
    defaults = job_params.settings_snapshot(kind.model_construct())
    differences = []
    for key in sorted((set(found.snapshot) | set(snapshot)) - job_params.HASH_EXCLUDED):
        was = found.snapshot.get(key, defaults.get(key))
        if _canonical(snapshot.get(key)) != _canonical(was):
            differences.append(
                {
                    "field": key,
                    "runs": found.snapshot.get(key),
                    "reask": snapshot.get(key),
                }
            )
    if differences:
        raise Refused(
            "these settings cannot be what they were for the runs", differences
        )
    kept = {
        key: value
        for key, value in snapshot.items()
        if key in found.snapshot or key in job_params.HASH_EXCLUDED
    }
    if job_params.settings_hash(kept) != found.settings_hash:
        raise Refused("the runs' settings hash cannot be reproduced")
    subjects = {provider.model for provider in subject_providers(conf)}
    missing = sorted({model for _, _, model in found.passes} - subjects)
    if missing:
        raise Refused(
            f"not a tested model under the runs' settings: {', '.join(missing)}"
        )
    return conf, kept


def check(
    session: Session,
    target: str,
    job_ids: Sequence[str],
    scope: Scope,
    node_conf: Settings,
    *,
    dry_run: bool = False,
) -> Plan:
    """``plan`` and ``settings_of`` together: the plan of a re-ask that can
    run. Unless ``dry_run``, its estimate must be within ``max_job_usd``.

    Raises:
        Refused: as ``plan`` and ``settings_of``, or over the cap
    """
    found = plan(session, target, job_ids, scope)
    conf, _ = settings_of(node_conf, found)
    cap = conf.max_job_usd
    if (
        not dry_run
        and cap > 0
        and found.estimated_usd is not None
        and found.estimated_usd > cap
    ):
        raise Refused(
            f"estimated ${found.estimated_usd:.2f}, over the job cap of ${cap:g}: "
            f"re-ask fewer arms, models or runs, judge with the primary judge "
            f"only, or raise max_job_usd"
        )
    return found
