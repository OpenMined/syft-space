"""Control questions graded by the judge panel: the prompt, the outcomes, the
storage and every figure that counts them."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import delete, select

import syft_benchmark.runs.execute as execute
import syft_benchmark.runs.judge as judge
import syft_benchmark.runs.parallel as parallel
from syft_benchmark.config import (
    ContextMode,
    ContextSource,
    ControlOutcome,
    EvalBlock,
    ExpectedBehavior,
    JobState,
    PairStatus,
    Settings,
    SpaceConfig,
    Verdict,
)
from syft_benchmark.db import Job, QaPair, Result, Run, session_scope
from syft_benchmark.llm import LLMError, Provider
from syft_benchmark.publish.space import payload_for
from syft_benchmark.report import run_view
from syft_benchmark.report.card import Card
from syft_benchmark.report.metrics import Metrics, render_markdown, summarize
from syft_benchmark.report.run_questions import question_detail
from syft_benchmark.report.slices import by_generator
from syft_benchmark.runs.judge import (
    FALSE_PREMISE,
    UNANSWERABLE,
    ControlCase,
    control_case,
    grade_control,
)
from syft_benchmark.runs.judge_stage import judge_pending, list_results

KEY = "pytest-control-judging"
JOB = "cj-job"
SUBJECT = "vendor/answerer"
J1, J2 = "judge/one", "judge/two"
CITED = [{"url": "https://example.org/fee", "title": "Fee schedule"}]
T0 = datetime(2026, 9, 1, 6, 0, tzinfo=UTC)


def _seat(role: str, model: str) -> Provider:
    return Provider(role=role, url="http://localhost:11434", api_key="", model=model)


ABSENT = ControlCase(
    kind=UNANSWERABLE, question="What is the hub's TLS fee?", missing="the fee"
)
PREMISE = ControlCase(
    kind=FALSE_PREMISE,
    question="Why did the hub drop TLS?",
    premise="the hub dropped TLS",
    correction="The hub requires TLS 1.3.",
)


class _Judge:
    """A judge stub: answers with a fixed behaviour, records what it was sent."""

    def __init__(self, reply: str) -> None:
        self.reply = reply
        self.sent: list[tuple[str, str, dict[str, Any]]] = []

    def __call__(self, system: str, user: str, **kwargs: Any) -> Any:
        self.sent.append((system, user, kwargs))
        return self.reply, {"served_by": "upstream-x"}


def _behaviour(name: str) -> str:
    return f'{{"behavior": "{name}", "reasoning": "because"}}'


# --- the prompt and the outcome ---------------------------------------------


@pytest.mark.parametrize(
    ("case", "named", "verdict"),
    [
        (ABSENT, "declined", Verdict.ABSTAIN),
        (ABSENT, "corrected", Verdict.ABSTAIN),
        (ABSENT, "made_up", Verdict.HALLUCINATE),
        (ABSENT, "web_sourced", Verdict.WEB_SOURCED),
        (PREMISE, "declined", Verdict.ABSTAIN),
        (PREMISE, "corrected", Verdict.CORRECT),
        (PREMISE, "made_up", Verdict.HALLUCINATE),
        (PREMISE, "web_sourced", Verdict.WEB_SOURCED),
    ],
)
def test_each_outcome_maps_onto_a_verdict(
    monkeypatch: pytest.MonkeyPatch, case: ControlCase, named: str, verdict: Verdict
) -> None:
    stub = _Judge(_behaviour(named))
    monkeypatch.setattr(judge, "chat", stub)

    graded = grade_control(
        case, "Some answer.", citations=CITED, judge=_seat("judge", J1)
    )

    assert graded.verdict is verdict
    assert graded.behavior == named
    assert graded.reasoning == "because"
    assert graded.served_by == "upstream-x"
    assert graded.judge_user and graded.judge_raw
    # The judge settings apply: it is a judging call on the panel seat.
    assert stub.sent[0][2]["judging"] is True
    assert stub.sent[0][2]["provider"].model == J1


def test_the_prompt_names_the_kind_and_the_citations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stub = _Judge(_behaviour("declined"))
    monkeypatch.setattr(judge, "chat", stub)

    grade_control(ABSENT, "The fee is $40.", citations=CITED)
    grade_control(PREMISE, "It never did.")

    absent, premise = stub.sent[0][1], stub.sent[1][1]
    assert "Kind: detail absent" in absent
    assert "What the archive does not state: the fee" in absent
    assert "1. Fee schedule — https://example.org/fee" in absent
    assert "Kind: false premise" in premise
    assert "False premise: the hub dropped TLS" in premise
    assert "What the archive says: The hub requires TLS 1.3." in premise
    assert "none: the answer cited no web sources" in premise
    assert '"behavior"' in stub.sent[0][0]


def test_web_sourced_without_citations_is_made_up(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(judge, "chat", _Judge(_behaviour("web_sourced")))

    graded = grade_control(ABSENT, "The fee is $40.", citations=[])

    assert graded.verdict is Verdict.HALLUCINATE
    assert graded.behavior == ControlOutcome.MADE_UP.value
    assert "no web citations" in graded.reasoning


def test_what_needs_no_judge_and_what_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    stub = _Judge("not json at all")
    monkeypatch.setattr(judge, "chat", stub)

    assert grade_control(ABSENT, "ERROR: HTTP 502").verdict is Verdict.TECHNICAL
    empty = grade_control(ABSENT, "  ")
    assert empty.verdict is Verdict.ABSTAIN and empty.behavior == "declined"
    assert stub.sent == []

    unread = grade_control(ABSENT, "The fee is $40.")
    assert unread.verdict is Verdict.TECHNICAL and unread.judge_user

    monkeypatch.setattr(judge, "chat", _Judge(_behaviour("guessed")))
    assert grade_control(ABSENT, "x").verdict is Verdict.TECHNICAL

    def down(*args: Any, **kwargs: Any) -> Any:
        raise LLMError("down")

    monkeypatch.setattr(judge, "chat", down)
    failed = grade_control(ABSENT, "The fee is $40.")
    assert failed.failed and failed.judge_user


def test_deferred_keeps_the_prompt(monkeypatch: pytest.MonkeyPatch) -> None:
    stub = _Judge(_behaviour("declined"))
    monkeypatch.setattr(judge, "chat", stub)

    graded = grade_control(ABSENT, "The fee is $40.", defer=True)

    assert graded.verdict is Verdict.PENDING
    assert "Kind: detail absent" in graded.judge_user
    assert stub.sent == []


def test_the_brief_comes_from_the_stored_pair() -> None:
    absent = control_case(
        UNANSWERABLE, "q", "not in the corpus: the fee", {"grading": "behavior"}
    )
    assert absent.missing == "the fee"
    premise = control_case(FALSE_PREMISE, "q", "It requires TLS.", {"premise": "p"})
    assert (premise.premise, premise.correction) == ("p", "It requires TLS.")


# --- the figures, without a database -----------------------------------------


def _metrics(expected: ExpectedBehavior, **counts: int) -> Metrics:
    graded = sum(counts.values())
    return Metrics(
        space=KEY,
        context_mode=ContextMode.CLOSED_BOOK,
        block=EvalBlock.DIRECT,
        model=SUBJECT,
        endpoint="",
        graded=graded,
        correct=counts.get("correct", 0),
        abstain=counts.get("abstain", 0),
        hallucinate=counts.get("hallucinate", 0),
        failed=0,
        retrieval_hits=0,
        retrieval_checked=0,
        checked_at=None,
        judge=J1,
        expected=expected,
        web_sourced=counts.get("web_sourced", 0),
    )


def test_fabrication_leaves_out_the_web_and_corrections() -> None:
    # Regex-graded rows of old: counted exactly as before.
    old = _metrics(ExpectedBehavior.ABSTAIN, abstain=3, hallucinate=1)
    assert old.fabrication_rate == pytest.approx(0.25)

    new = _metrics(ExpectedBehavior.ABSTAIN, abstain=2, hallucinate=1, web_sourced=1)
    assert new.fabrication_rate == pytest.approx(0.25)
    assert new.hallucination_rate == pytest.approx(0.25)
    assert new.web_sourced_rate == pytest.approx(0.25)
    assert new.lmi is None

    premise = _metrics(
        ExpectedBehavior.CORRECT_PREMISE, correct=2, abstain=1, hallucinate=1
    )
    assert premise.fabrication_rate == pytest.approx(0.25)

    text = render_markdown([new])
    assert "| From the web |" in text
    assert "| 25% | 1 |" in text

    card = Card(
        space=KEY,
        endpoint="kb",
        kind="answering",
        arm="open_book",
        checked_at=None,
        score=None,
        fabrication=0.25,
        control=new,
    )
    assert payload_for(card)["unanswerable"] == {
        "samples": 4,
        "fabricated": 0.25,
        "web_sourced": 1,
    }


# --- a stubbed run over both kinds in both conditions -------------------------


def _db_ready() -> bool:
    try:
        with session_scope() as session:
            session.execute(delete(QaPair).where(QaPair.space == KEY))
        return True
    except Exception:  # noqa: BLE001 - the database may simply not be at hand
        return False


needs_db = pytest.mark.skipif(
    not _db_ready(), reason="the benchmark database is unavailable"
)


@pytest.fixture
def clean() -> Any:
    def wipe() -> None:
        with session_scope() as session:
            session.execute(delete(Result).where(Result.space == KEY))
            session.execute(delete(Run).where(Run.space == KEY))
            session.execute(delete(QaPair).where(QaPair.space == KEY))
            session.execute(delete(Job).where(Job.target == KEY))

    wipe()
    yield
    wipe()


# qa id -> (generator, question, gold, meta, the answerer's reply)
_PAIRS: dict[str, tuple[str, str, str, dict[str, Any], str]] = {
    "u-declines": (
        UNANSWERABLE,
        "What fee does the hub charge for TLS?",
        "not in the corpus: the fee",
        {"grading": "behavior", "missing": "the fee"},
        "I don't know.",
    ),
    "u-states": (
        UNANSWERABLE,
        "Who signed the hub's TLS contract?",
        "not in the corpus: the signatory",
        {"grading": "behavior", "missing": "the signatory"},
        "It was signed by Jane Roe.",
    ),
    "p-corrects": (
        FALSE_PREMISE,
        "Why did the hub drop TLS?",
        "The hub requires TLS 1.3.",
        {"grading": "judge", "premise": "the hub dropped TLS"},
        "The premise is wrong: the hub requires TLS 1.3.",
    ),
    "p-states": (
        FALSE_PREMISE,
        "When did the hub switch to plain HTTP?",
        "The hub serves HTTPS only.",
        {"grading": "judge", "premise": "the hub switched to HTTP"},
        "It switched in 2020.",
    ),
}


def _rows() -> list[QaPair]:
    return [
        QaPair(
            id=qa,
            space=KEY,
            generator=generator,
            task_type="negative",
            question=question,
            answer=gold,
            context="The hub requires TLS 1.3.",
            meta=meta,
            expected_behavior=(
                ExpectedBehavior.CORRECT_PREMISE.value
                if generator == FALSE_PREMISE
                else ExpectedBehavior.ABSTAIN.value
            ),
            status=PairStatus.ACTIVE.value,
            model="m",
            question_hash=qa,
            doc_id="doc-1",
            file_name="hub.md",
            document_title="Hub",
        )
        for qa, (generator, question, gold, meta, _) in _PAIRS.items()
    ]


class _Stand:
    """The answerer searches the web alone (citations), not with the data;
    Judge 1 reads the behaviour, Judge 2 always says made up."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.judged: list[tuple[str, str]] = []
        replies = {question: reply for _, question, _, _, reply in _PAIRS.values()}

        def answer(system: str, user: str, **kwargs: Any) -> Any:
            question = next(q for q in replies if q in user)
            reply = replies[question]
            if system == execute._CLOSED_BOOK_SYSTEM:
                return reply, {"web_search": "plugin", "citations": CITED}
            return reply, {"web_search": False, "citations": []}

        def judging(system: str, user: str, **kwargs: Any) -> Any:
            seat = kwargs["provider"].model
            if system != judge._CONTROL_SYSTEM:
                return '{"grounded": true, "reasoning": "ok"}', {}
            self.judged.append((seat, user))
            if seat == J2:
                return _behaviour("made_up"), {}
            if "don't know" in user:
                return _behaviour("declined"), {}
            if "premise is wrong" in user:
                return _behaviour("corrected"), {}
            return _behaviour("web_sourced"), {}

        def endpoint(space: SpaceConfig, question: str, **kwargs: Any) -> Any:
            return {
                "answer": "",
                "documents": [
                    {
                        "content": "The hub requires TLS 1.3.",
                        "metadata": {"doc_id": "doc-1", "file_name": "hub.md"},
                        "similarity_score": 0.8,
                    }
                ],
                "latency": 0.0,
                "failed": False,
            }

        pairs = _rows()
        with session_scope() as session:
            session.add(
                Job(
                    id=JOB,
                    target=KEY,
                    state=JobState.SUCCEEDED.value,
                    created_at=T0,
                    finished_at=T0 + timedelta(hours=1),
                )
            )
            session.add_all(_rows())
        monkeypatch.setattr(parallel, "chat", answer)
        monkeypatch.setattr(judge, "chat", judging)
        monkeypatch.setattr(execute, "check_grounded", lambda *a, **k: (True, "ok"))
        monkeypatch.setattr(parallel, "ask_endpoint", endpoint)
        monkeypatch.setattr(execute, "endpoint_mode", lambda space: "both")
        monkeypatch.setattr(execute, "_active_pairs", lambda key, limit, conf: pairs)


def _conf() -> Settings:
    return Settings(
        ollama_url="http://localhost:11434",
        context_source=ContextSource.ENDPOINT_FRAGMENTS,
        judge_policy="off",
        text_metrics=[],
    )


def _run(conf: Settings, *, defer: bool = False) -> None:
    space = SpaceConfig(key=KEY, url="http://node.invalid", endpoint="kb")
    for mode in (ContextMode.CLOSED_BOOK, ContextMode.MODEL_WITH_CONTEXT):
        execute.run_pass(
            space,
            mode,
            settings=conf,
            subject=_seat("subject", SUBJECT),
            judges=[_seat("judge", J1), _seat("judge", J2)],
            job_id=JOB,
            defer_judging=defer,
        )


def _results() -> dict[tuple[str, str, str], Result]:
    with session_scope() as session:
        rows = session.execute(
            select(Result, Run.context_mode)
            .join(Run, Run.id == Result.run_id)
            .where(Result.space == KEY)
        ).all()
        out = {}
        for result, mode in rows:
            session.expunge(result)
            out[(mode, result.qa_id, result.judge_model)] = result
        return out


@needs_db
def test_a_run_grades_both_kinds_in_both_conditions(
    monkeypatch: pytest.MonkeyPatch, clean: None
) -> None:
    stand = _Stand(monkeypatch)
    _run(_conf())

    # Every panel judge graded every control answer in both conditions.
    assert len(stand.judged) == 2 * 2 * len(_PAIRS)
    rows = _results()
    alone, with_ = ContextMode.CLOSED_BOOK.value, ContextMode.MODEL_WITH_CONTEXT.value

    def outcome(mode: str, qa: str, seat: str = J1) -> tuple[str, str]:
        row = rows[(mode, qa, seat)]
        return row.verdict, (row.extra or {}).get("behavior", "")

    assert outcome(alone, "u-declines") == ("abstain", "declined")
    assert outcome(alone, "u-states") == ("web_sourced", "web_sourced")
    assert outcome(alone, "p-corrects") == ("correct", "corrected")
    assert outcome(alone, "p-states") == ("web_sourced", "web_sourced")
    # With the data there was no search: web_sourced cannot stand.
    assert outcome(with_, "u-states") == ("hallucinate", "made_up")
    assert outcome(with_, "p-states") == ("hallucinate", "made_up")
    assert "no web citations" in rows[(with_, "u-states", J1)].reasoning
    assert outcome(with_, "p-corrects") == ("correct", "corrected")
    assert outcome(alone, "u-declines", J2) == ("hallucinate", "made_up")

    # The transcript carries the judge's exchange; the citations reached it.
    audit = rows[(alone, "u-states", J1)].audit
    assert "Fee schedule — https://example.org/fee" in audit["judge_prompt"]
    assert "judged_without_model" not in audit
    views, _ = list_results(KEY, qa_id="u-states", prompts=True)
    assert all(v.prompts and v.prompts.judge_prompt for v in views)
    assert all(not v.prompts.judged_without_model for v in views if v.prompts)
    assert {(v.judge_model, v.behavior) for v in views} >= {
        (J1, "web_sourced"),
        (J1, "made_up"),
        (J2, "made_up"),
    }

    # The run report: Judge 1's verdicts count, web_sourced on its own.
    with session_scope() as session:
        job = session.get(Job, JOB)
        assert job is not None
        payload = run_view.compute(session, job, configured=[J1, J2])
    model = payload["models"][0]
    checks = model["checks"]
    assert (checks["trick_asked"], checks["trick_answered"], checks["trick_web"]) == (
        2,
        1,
        0,
    )
    assert (
        checks["trick_alone_asked"],
        checks["trick_alone_answered"],
        checks["trick_alone_web"],
    ) == (2, 0, 1)
    assert model["tally"]["alone"]["web_sourced"] == 1
    assert model["tally"]["alone"]["graded"] == 2
    assert model["made_up_alone"] == 0.0
    assert model["made_up_with"] == 0.5
    assert model["rate_alone"] == 0.5
    premise = next(k for k in model["kinds"] if k["generator"] == FALSE_PREMISE)
    assert (premise["web_alone"], premise["web_with"]) == (1, 0)
    card = run_view.card_models(model)
    assert card["fabrication"] == 0.5

    # The question detail carries the fine outcome: counted and per judge.
    with session_scope() as session:
        job = session.get(Job, JOB)
        assert job is not None
        detail = question_detail(session, job, "p-states", configured=[J1, J2])
    assert detail is not None
    assert detail["arms"]["alone"]["behavior"] == "web_sourced"
    assert detail["arms"]["with"]["behavior"] == "made_up"
    first, second = detail["judges"]
    assert (first["alone_behavior"], second["alone_behavior"]) == (
        "web_sourced",
        "made_up",
    )

    # The node figures.
    control = summarize(
        KEY,
        ContextMode.CLOSED_BOOK,
        model=SUBJECT,
        judge=J1,
        expected=ExpectedBehavior.ABSTAIN,
        job=JOB,
    )
    assert control is not None
    assert (control.graded, control.web_sourced, control.hallucinate) == (2, 1, 0)
    assert control.fabrication_rate == 0.0
    slices = by_generator(
        KEY,
        ContextMode.CLOSED_BOOK,
        model=SUBJECT,
        judge=J1,
        expected=ExpectedBehavior.CORRECT_PREMISE,
        job=JOB,
    )
    assert [(s.generator, s.graded, s.web_sourced) for s in slices] == [
        (FALSE_PREMISE, 2, 1)
    ]


@needs_db
def test_deferred_control_answers_are_graded_later(
    monkeypatch: pytest.MonkeyPatch, clean: None
) -> None:
    stand = _Stand(monkeypatch)
    _run(_conf(), defer=True)
    assert stand.judged == []
    pending = _results()
    assert {r.verdict for r in pending.values()} == {Verdict.PENDING.value}

    report = judge_pending(
        SpaceConfig(key=KEY, url="http://node.invalid", endpoint="kb"),
        settings=_conf(),
        judge=_seat("judge", J1),
    )

    assert report.checked == 2 * len(_PAIRS)
    assert report.web_sourced == 2
    graded = [r for r in _results().values() if r.verdict != Verdict.PENDING.value]
    by_key = {(r.qa_id, (r.extra or {}).get("behavior")): r.verdict for r in graded}
    assert by_key[("u-declines", "declined")] == "abstain"
    assert by_key[("p-corrects", "corrected")] == "correct"
    assert ("u-states", "web_sourced") in by_key
    assert ("u-states", "made_up") in by_key
    assert all(r.audit.get("judge_prompt") for r in graded)


@needs_db
def test_older_regex_rows_count_as_before(clean: None) -> None:
    with session_scope() as session:
        session.add(
            Job(
                id=JOB,
                target=KEY,
                state=JobState.SUCCEEDED.value,
                created_at=T0,
                finished_at=T0,
            )
        )
        session.add_all(_rows())
        session.flush()
        for mode in (ContextMode.CLOSED_BOOK, ContextMode.MODEL_WITH_CONTEXT):
            run_id = f"run-{mode.value}"
            session.add(
                Run(
                    id=run_id,
                    space=KEY,
                    job_id=JOB,
                    context_mode=mode.value,
                    block="direct",
                    model=SUBJECT,
                )
            )
            for qa, verdict in (("u-declines", "abstain"), ("u-states", "hallucinate")):
                session.add(
                    Result(
                        id=f"{run_id}-{qa}",
                        run_id=run_id,
                        qa_id=qa,
                        space=KEY,
                        answer="x",
                        verdict=verdict,
                        expected_behavior="abstain",
                        judge_model=J1,
                        audit={"judged_without_model": True},
                    )
                )

    with session_scope() as session:
        job = session.get(Job, JOB)
        assert job is not None
        checks = run_view.compute(session, job, configured=[J1])["models"][0]["checks"]
    assert (checks["trick_asked"], checks["trick_answered"], checks["trick_web"]) == (
        2,
        1,
        0,
    )
    control = summarize(
        KEY,
        ContextMode.CLOSED_BOOK,
        model=SUBJECT,
        expected=ExpectedBehavior.ABSTAIN,
        job=JOB,
    )
    assert control is not None
    assert control.fabrication_rate == 0.5 and control.web_sourced == 0
    view = list_results(KEY, qa_id="u-states", prompts=True)[0][0]
    assert view.prompts is not None and view.prompts.judged_without_model
