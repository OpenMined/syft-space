"""The three arms, building the context and the audit trail.

What is checked here is what the interpretation rests on: arms A and C differ
by exactly the presence of context, an arm's incompatibility with the
endpoint's mode is named before the run, and the prompt is stored next to the
answer.
"""

from __future__ import annotations

from syft_benchmark.config import (
    ARM_LETTER,
    ContextMode,
    ContextSource,
    Settings,
    SpaceConfig,
    Verdict,
)
from syft_benchmark.runs import (
    Asked,
    Grade,
    arm_blocker,
    audit_record,
    build_context,
    pick_pairs,
    with_context_prompt,
)
from syft_benchmark.runs.execute import (
    _CLOSED_BOOK_SYSTEM,
    _NEEDS_ANSWER,
    _WITH_CONTEXT_SYSTEM,
    RETRIEVAL_ONLY_TOKENS,
)

FRAGMENTS = [
    {
        "file_name": "setup.md",
        "score": 0.81,
        "content": "The port is published as 5442.",
    },
    {"file_name": "api.md", "score": 0.64, "content": "The hub stores metrics itself."},
    {"file_name": "old.md", "score": 0.41, "content": "The third chunk."},
]


def _settings(**kwargs: object) -> Settings:
    return Settings(**kwargs)  # type: ignore[arg-type]


def test_every_arm_has_a_letter() -> None:
    """Every arm has a letter: the report speaks the methodology's language."""
    for mode in ContextMode:
        assert ARM_LETTER[mode.value] in {"A", "B", "C"}


def test_arms_a_and_c_differ_only_by_context() -> None:
    """Arm C's instruction repeats the form of arm A's instruction.

    Let them diverge in style and the difference between the arms would measure
    the wording of the prompt, whereas it has to measure exactly the appearance
    of context.
    """
    for system in (_CLOSED_BOOK_SYSTEM, _WITH_CONTEXT_SYSTEM):
        assert "I don't know" in system
        assert "Do not guess" in system or "do not guess" in system


def test_context_keeps_order_and_respects_the_limit() -> None:
    """The top chunks are mixed in, in the order retrieved and with a label."""
    context = build_context(
        FRAGMENTS, "", source=ContextSource.ENDPOINT_FRAGMENTS, limit=2
    )
    assert "[1] setup.md" in context
    assert "[2] api.md" in context
    assert "old.md" not in context, "the limit was not respected"


def test_endpoint_answer_is_a_separate_source() -> None:
    """The endpoint's ready answer and the chunks are different sources."""
    only_answer = build_context(
        FRAGMENTS, "Port 5442.", source=ContextSource.ENDPOINT_ANSWER, limit=3
    )
    assert "endpoint answer" in only_answer
    assert "setup.md" not in only_answer

    both = build_context(
        FRAGMENTS, "Port 5442.", source=ContextSource.ENDPOINT_BOTH, limit=3
    )
    assert "endpoint answer" in both
    assert "setup.md" in both


def test_failed_endpoint_answer_never_becomes_context() -> None:
    """A failure message is not material: mixing it in means judging the rig."""
    context = build_context(
        [], "ERROR: HTTP 502", source=ContextSource.ENDPOINT_ANSWER, limit=3
    )
    assert context == ""


def test_oracle_context_does_not_need_retrieval() -> None:
    """The oracle arm takes the source chunk: retrieval takes no part in it."""
    context = build_context(
        [], "", source=ContextSource.ORACLE_CHUNK, limit=3, oracle="Port 5442."
    )
    assert "Port 5442." in context


def test_question_comes_before_the_material() -> None:
    """The question is read before the material, not fitted to what was found."""
    prompt = with_context_prompt("Which port?", "[1] setup.md\nPort 5442.")
    assert prompt.index("Which port?") < prompt.index("setup.md")


def test_summary_endpoint_blocks_the_fragment_arm() -> None:
    """Summary mode cuts the references out — arm C is not measurable on it.

    This has to be said before the run: otherwise the arm would work through
    without a single chunk and show comfortable zeros where nothing was
    measured.
    """
    blocked = arm_blocker(
        ContextMode.MODEL_WITH_CONTEXT, "summary", ContextSource.ENDPOINT_FRAGMENTS
    )
    assert "summary" in blocked

    allowed = arm_blocker(
        ContextMode.MODEL_WITH_CONTEXT, "both", ContextSource.ENDPOINT_FRAGMENTS
    )
    assert allowed == ""


def test_raw_endpoint_blocks_the_prose_arms() -> None:
    """Raw mode does not compose an answer: arm B has nothing to grade."""
    assert arm_blocker(ContextMode.OPEN_BOOK, "raw", ContextSource.ENDPOINT_OWN)
    assert (
        arm_blocker(
            ContextMode.MODEL_WITH_CONTEXT, "raw", ContextSource.ENDPOINT_ANSWER
        )
        != ""
    )
    # Raw does hand back chunks — this arm works on it.
    assert (
        arm_blocker(
            ContextMode.MODEL_WITH_CONTEXT, "raw", ContextSource.ENDPOINT_FRAGMENTS
        )
        == ""
    )


def test_unknown_endpoint_mode_does_not_block_the_run() -> None:
    """A failed diagnostic is not the same thing as a known incompatibility."""
    assert arm_blocker(ContextMode.OPEN_BOOK, "", ContextSource.ENDPOINT_OWN) == ""


def test_audit_keeps_prompts_and_the_judge_trail() -> None:
    """A verdict can be rechecked: both prompts and the judge's answer are stored."""
    asked = Asked(
        answer="Port 5442.",
        latency=0.4,
        system=_WITH_CONTEXT_SYSTEM,
        user=with_context_prompt("Which port?", "[1] setup.md\nPort 5442."),
        retrieval={"retrieval_hit": True, "retrieval_rank": 1, "retrieved": FRAGMENTS},
        context_source=ContextSource.ENDPOINT_FRAGMENTS,
        context="[1] setup.md\nPort 5442.",
    )
    verdict = Grade(
        Verdict.CORRECT,
        "matches the reference answer",
        judge_system="judge system",
        judge_user="judge user",
        judge_raw='{"correct": true}',
    )
    record = audit_record(asked, verdict, _settings())

    assert record["responder_prompt"].startswith("Question:")
    assert record["context_source"] == "endpoint_fragments"
    assert record["context"] == "[1] setup.md\nPort 5442."
    assert record["judge_raw"] == '{"correct": true}'


def test_audit_marks_verdicts_that_cost_no_model_call() -> None:
    """Matching a letter and spotting an abstention do not call the judge.

    That is a fact for the audit too.
    """
    asked = Asked(
        answer="I don't know",
        latency=0.1,
        system=_CLOSED_BOOK_SYSTEM,
        user="Which port?",
        retrieval={"retrieval_hit": None, "retrieval_rank": None, "retrieved": []},
        context_source=ContextSource.NONE,
    )
    record = audit_record(
        asked, Grade(Verdict.ABSTAIN, "refused to answer"), _settings()
    )
    assert record["judged_without_model"] is True
    assert "judge_prompt" not in record


def test_audit_can_be_switched_off() -> None:
    """The log holds corpus text, and the owner is entitled not to keep it."""
    asked = Asked(
        answer="an answer",
        latency=0.1,
        system="s",
        user="u",
        retrieval={"retrieval_hit": None, "retrieval_rank": None, "retrieved": []},
        context_source=ContextSource.NONE,
    )
    off = _settings(audit_log=False)
    assert audit_record(asked, Grade(Verdict.CORRECT, ""), off) == {}


def test_space_overrides_the_retrieval_knobs() -> None:
    """The threshold is tuned to the corpus, so it lives on the Space."""
    conf = _settings(retrieval_top_k=5, similarity_threshold=0.0)
    common = SpaceConfig(key="a", url="http://x", endpoint="e")
    tuned = SpaceConfig(
        key="b",
        url="http://x",
        endpoint="e",
        retrieval_top_k=8,
        similarity_threshold=0.45,
    )
    assert conf.retrieval_for(common) == (5, 0.0)
    assert conf.retrieval_for(tuned) == (8, 0.45)


def test_run_records_the_settings_that_produced_it() -> None:
    """A configurable methodology has to leave a trail in every run."""
    conf = _settings(methodology_profile="strict", similarity_threshold=0.45)
    params = conf.measurement_params(SpaceConfig(key="a", url="http://x", endpoint="e"))
    assert params["profile"] == "strict"
    assert params["similarity_threshold"] == 0.45
    assert "context_source" in params


class _Pair:
    """A pair as the pick needs it: the labelling, the generator and the time."""

    def __init__(self, behavior: str, number: int, generator: str = "cloze") -> None:
        self.expected_behavior = behavior
        self.generator = generator
        self.id = f"{behavior}-{generator}-{number}"


def test_every_generator_gets_its_share() -> None:
    """The pick's main property: the limit counts PER GENERATOR.

    A generator is a separate skill, not a share of the sample. An overall
    limit divided between them would, at a small value, simply throw some
    generators out: ten items over ten generators — and half were not checked
    at all, while the report called the result the model's accuracy.
    """
    rows = [
        _Pair("answer", i, generator)
        for generator in ("cloze", "mcq", "multihop", "tiered")
        for i in range(20)
    ]
    picked = pick_pairs(rows, 3)  # type: ignore[arg-type]

    by_generator: dict[str, int] = {}
    for pair in picked:
        by_generator[pair.generator] = by_generator.get(pair.generator, 0) + 1
    assert by_generator == {"cloze": 3, "mcq": 3, "multihop": 3, "tiered": 3}
    assert len(picked) == 12


def test_a_generator_with_less_than_the_limit_gives_what_it_has() -> None:
    """A poor generator neither cancels the others' limit nor takes their place."""
    rows = [_Pair("answer", i, "cloze") for i in range(10)]
    rows += [_Pair("answer", i, "multihop") for i in range(2)]
    picked = pick_pairs(rows, 5)  # type: ignore[arg-type]

    by_generator: dict[str, int] = {}
    for pair in picked:
        by_generator[pair.generator] = by_generator.get(pair.generator, 0) + 1
    assert by_generator == {"cloze": 5, "multihop": 2}


def test_a_limit_never_drops_the_control_half() -> None:
    """The control half survives — and now it does so by itself.

    Every generator produces items of EXACTLY one half, so the generators being
    represented entails the halves being represented. A separate round over the
    halves is unnecessary and harmful: there are two control generators against
    eight ordinary ones, and such a round would hand them two thirds of the
    sample.
    """
    rows = [
        _Pair("answer", i, generator)
        for generator in ("cloze", "mcq", "multihop", "tiered")
        for i in range(20)
    ]
    rows += [_Pair("abstain", i, "unanswerable") for i in range(20)]
    rows += [_Pair("correct_premise", i, "false_premise") for i in range(20)]
    picked = pick_pairs(rows, 4)  # type: ignore[arg-type]

    halves = {pair.expected_behavior for pair in picked}
    assert halves == {"answer", "abstain", "correct_premise"}


def test_the_control_half_does_not_swallow_the_sample() -> None:
    """A skew the other way is the same trouble.

    The earlier round over the halves gave two control generators as much room
    as eight ordinary ones: with a limit of ten questions, seven went on
    checking silence, and half the skills were not measured at all.
    """
    rows = [
        _Pair("answer", i, generator)
        for generator in ("a", "b", "c", "d", "e", "f", "g", "h")
        for i in range(20)
    ]
    rows += [_Pair("abstain", i, "unanswerable") for i in range(20)]
    rows += [_Pair("correct_premise", i, "false_premise") for i in range(20)]
    picked = pick_pairs(rows, 2)  # type: ignore[arg-type]

    control = sum(1 for p in picked if p.expected_behavior != "answer")
    assert len(picked) == 20
    assert control == 4, "the control ones take their share, not a third of the sample"


def test_a_limit_larger_than_the_set_returns_everything() -> None:
    rows = [_Pair("answer", i) for i in range(3)]
    assert pick_pairs(rows, 10) == rows  # type: ignore[arg-type]
    assert pick_pairs(rows, None) == rows  # type: ignore[arg-type]


def test_the_pick_is_deterministic() -> None:
    """Two runs with one limit must take the same items."""
    rows = [_Pair("answer", i) for i in range(10)] + [
        _Pair("abstain", i) for i in range(10)
    ]
    first = [p.id for p in pick_pairs(rows, 7)]  # type: ignore[arg-type]
    second = [p.id for p in pick_pairs(rows, 7)]  # type: ignore[arg-type]
    assert first == second


def test_one_half_alone_still_fills_the_limit() -> None:
    """While there are no control items, the limit works as it did before."""
    rows = [_Pair("answer", i) for i in range(10)]
    assert len(pick_pairs(rows, 4)) == 4  # type: ignore[arg-type]


def test_only_the_answer_sources_need_the_endpoint_to_write() -> None:
    """Chunks do not need the endpoint's prose, and there is no point waiting for it.

    The answer mode is set by the owner: on a `both` endpoint a request always
    triggers generation, even when only the chunks are wanted from it. It
    cannot be cancelled, but one token can be asked for — on a local model that
    is the difference between seconds and minutes.
    """
    assert ContextSource.ENDPOINT_FRAGMENTS not in _NEEDS_ANSWER
    assert ContextSource.ENDPOINT_ANSWER in _NEEDS_ANSWER
    assert ContextSource.ENDPOINT_BOTH in _NEEDS_ANSWER
    assert RETRIEVAL_ONLY_TOKENS >= 1, "the endpoint will not accept a zero"


def test_the_audit_shows_when_the_model_was_cut_off() -> None:
    """A cut-off at the token cap is visible in the record, not after the fact.

    A truncated answer is judged like any other, and the auditor needs to know
    that the model was not allowed to finish: this is a port of P11 from
    LiveTruth.
    """
    asked = Asked(
        answer="The port is",
        latency=0.2,
        system=_CLOSED_BOOK_SYSTEM,
        user="Which port?",
        retrieval={"retrieval_hit": None, "retrieval_rank": None, "retrieved": []},
        context_source=ContextSource.NONE,
        usage={"finish_reason": "length", "truncated": True, "length_retry": True},
    )
    record = audit_record(asked, Grade(Verdict.HALLUCINATE, ""), _settings())

    assert record["call"]["truncated"] is True
    assert record["call"]["length_retry"] is True


def test_pairs_without_a_generator_still_get_picked() -> None:
    """Old pairs carry no generator into the pick — the split survives that."""

    class _Old:
        def __init__(self, number: int) -> None:
            self.expected_behavior = "answer"
            self.id = f"old-{number}"

    rows = [_Old(i) for i in range(10)]
    assert len(pick_pairs(rows, 4)) == 4  # type: ignore[arg-type]
