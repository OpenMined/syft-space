"""The schedule the service runs itself, and reading one measurement back.

The service decides when to measure, and a measurement is findable afterwards —
a launch, its verdicts and its raw records, as against the node's numbers as of
today. Within a measurement, a model name the provider refused is not asked
again in the passes still to come.

The schedule half is checked mostly without a database: what to fire and when is
a function of a target and a moment, and it is worth being able to say so. The
scoping half cannot be: it is a question about what a query selects, and a
stubbed session would check a conspiracy of stubs.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import select

from syft_benchmark.config import ContextMode, EvalBlock, Settings
from syft_benchmark.control import targets as registry
from syft_benchmark.control.schemas import TargetSpec
from syft_benchmark.control.ticker import SCHEDULE, plan, tick
from syft_benchmark.db.models import Job, QaPair, Result, Run, Target
from syft_benchmark.db.session import session_scope
from syft_benchmark.report.audit import audit_records
from syft_benchmark.report.metrics import summarize
from syft_benchmark.scheduler import next_fire, parse_interval

KEY = "pytest-schedule"
SPACE = "pytest-scope"
NIGHT = datetime(2026, 9, 17, 1, 0, tzinfo=UTC)


def _target(**kw: Any) -> Target:
    fields: dict[str, Any] = {
        "key": KEY,
        "url": "http://space.invalid",
        "endpoint": "kb",
        "enabled": True,
        "schedule": "",
        "schedule_at": "",
        "next_run_at": None,
    }
    fields.update(kw)
    return Target(**fields)


# --- what to fire and when -------------------------------------------------


def test_a_daily_schedule_lands_on_the_hour_it_was_given() -> None:
    """The point of the hour is that the measurement lands at night, not at the
    moment the owner happened to press save."""
    moment = plan(_target(schedule="24h", schedule_at="03:00"), now=NIGHT)
    assert moment == datetime(2026, 9, 17, 3, 0, tzinfo=UTC)


def test_the_hour_is_utc_and_not_the_clock_of_whoever_is_watching() -> None:
    """A container has no idea what the owner's night is.

    The moment handed back is timezone-aware, so nothing downstream can quietly
    compare it against a naive local clock and be a few hours out.
    """
    moment = plan(_target(schedule="24h", schedule_at="03:00"), now=NIGHT)
    assert moment is not None
    assert moment.tzinfo is not None
    assert moment.utcoffset() == timedelta(0)


def test_an_hour_already_past_moves_to_tomorrow() -> None:
    """Otherwise a schedule saved in the afternoon would fire the same second."""
    noon = datetime(2026, 9, 17, 12, 0, tzinfo=UTC)
    assert plan(_target(schedule="24h", schedule_at="03:00"), now=noon) == datetime(
        2026, 9, 18, 3, 0, tzinfo=UTC
    )


def test_a_short_interval_counts_from_now_and_ignores_the_hour() -> None:
    """An hour of the day means nothing to a schedule that fires several times
    within one."""
    assert plan(_target(schedule="6h", schedule_at="03:00"), now=NIGHT) == NIGHT + (
        timedelta(hours=6)
    )


def test_a_disabled_target_is_not_scheduled() -> None:
    """Pausing a measurement has to pause it. The schedule itself is kept: the
    owner switches it back on, they do not fill the form in again."""
    assert plan(_target(schedule="24h", enabled=False), now=NIGHT) is None


def test_an_unreadable_schedule_does_not_bring_the_thread_down() -> None:
    """A field the owner typed into is a field somebody will mistype. The target
    goes unscheduled and says so in the log — the rest keep their schedules."""
    assert plan(_target(schedule="every night"), now=NIGHT) is None
    assert plan(_target(schedule="24h", schedule_at="25:00"), now=NIGHT) is None
    assert plan(_target(schedule="0h"), now=NIGHT) is None


# --- the interval and the next fire of the scheduler -----------------------


@pytest.mark.parametrize(
    ("text", "seconds"),
    [("24h", 86400.0), ("90m", 5400.0), ("30s", 30.0), ("2d", 172800.0)],
)
def test_interval_parsing(text: str, seconds: float) -> None:
    assert parse_interval(text) == seconds


def test_empty_interval_is_rejected() -> None:
    with pytest.raises(ValueError, match="empty interval"):
        parse_interval("")


def test_daily_step_lands_on_the_wall_clock_time() -> None:
    """The cycle should land at night, not at the moment of the first launch."""
    now = datetime(2026, 9, 9, 14, 30)
    assert next_fire(86400, "03:00", now=now) == datetime(2026, 9, 10, 3, 0)


def test_daily_step_today_when_the_hour_is_still_ahead() -> None:
    now = datetime(2026, 9, 9, 1, 15)
    assert next_fire(86400, "03:00", now=now) == datetime(2026, 9, 9, 3, 0)


def test_sub_daily_interval_ignores_the_wall_clock() -> None:
    now = datetime(2026, 9, 9, 14, 30)
    assert next_fire(3600, "03:00", now=now) == datetime(2026, 9, 9, 15, 30)


# --- the ticker over a live table ------------------------------------------


def _queued(session: Any) -> list[Job]:
    """Every job standing against the test target, in the order they were made."""
    return list(
        session.scalars(select(Job).where(Job.target == KEY).order_by(Job.created_at))
    )


@pytest.mark.needs_db
def test_a_schedule_seen_for_the_first_time_plans_and_does_not_measure(
    clean: Any,
) -> None:
    """Saving a form must not answer with hours of paid work.

    "Every 24h at 03:00" means tonight. A first pass that fired at once would
    measure at the moment of the save and then again tonight.
    """
    with session_scope() as session:
        session.add(_target(schedule="24h", schedule_at="03:00"))

    with session_scope() as session:
        assert tick(session, now=NIGHT) == []
        target = session.get(Target, KEY)
        assert target is not None
        assert target.next_run_at == datetime(2026, 9, 17, 3, 0, tzinfo=UTC)
        assert _queued(session) == []


@pytest.mark.needs_db
def test_the_moment_arrives_and_the_measurement_is_queued(clean: Any) -> None:
    """And the plan moves forward at once, so the next tick does not fire again."""
    with session_scope() as session:
        session.add(
            _target(
                schedule="24h",
                schedule_at="03:00",
                next_run_at=datetime(2026, 9, 17, 3, 0, tzinfo=UTC),
            )
        )

    after = datetime(2026, 9, 17, 3, 0, 30, tzinfo=UTC)
    with session_scope() as session:
        assert tick(session, now=after) == [KEY]
        jobs = _queued(session)
        assert len(jobs) == 1
        assert jobs[0].trigger == SCHEDULE
        target = session.get(Target, KEY)
        assert target is not None
        assert target.next_run_at == datetime(2026, 9, 18, 3, 0, tzinfo=UTC)

    # The very next tick, a second later, must not queue a second measurement.
    with session_scope() as session:
        assert tick(session, now=after + timedelta(seconds=1)) == []
        assert len(_queued(session)) == 1


@pytest.mark.needs_db
def test_three_nights_slept_through_are_one_measurement_overdue(clean: Any) -> None:
    """A service that was down does not owe a run for every window it missed.

    Working them off would mean a container coming back from a week's outage
    spending a week's budget on seven measurements of the same corpus, of which
    only the last would be about today.
    """
    with session_scope() as session:
        session.add(
            _target(
                schedule="24h",
                schedule_at="03:00",
                next_run_at=datetime(2026, 9, 14, 3, 0, tzinfo=UTC),
            )
        )

    back_up = datetime(2026, 9, 17, 9, 0, tzinfo=UTC)
    with session_scope() as session:
        assert tick(session, now=back_up) == [KEY]
        assert len(_queued(session)) == 1
        target = session.get(Target, KEY)
        assert target is not None
        assert target.next_run_at == datetime(2026, 9, 18, 3, 0, tzinfo=UTC)


@pytest.mark.needs_db
def test_a_measurement_still_running_is_not_overtaken_by_its_own_schedule(
    clean: Any,
) -> None:
    """A node answering under double load is not the node that answered
    yesterday, and the numbers would diverge for a reason of their own."""
    with session_scope() as session:
        session.add(
            _target(
                schedule="1h",
                next_run_at=datetime(2026, 9, 17, 1, 0, tzinfo=UTC),
            )
        )
        session.add(
            Job(
                id="pytest-running",
                target=KEY,
                state="running",
                phase="evaluate",
                trigger="manual",
                params={},
            )
        )

    with session_scope() as session:
        tick(session, now=datetime(2026, 9, 17, 1, 0, 30, tzinfo=UTC))
        jobs = _queued(session)
        assert len(jobs) == 1
        assert jobs[0].id == "pytest-running"


@pytest.mark.needs_db
def test_a_schedule_taken_off_leaves_no_plan_behind(clean: Any) -> None:
    """Otherwise switching it back on a month later would fire against a moment
    long past — a measurement nobody asked for, at the moment of the save."""
    with session_scope() as session:
        session.add(_target(schedule="", next_run_at=datetime(2026, 9, 1, tzinfo=UTC)))

    with session_scope() as session:
        assert tick(session, now=NIGHT) == []
        target = session.get(Target, KEY)
        assert target is not None
        assert target.next_run_at is None


def test_changing_the_schedule_replans_it() -> None:
    """A measurement switched from nightly to hourly must not stay nightly until
    the night it was already waiting for."""
    row = Target(
        key=KEY,
        url="http://space.invalid",
        schedule="24h",
        schedule_at="03:00",
        next_run_at=datetime(2026, 9, 17, 3, 0, tzinfo=UTC),
    )
    registry._row(TargetSpec(key=KEY, url="http://space.invalid", schedule="6h"), row)
    assert row.next_run_at is None


def test_saving_a_target_without_touching_the_schedule_keeps_the_plan() -> None:
    """Renaming a target is not a reason to postpone its measurement."""
    planned = datetime(2026, 9, 17, 3, 0, tzinfo=UTC)
    row = Target(
        key=KEY,
        url="http://space.invalid",
        schedule="24h",
        schedule_at="03:00",
        next_run_at=planned,
    )
    registry._row(
        TargetSpec(
            key=KEY,
            url="http://space.invalid",
            title="A new name",
            schedule="24h",
            schedule_at="03:00",
        ),
        row,
    )
    assert row.next_run_at == planned


# --- reading one measurement back ------------------------------------------


def _pair(pair_id: str, status: str = "active") -> QaPair:
    return QaPair(
        id=pair_id,
        space=SPACE,
        collection="kb",
        cohort="c1",
        generator="factual",
        doc_id="doc1",
        chunk_id="chunk1",
        question=f"Question {pair_id}?",
        answer="An answer.",
        expected_behavior="answer",
        status=status,
        model="generator-model",
        question_hash=pair_id,
        created_at=datetime(2026, 8, 1, tzinfo=UTC),
    )


def _seed_run(run_id: str, job_id: str | None, at: datetime) -> Run:
    return Run(
        id=run_id,
        space=SPACE,
        endpoint="kb",
        job_id=job_id,
        context_mode=ContextMode.MODEL_WITH_CONTEXT.value,
        context_source="endpoint_own",
        profile="default",
        params={},
        block=EvalBlock.DIRECT.value,
        model="endpoint",
        model_vendor="",
        judge_model="judge-1",
        started_at=at,
    )


def _seed_result(
    result_id: str, run_id: str, pair_id: str, verdict: str, at: datetime
) -> Result:
    return Result(
        id=result_id,
        run_id=run_id,
        qa_id=pair_id,
        space=SPACE,
        endpoint="kb",
        endpoint_response_type="both",
        answer="An answer.",
        verdict=verdict,
        reasoning="because",
        expected_behavior="answer",
        extra={},
        audit={},
        model="endpoint",
        judge_model="judge-1",
        created_at=at,
    )


@pytest.fixture
def two_measurements(clean: Any) -> Any:
    """One node, two launches a month apart, opposite verdicts on one question.

    The second launch also answers a question the first never saw, and the first
    launch's question is afterwards taken out of the set — which is what makes
    "as of now" and "as it was" different numbers rather than the same one.
    """
    old = datetime(2026, 8, 17, 3, 0, tzinfo=UTC)
    new = datetime(2026, 9, 17, 3, 0, tzinfo=UTC)
    with session_scope() as session:
        session.add(_pair("qa-retired", status="rejected"))
        session.add(_pair("qa-kept"))
        session.add(_seed_run("run-old", "job-old", old))
        session.add(_seed_run("run-new", "job-new", new))
        session.add(_seed_result("res-old-1", "run-old", "qa-retired", "correct", old))
        session.add(_seed_result("res-old-2", "run-old", "qa-kept", "correct", old))
        session.add(_seed_result("res-new-1", "run-new", "qa-kept", "hallucinate", new))
    yield


@pytest.mark.needs_db
def test_a_launch_is_read_back_as_it_was(two_measurements: Any) -> None:
    """Two questions were asked in August and both were answered correctly.

    One of them has since been taken out of the set. Scoped to its launch the
    measurement still holds both: screening a question out afterwards does not
    unask it.
    """
    metrics = summarize(
        SPACE,
        ContextMode.MODEL_WITH_CONTEXT,
        EvalBlock.DIRECT,
        judge="judge-1",
        job="job-old",
    )
    assert metrics is not None
    assert metrics.graded == 2
    assert metrics.correct == 2


@pytest.mark.needs_db
def test_the_node_as_of_now_is_a_different_number(two_measurements: Any) -> None:
    """Unscoped, the September verdict wins and the retired question is gone.

    It is not the August one; the two being different is the whole reason a
    launch has to be nameable.
    """
    metrics = summarize(
        SPACE, ContextMode.MODEL_WITH_CONTEXT, EvalBlock.DIRECT, judge="judge-1"
    )
    assert metrics is not None
    assert metrics.graded == 1
    assert metrics.hallucinate == 1


@pytest.mark.needs_db
def test_the_audit_of_a_launch_holds_only_that_launch(two_measurements: Any) -> None:
    """Settings change between launches. An export that mixed two of them would
    lay answers obtained at different thresholds side by side under one heading.
    """
    records = list(audit_records(SPACE, job="job-new"))
    assert [r["qa_id"] for r in records] == ["qa-kept"]
    verdicts = [a["verdict"] for r in records for a in r["answers"]]
    assert verdicts == ["hallucinate"]


@pytest.mark.needs_db
def test_a_run_from_the_console_belongs_to_no_launch(clean: Any) -> None:
    """And is not swept into one. NULL here is a fact, not a gap to be filled."""
    at = datetime(2026, 9, 1, tzinfo=UTC)
    with session_scope() as session:
        session.add(_pair("qa-console"))
        session.add(_seed_run("run-console", None, at))
        session.add(
            _seed_result("res-console", "run-console", "qa-console", "correct", at)
        )

    assert (
        summarize(
            SPACE,
            ContextMode.MODEL_WITH_CONTEXT,
            EvalBlock.DIRECT,
            judge="judge-1",
            job="job-old",
        )
        is None
    )
    assert list(audit_records(SPACE, job="job-old")) == []
    assert len(list(audit_records(SPACE))) == 1


@pytest.mark.needs_db
def test_the_runs_a_launch_opens_carry_its_id(clean: Any) -> None:
    """The column is not decoration: this is the code path that writes it.

    Everything above selects by ``job_id``; without this the whole scoping
    would rest on rows the tests seeded themselves, and a launch that never
    filled the field in would pass every one of them.
    """
    from syft_benchmark.config import ContextSource, SpaceConfig
    from syft_benchmark.llm.roles import Provider
    from syft_benchmark.runs.execute import _open_runs

    space = SpaceConfig(key=SPACE, url="http://space.invalid", endpoint="kb")
    seat = Provider(role="judge", url="http://llm.invalid", api_key="", model="judge-1")
    subject = Provider(role="subject", url="http://llm.invalid", api_key="", model="m")

    _open_runs(
        space,
        ContextMode.MODEL_WITH_CONTEXT,
        block=EvalBlock.DIRECT,
        source=ContextSource.ENDPOINT_FRAGMENTS,
        responder="model",
        vendor="",
        seated=[seat],
        params={},
        settings=Settings(),
        subject=subject,
        job_id="job-opened",
    )

    with session_scope() as session:
        rows = list(session.scalars(select(Run).where(Run.space == SPACE)))
        assert [r.job_id for r in rows] == ["job-opened"]


def test_a_measurement_hands_its_launch_down_to_the_runs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``measure`` is several layers above the row being written.

    The id travels through ``run_pass`` to reach it, and a layer that dropped it
    on the way would leave every run unattached while the job looked fine.
    """
    from syft_benchmark import scheduler
    from syft_benchmark.config import SpaceConfig

    seen: list[str | None] = []

    class FakeProvider:
        def __init__(self, model: str) -> None:
            self.model = model

    monkeypatch.setattr(
        scheduler, "subject_providers", lambda conf: [FakeProvider("model-a")]
    )
    monkeypatch.setattr(
        scheduler, "judge_providers", lambda conf: [FakeProvider("judge-1")]
    )

    async def fake_run_pass(space: Any, mode: Any, **kwargs: Any) -> list[Any]:
        seen.append(kwargs.get("job_id"))
        return []

    monkeypatch.setattr(scheduler, "arun_pass", fake_run_pass)
    monkeypatch.setattr(scheduler, "summarize", lambda *a, **k: None)

    conf = Settings(
        arms=[ContextMode.CLOSED_BOOK],
        blocks=[EvalBlock.DIRECT],
        generate_in_cycle=False,
    )
    scheduler.measure(
        SpaceConfig(key=SPACE, url="http://space.invalid", endpoint="kb"),
        conf,
        job_id="job-handed-down",
    )

    assert seen == ["job-handed-down"]


# --- a refusal outlives the pass it happened in ----------------------------


def test_a_refused_name_is_not_asked_in_the_passes_still_to_come(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The whole point of noticing a refusal at all.

    A run stopped from within is followed by the next one, which is fresh; a
    refused model name is not paid for again in every pass. The models that were not
    refused go on being measured: a panel with one bad name in it is still a
    measurement of the other two.
    """
    from syft_benchmark import scheduler as sched
    from syft_benchmark.config import Settings, SpaceConfig
    from syft_benchmark.llm.roles import Provider
    from syft_benchmark.runs.execute import RunReport

    def _seat(role: str, model: str) -> Provider:
        return Provider(
            role=role, url="http://localhost:11434", api_key="", model=model
        )

    bad, good, judge = (
        _seat("subject", "bad/name"),
        _seat("subject", "good/one"),
        _seat("judge", "a/judge"),
    )
    monkeypatch.setattr(sched, "subject_providers", lambda conf: [bad, good])
    monkeypatch.setattr(sched, "judge_providers", lambda conf: [judge])
    monkeypatch.setattr(sched, "summarize", lambda *args, **kwargs: None)

    asked: list[str] = []

    async def one_pass(space, mode, **kwargs):  # type: ignore[no-untyped-def]
        subject = kwargs["subject"]
        asked.append(subject.model)
        return [
            RunReport(
                run_id="r",
                context_mode=mode,
                block=kwargs["block"],
                model=subject.model,
                judge=judge.model,
                asked=1,
                refused=subject.model if subject is bad else "",
            )
        ]

    monkeypatch.setattr(sched, "arun_pass", one_pass)

    conf = Settings(  # type: ignore[call-arg]
        ollama_url="http://localhost:11434",
        arms=[ContextMode.CLOSED_BOOK],
        blocks=[EvalBlock.DIRECT, EvalBlock.MONTE_CARLO],
    )
    out = sched.measure(
        SpaceConfig(key="docs", url="http://localhost:8081", endpoint="kb"),
        conf,
        generate=False,
    )

    # Two blocks over two models is four passes. The refused name is asked in
    # the first and never again; the other model keeps both of its.
    assert asked == ["bad/name", "good/one", "good/one"]
    assert any("bad/name" in line for line in out.failures)
