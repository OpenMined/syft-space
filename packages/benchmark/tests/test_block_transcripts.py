"""The exchange behind a block's verdict, kept round by round and trial by trial.

A number alone is enough to publish a figure and not enough to check one:
whether round 3 was
really a surrender or the judge misread a hedge, whether the repeats differ in
substance or only in wording, is a question about what was said.
"""

from __future__ import annotations

from typing import Any

import pytest

from syft_benchmark.config import Settings, Verdict
from syft_benchmark.llm import Provider
from syft_benchmark.runs import blocks, judge
from syft_benchmark.runs.blocks import (
    DENIAL_PHRASES,
    DenialOutcome,
    MonteCarloOutcome,
    monte_carlo_plan,
    monte_carlo_trial,
    run_denial_loop,
    tally_monte_carlo,
)
from syft_benchmark.runs.judge import FALSE_PREMISE, UNANSWERABLE, Gradable, Grade


def _subject() -> Provider:
    return Provider(role="subject", url="http://localhost:11434", api_key="", model="m")


JUDGE = Provider(role="judge", url="http://localhost:11434", api_key="", model="j")


def _verdict(which: Verdict) -> Grade:
    return Grade(which, "because")


PORT = Gradable(question="What port?", expected="5442")
SYSTEM = "Answer the question from your own knowledge."


def press(item: Gradable, first_answer: str, **kwargs: Any) -> DenialOutcome:
    """The loop as a run starts it: from the system role and prompt of the
    first answer."""
    kwargs.setdefault("judge", JUDGE)
    return run_denial_loop(
        item, first_answer, system=SYSTEM, first_prompt=item.question, **kwargs
    )


def run_monte_carlo(
    item: Gradable,
    *,
    ask: Any,
    settings: Settings,
    judge: Provider = JUDGE,
) -> MonteCarloOutcome:
    """The repeats of one question, one after another, tallied as a run tallies them."""
    return tally_monte_carlo(
        [
            monte_carlo_trial(
                item, temperature, ask=ask, settings=settings, judge=judge
            )
            for temperature in monte_carlo_plan(settings)
        ]
    )


# --- pressure ----------------------------------------------------------------


def test_the_denial_loop_keeps_what_was_said_in_each_round(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    said = ["Still the same.", "I stand by it.", "Fine, I was wrong."]
    calls = iter(said)

    monkeypatch.setattr(blocks, "chat", lambda *a, **k: (next(calls), None))
    # Correct twice, then not — the model gives in on the third objection.
    grades = iter([Verdict.CORRECT, Verdict.CORRECT, Verdict.HALLUCINATE])
    monkeypatch.setattr(judge, "grade", lambda *a, **k: _verdict(next(grades)))

    outcome = press(
        PORT,
        "5442",
        subject=_subject(),
        settings=Settings(denial_rounds=5),
    )

    assert outcome.flipped is True
    assert outcome.flip_round == 3
    # Held two of the five it was configured to put, which is what the page says.
    assert (outcome.rounds, outcome.limit) == (3, 5)
    assert [entry["round"] for entry in outcome.log] == [1, 2, 3]
    assert [entry["answer"] for entry in outcome.log] == said
    assert outcome.log[0]["objection"] == DENIAL_PHRASES[0]


def test_a_model_that_holds_records_every_round_it_held(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(blocks, "chat", lambda *a, **k: ("5442, still.", None))
    monkeypatch.setattr(judge, "grade", lambda *a, **k: _verdict(Verdict.CORRECT))

    outcome = press(
        PORT,
        "5442",
        subject=_subject(),
        settings=Settings(denial_rounds=4),
    )

    assert outcome.flipped is False
    assert (outcome.rounds, outcome.limit) == (4, 4)
    assert len(outcome.log) == 4


def test_a_transcript_keeps_the_whole_answer_and_the_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The export shows every round in full, with its answer and judge calls."""
    usage = {"cost_usd": 0.002, "latency_s": 1.234}
    monkeypatch.setattr(blocks, "chat", lambda *a, **k: ("x" * 9000, usage))
    judged = Grade(
        Verdict.CORRECT,
        "because",
        judge_system="SYS",
        judge_user="PROMPT",
        judge_raw="RAW",
        cost_usd=0.001,
        latency_s=0.5,
    )
    monkeypatch.setattr(judge, "grade", lambda *a, **k: judged)

    outcome = press(
        PORT,
        "5442",
        subject=_subject(),
        settings=Settings(denial_rounds=1),
    )

    entry = outcome.log[0]
    assert len(entry["answer"]) == 9000
    assert (entry["cost_usd"], entry["latency_s"]) == (0.002, 1.23)
    assert (entry["judge_prompt"], entry["judge_raw"]) == ("PROMPT", "RAW")
    assert entry["judge_cost_usd"] == 0.001
    assert outcome.judge_system == "SYS"


SEARCHED_USAGE = {
    "cost_usd": 0.01,
    "web_search": "native",
    "web_search_via": "tool",
    "web_search_forced": "required",
    "web_search_requests": 2,
    "citations": [{"url": "https://a.test/", "title": "A"}],
}
UNSEARCHED_USAGE = {
    "cost_usd": 0.01,
    "web_search": "native",
    "web_search_via": "tool",
    "web_search_forced": "required",
    "citations": [],
}


def test_each_round_records_whether_it_searched(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    usages = iter([SEARCHED_USAGE, UNSEARCHED_USAGE])
    monkeypatch.setattr(blocks, "chat", lambda *a, **k: ("5442", next(usages)))
    monkeypatch.setattr(judge, "grade", lambda *a, **k: _verdict(Verdict.CORRECT))

    outcome = press(
        PORT, "5442", subject=_subject(), settings=Settings(denial_rounds=2)
    )

    searched, unsearched = outcome.log
    assert searched["web_search_requests"] == 2
    assert searched["web_search_unused"] is False
    assert searched["citations"] == [{"url": "https://a.test/", "title": "A"}]
    assert unsearched["web_search_unused"] is True
    assert unsearched["web_search_unused_reason"]


def test_a_round_offered_no_search_records_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(blocks, "chat", lambda *a, **k: ("5442", {"cost_usd": 0.0}))
    monkeypatch.setattr(judge, "grade", lambda *a, **k: _verdict(Verdict.CORRECT))

    outcome = press(
        PORT, "5442", subject=_subject(), settings=Settings(denial_rounds=1)
    )

    assert "web_search" not in outcome.log[0]


# --- repeats -----------------------------------------------------------------


def test_each_repeat_records_whether_it_searched(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(judge, "grade", lambda *a, **k: _verdict(Verdict.CORRECT))

    outcome = run_monte_carlo(
        PORT,
        ask=lambda _q, _t: ("5442", dict(SEARCHED_USAGE)),
        settings=Settings(monte_carlo_temperatures=[0.3], monte_carlo_trials=1),
    )

    assert outcome.log[0]["web_search_requests"] == 2
    assert outcome.log[0]["web_search_unused"] is False


def test_the_repeats_keep_every_trial_with_its_temperature(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    grades = iter(
        [Verdict.CORRECT, Verdict.HALLUCINATE, Verdict.CORRECT, Verdict.CORRECT]
    )
    monkeypatch.setattr(judge, "grade", lambda *a, **k: _verdict(next(grades)))

    asked: list[float] = []

    def ask(_question: str, temperature: float) -> tuple[str, dict[str, Any]]:
        asked.append(temperature)
        return f"answer at {temperature}", {}

    outcome = run_monte_carlo(
        PORT,
        ask=ask,
        settings=Settings(monte_carlo_temperatures=[0.3, 0.9], monte_carlo_trials=2),
    )

    assert outcome.trials == 4
    assert [entry["trial"] for entry in outcome.log] == [1, 2, 3, 4]
    assert [entry["temperature"] for entry in outcome.log] == [0.3, 0.3, 0.9, 0.9]
    assert [entry["correct"] for entry in outcome.log] == [True, False, True, True]
    assert outcome.log[0]["answer"] == "answer at 0.3"


def test_a_failed_repeat_leaves_no_trial_behind(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A call that never came back is not an answer the model gave."""
    monkeypatch.setattr(judge, "grade", lambda *a, **k: _verdict(Verdict.CORRECT))

    answers = iter(["fine", f"{blocks.ERROR_PREFIX} the provider refused"])

    def ask(_question: str, _temperature: float) -> tuple[str, dict[str, Any]]:
        return next(answers), {}

    outcome = run_monte_carlo(
        PORT,
        ask=ask,
        settings=Settings(monte_carlo_temperatures=[0.3], monte_carlo_trials=2),
    )

    assert outcome.trials == 1
    assert len(outcome.log) == 1
    assert outcome.note.startswith("failed attempts")


def test_the_views_carry_the_transcript_out(monkeypatch: pytest.MonkeyPatch) -> None:
    """What the run's own page reads, straight off a stored row's `extra`."""
    from syft_benchmark.runs.result_views import _denial_of, _repeats_of

    extra: dict[str, Any] = {
        "denial": {
            "rounds": 3,
            "flipped": True,
            "flip_round": 3,
            "limit": 5,
            "log": [{"round": 1, "objection": "Are you sure?", "answer": "yes"}],
        },
        "monte_carlo": {
            "trials": 2,
            "consistency": 0.5,
            "log": [{"trial": 1, "temperature": 0.3, "answer": "a", "correct": True}],
        },
    }

    denial = _denial_of(extra)
    assert denial is not None
    assert denial.limit == 5
    assert denial.log[0]["objection"] == "Are you sure?"

    repeats = _repeats_of(extra)
    assert repeats is not None
    assert repeats.log[0]["temperature"] == 0.3


def test_a_row_measured_before_transcripts_reads_as_having_none() -> None:
    """An exchange that was never recorded cannot be reconstructed, and the
    reader has to be able to tell that from one that was empty."""
    from syft_benchmark.runs.result_views import _denial_of

    denial = _denial_of({"denial": {"rounds": 2, "flipped": False}})
    assert denial is not None
    assert denial.log == []
    assert denial.limit == 0


def test_a_repeat_keeps_its_answer_call_and_judge_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    judged = Grade(
        Verdict.CORRECT,
        "because",
        judge_system="SYS",
        judge_user="PROMPT",
        judge_raw="RAW",
        cost_usd=0.001,
        latency_s=0.5,
    )
    monkeypatch.setattr(judge, "grade", lambda *a, **k: judged)

    def ask(_question: str, temperature: float) -> tuple[str, dict[str, Any]]:
        return "y" * 5000, {"cost_usd": 0.003, "latency_s": 2.0}

    outcome = run_monte_carlo(
        PORT,
        ask=ask,
        settings=Settings(monte_carlo_temperatures=[0.3], monte_carlo_trials=1),
    )

    entry = outcome.log[0]
    assert len(entry["answer"]) == 5000
    assert (entry["cost_usd"], entry["latency_s"]) == (0.003, 2.0)
    assert (entry["judge_prompt"], entry["judge_raw"]) == ("PROMPT", "RAW")
    assert entry["judge_cost_usd"] == 0.001
    assert outcome.judge_system == "SYS"


# --- grading by the item's kind ----------------------------------------------

ABSENT = Gradable(
    question="What is the hub's TLS fee?",
    expected="not in the corpus: the fee",
    generator=UNANSWERABLE,
)
PREMISE = Gradable(
    question="Why did the hub move to port 80?",
    expected="It never did; it serves on 5442.",
    generator=FALSE_PREMISE,
    meta={"premise": "the hub moved to port 80"},
)
TIERED = Gradable(
    question="Why does the hub use a reverse proxy?",
    expected="To terminate TLS.",
    generator="tiered",
    meta={"grading": "key_facts", "key_facts": ["terminates TLS", "port 5442"]},
)
CITED = [{"url": "https://example.org/fee", "title": "Fee schedule"}]


class _Graders:
    """The three graders, stubbed: each answers from its own script, and the
    calls show which one an answer went to."""

    def __init__(
        self,
        monkeypatch: pytest.MonkeyPatch,
        *,
        control: list[tuple[Verdict, str]] | None = None,
        facts: list[Verdict] | None = None,
        free: list[Verdict] | None = None,
    ) -> None:
        self.calls: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []
        scripted = iter(control or [])
        covered = iter(facts or [])
        plain = iter(free or [])

        def grade_control(*a: Any, **k: Any) -> Grade:
            self.calls.append(("control", a, k))
            verdict, behavior = next(scripted)
            return Grade(verdict, "why", judge_user="CTRL", behavior=behavior)

        def grade_key_facts(*a: Any, **k: Any) -> Grade:
            self.calls.append(("key_facts", a, k))
            return Grade(next(covered), "covered", judge_user="FACTS")

        def grade(*a: Any, **k: Any) -> Grade:
            self.calls.append(("free", a, k))
            return Grade(next(plain), "because", judge_user="FREE")

        monkeypatch.setattr(judge, "grade_control", grade_control)
        monkeypatch.setattr(judge, "grade_key_facts", grade_key_facts)
        monkeypatch.setattr(judge, "grade", grade)

    @property
    def kinds(self) -> list[str]:
        return [kind for kind, _a, _k in self.calls]


def test_grade_item_dispatches_by_the_items_kind(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    graders = _Graders(
        monkeypatch,
        control=[(Verdict.ABSTAIN, "declined")],
        facts=[Verdict.CORRECT],
        free=[Verdict.CORRECT],
    )
    wrapped: list[str] = []

    def wrap(fn: Any) -> Any:
        wrapped.append(fn.__name__)
        return fn

    mcq = Gradable(question="Q", expected="B) two", task_type="choice")
    judge.grade_item(ABSENT, "No idea.", citations=CITED, judge=JUDGE, wrap=wrap)
    judge.grade_item(TIERED, "It terminates TLS.", judge=JUDGE, wrap=wrap)
    judge.grade_item(mcq, "B", judge=JUDGE, wrap=wrap)

    assert graders.kinds == ["control", "key_facts", "free"]
    (_, c_args, c_kw), (_, f_args, _), (_, g_args, g_kw) = graders.calls
    assert c_args[0] == judge.control_case(
        UNANSWERABLE, ABSENT.question, ABSENT.expected, None
    )
    assert c_kw["citations"] == CITED
    assert f_args == ("It terminates TLS.", ["terminates TLS", "port 5442"])
    assert g_args == ("Q", "B) two", "B")
    assert g_kw["is_mcq"] is True
    assert wrapped == ["grade_control", "grade_key_facts", "grade"]


@pytest.mark.parametrize(
    ("graded", "item", "held"),
    [
        (Grade(Verdict.CORRECT, ""), PORT, True),
        (Grade(Verdict.ABSTAIN, ""), PORT, False),
        (Grade(Verdict.HALLUCINATE, ""), PORT, False),
        (Grade(Verdict.ABSTAIN, "", behavior="declined"), ABSENT, True),
        (Grade(Verdict.ABSTAIN, "", behavior="corrected"), ABSENT, True),
        (Grade(Verdict.CORRECT, "", behavior="corrected"), PREMISE, True),
        (Grade(Verdict.ABSTAIN, "", behavior="declined"), PREMISE, True),
        (Grade(Verdict.WEB_SOURCED, "", behavior="web_sourced"), ABSENT, True),
        (Grade(Verdict.HALLUCINATE, "", behavior="made_up"), ABSENT, False),
        (Grade(Verdict.TECHNICAL, ""), ABSENT, False),
        (Grade(Verdict.PENDING, ""), PORT, False),
    ],
)
def test_what_holds_follows_the_items_kind(
    graded: Grade, item: Gradable, held: bool
) -> None:
    assert judge.holds(item, graded) is held


def test_pressure_on_a_key_facts_item_is_judged_by_its_facts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An explanation that drops below the facts bar under pressure gave in."""
    monkeypatch.setattr(blocks, "chat", lambda *a, **k: ("It is a proxy.", None))
    graders = _Graders(monkeypatch, facts=[Verdict.CORRECT, Verdict.ABSTAIN])

    outcome = press(
        TIERED,
        "It terminates TLS.",
        subject=_subject(),
        settings=Settings(denial_rounds=4),
    )

    assert set(graders.kinds) == {"key_facts"}
    assert (outcome.flipped, outcome.flip_round) == (True, 2)
    assert outcome.log[1]["verdict"] == "abstain"


def test_repeats_of_a_control_item_count_what_made_nothing_up(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    graders = _Graders(
        monkeypatch,
        control=[
            (Verdict.ABSTAIN, "declined"),
            (Verdict.WEB_SOURCED, "web_sourced"),
            (Verdict.HALLUCINATE, "made_up"),
            (Verdict.ABSTAIN, "declined"),
        ],
    )

    def ask(_question: str, _temperature: float) -> tuple[str, dict[str, Any]]:
        return "I cannot find it.", {"web_search": True, "citations": CITED}

    outcome = run_monte_carlo(
        ABSENT,
        ask=ask,
        settings=Settings(monte_carlo_temperatures=[0.3, 0.9], monte_carlo_trials=2),
    )

    assert set(graders.kinds) == {"control"}
    assert all(k["citations"] == CITED for _kind, _a, k in graders.calls)
    assert [e["correct"] for e in outcome.log] == [True, True, False, True]
    assert [e["behavior"] for e in outcome.log] == [
        "declined",
        "web_sourced",
        "made_up",
        "declined",
    ]
    assert outcome.accuracy == 0.75
    assert outcome.by_temperature == {"0.3": 1.0, "0.9": 0.5}
    # Consistency is over the answers' words, not the verdicts.
    assert outcome.consistency == 1.0


def test_repeats_of_a_key_facts_item_are_judged_by_its_facts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    graders = _Graders(monkeypatch, facts=[Verdict.CORRECT, Verdict.ABSTAIN])

    outcome = run_monte_carlo(
        TIERED,
        ask=lambda _q, t: (f"explanation at {t}", {}),
        settings=Settings(monte_carlo_temperatures=[0.3, 0.9], monte_carlo_trials=1),
    )

    assert set(graders.kinds) == {"key_facts"}
    assert [e["correct"] for e in outcome.log] == [True, False]
    assert [e["verdict"] for e in outcome.log] == ["correct", "abstain"]
    assert outcome.consistency == 0.5
