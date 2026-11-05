"""The arms, building the context and the audit trail.

What is checked here is what the interpretation rests on: arms A and C differ
by exactly the presence of context, an arm's incompatibility with the
endpoint's mode is named before the run, and the prompt is stored next to the
answer.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

import pytest

from syft_benchmark.config import (
    ARM_LETTER,
    ContextMode,
    ContextSource,
    Settings,
    SpaceConfig,
    Verdict,
)
from syft_benchmark.llm import Provider
from syft_benchmark.runs import (
    Asked,
    Grade,
    Pool,
    RunCache,
    arm_blocker,
    audit_record,
    build_context,
    pick_pairs,
    with_context_prompt,
)
from syft_benchmark.runs.endpoint import RETRIEVAL_ONLY_TOKENS, check_retrieval
from syft_benchmark.runs.execute import CLOSED_BOOK_SYSTEM, aask_once

from fakes import FakePair

FRAGMENTS = [
    {
        "file_name": "setup.md",
        "score": 0.81,
        "content": "The port is published as 5442.",
    },
    {"file_name": "api.md", "score": 0.64, "content": "The hub stores metrics itself."},
    {"file_name": "old.md", "score": 0.41, "content": "The third chunk."},
]


def _ask(
    monkeypatch: pytest.MonkeyPatch,
    mode: ContextMode,
    *,
    source: ContextSource = ContextSource.ENDPOINT_FRAGMENTS,
    documents: list[dict[str, Any]] | None = None,
    pair: Any = None,
    **settings: Any,
) -> tuple[Asked, list[dict[str, Any]], list[tuple[str, str]]]:
    """One question through ``aask_once``: what was asked, of the node and the model.

    The node answers with ``documents`` (one port fragment by default) and a
    ready answer; the model answers "Port 5442.".
    """
    node: list[dict[str, Any]] = []
    model: list[tuple[str, str]] = []
    found = documents or [
        {
            "content": "The port is published as 5442.",
            "metadata": {"doc_id": "doc-1", "file_name": "setup.md"},
            "similarity_score": 0.81,
        }
    ]

    def endpoint(space: SpaceConfig, question: str, **kwargs: Any) -> Any:
        node.append(kwargs)
        return {"answer": "Port 5442.", "documents": found, "latency": 0.1}

    def chat(system: str, user: str, **kwargs: Any) -> Any:
        model.append((system, user))
        return "Port 5442.", {"finish_reason": "stop"}

    monkeypatch.setattr("syft_benchmark.runs.parallel.ask_endpoint", endpoint)
    monkeypatch.setattr("syft_benchmark.runs.parallel.chat", chat)
    conf = Settings(**settings)

    async def go() -> Asked:
        pool = Pool(conf)
        try:
            return await aask_once(
                pair or FakePair(),  # type: ignore[arg-type]
                mode,
                space=SpaceConfig(key="docs", url="http://node.local", endpoint="kb"),
                settings=conf,
                subject=Provider(
                    role="subject", url="http://localhost:11434", api_key="", model="m"
                ),
                source=source,
                pool=pool,
                cache=RunCache(),
            )
        finally:
            pool.close()

    return asyncio.run(go()), node, model


def test_every_arm_has_a_letter() -> None:
    """Every arm has a letter: the report speaks the methodology's language."""
    for mode in ContextMode:
        assert ARM_LETTER[mode.value] in {"A", "C"}


def test_arms_a_and_c_differ_only_by_context(monkeypatch: pytest.MonkeyPatch) -> None:
    """Arm C's instruction repeats the form of arm A's instruction.

    Let them diverge in style and the difference between the arms would measure
    the wording of the prompt, whereas it has to measure exactly the appearance
    of context.
    """
    for mode in (ContextMode.CLOSED_BOOK, ContextMode.MODEL_WITH_CONTEXT):
        _, _, model = _ask(monkeypatch, mode)
        ((system, _user),) = model
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
    """Raw mode does not compose an answer: arm C has no prose to mix in."""
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
    assert (
        arm_blocker(ContextMode.MODEL_WITH_CONTEXT, "", ContextSource.ENDPOINT_ANSWER)
        == ""
    )


def test_audit_keeps_prompts_and_the_judge_trail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A verdict can be rechecked: both prompts and the judge's answer are stored."""
    asked, _, _ = _ask(monkeypatch, ContextMode.MODEL_WITH_CONTEXT)
    verdict = Grade(
        Verdict.CORRECT,
        "matches the reference answer",
        judge_system="judge system",
        judge_user="judge user",
        judge_raw='{"correct": true}',
    )
    record = audit_record(asked, verdict, Settings())

    assert record["responder_prompt"].startswith("Question:")
    assert record["context_source"] == "endpoint_fragments"
    assert record["context"] == "[1] setup.md\nThe port is published as 5442."
    assert record["judge_raw"] == '{"correct": true}'


def test_audit_marks_verdicts_that_cost_no_model_call() -> None:
    """Matching a letter and spotting an abstention do not call the judge.

    That is a fact for the audit too.
    """
    asked = Asked(
        answer="I don't know",
        latency=0.1,
        system=CLOSED_BOOK_SYSTEM,
        user="Which port?",
        retrieval={"retrieval_hit": None, "retrieval_rank": None, "retrieved": []},
        context_source=ContextSource.NONE,
    )
    record = audit_record(
        asked, Grade(Verdict.ABSTAIN, "refused to answer"), Settings()
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
    off = Settings(audit_log=False)
    assert audit_record(asked, Grade(Verdict.CORRECT, ""), off) == {}


def test_run_records_the_settings_that_produced_it() -> None:
    """A configurable methodology has to leave a trail in every run."""
    conf = Settings(methodology_profile="strict", similarity_threshold=0.45)
    params = conf.measurement_params()
    assert params["profile"] == "strict"
    assert params["similarity_threshold"] == 0.45
    assert "context_source" in params


def _pair(behavior: str, number: int, generator: str = "cloze") -> FakePair:
    """A pair as the pick needs it: the labelling and the generator."""
    return FakePair(
        f"{behavior}-{generator}-{number}",
        expected_behavior=behavior,
        generator=generator,
    )


def test_every_generator_gets_its_share() -> None:
    """The pick's main property: the limit counts PER GENERATOR.

    A generator is a separate skill, not a share of the sample. An overall
    limit divided between them would, at a small value, simply throw some
    generators out: ten items over ten generators — and half were not checked
    at all, while the report called the result the model's accuracy.
    """
    rows = [
        _pair("answer", i, generator)
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
    rows = [_pair("answer", i, "cloze") for i in range(10)]
    rows += [_pair("answer", i, "multihop") for i in range(2)]
    picked = pick_pairs(rows, 5)  # type: ignore[arg-type]

    by_generator: dict[str, int] = {}
    for pair in picked:
        by_generator[pair.generator] = by_generator.get(pair.generator, 0) + 1
    assert by_generator == {"cloze": 5, "multihop": 2}


def test_a_limit_never_drops_the_control_half() -> None:
    """The control half survives by itself.

    Every generator produces items of EXACTLY one half, so the generators being
    represented entails the halves being represented. A separate round over the
    halves is unnecessary and harmful: there are two control generators against
    eight ordinary ones, and such a round would hand them two thirds of the
    sample.
    """
    rows = [
        _pair("answer", i, generator)
        for generator in ("cloze", "mcq", "multihop", "tiered")
        for i in range(20)
    ]
    rows += [_pair("abstain", i, "unanswerable") for i in range(20)]
    rows += [_pair("correct_premise", i, "false_premise") for i in range(20)]
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
        _pair("answer", i, generator)
        for generator in ("a", "b", "c", "d", "e", "f", "g", "h")
        for i in range(20)
    ]
    rows += [_pair("abstain", i, "unanswerable") for i in range(20)]
    rows += [_pair("correct_premise", i, "false_premise") for i in range(20)]
    picked = pick_pairs(rows, 2)  # type: ignore[arg-type]

    control = sum(1 for p in picked if p.expected_behavior != "answer")
    assert len(picked) == 20
    assert control == 4, "the control ones take their share, not a third of the sample"


def test_a_limit_larger_than_the_set_returns_everything() -> None:
    rows = [_pair("answer", i) for i in range(3)]
    assert pick_pairs(rows, 10) == rows  # type: ignore[arg-type]
    assert pick_pairs(rows, None) == rows  # type: ignore[arg-type]


def test_the_pick_is_deterministic() -> None:
    """Two runs with one limit must take the same items."""
    rows = [_pair("answer", i) for i in range(10)] + [
        _pair("abstain", i) for i in range(10)
    ]
    first = [p.id for p in pick_pairs(rows, 7)]  # type: ignore[arg-type]
    second = [p.id for p in pick_pairs(rows, 7)]  # type: ignore[arg-type]
    assert first == second


def test_one_half_alone_still_fills_the_limit() -> None:
    """While there are no control items, the limit works as it did before."""
    rows = [_pair("answer", i) for i in range(10)]
    assert len(pick_pairs(rows, 4)) == 4  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("source", "max_tokens"),
    [
        (ContextSource.ENDPOINT_FRAGMENTS, RETRIEVAL_ONLY_TOKENS),
        (ContextSource.ENDPOINT_ANSWER, None),
        (ContextSource.ENDPOINT_BOTH, None),
    ],
)
def test_only_the_answer_sources_need_the_endpoint_to_write(
    monkeypatch: pytest.MonkeyPatch, source: ContextSource, max_tokens: int | None
) -> None:
    """Chunks do not need the endpoint's prose, and there is no point waiting for it.

    The answer mode is set by the owner: on a `both` endpoint a request always
    triggers generation, even when only the chunks are wanted from it. It
    cannot be cancelled, but one token can be asked for — on a local model that
    is the difference between seconds and minutes.
    """
    _, node, _ = _ask(monkeypatch, ContextMode.MODEL_WITH_CONTEXT, source=source)
    assert [call.get("max_tokens") for call in node] == [max_tokens]
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
        system=CLOSED_BOOK_SYSTEM,
        user="Which port?",
        retrieval={"retrieval_hit": None, "retrieval_rank": None, "retrieved": []},
        context_source=ContextSource.NONE,
        usage={"finish_reason": "length", "truncated": True, "length_retry": True},
    )
    record = audit_record(asked, Grade(Verdict.HALLUCINATE, ""), Settings())

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


def test_the_chunk_ceiling_decides_what_the_model_sees(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Not a storage limit. The arm C prompt is built from the cut text.

    `check_retrieval` shortens each chunk and the context is assembled out of
    what it returned, so a chunk longer than the ceiling reaches the model
    truncated while the endpoint saw it whole. `chars` keeps the length before
    the cut.
    """
    long_text = "x" * 5000
    documents = [
        {
            "metadata": {"file_name": "long.md", "doc_id": "d1"},
            "similarity_score": 0.9,
            "content": long_text,
        }
    ]
    pair = SimpleNamespace(doc_id="d1", file_name="long.md", context="")

    retrieval = check_retrieval(documents, pair, max_chars=500)  # type: ignore[arg-type]
    (fragment,) = retrieval["retrieved"]
    assert len(fragment["content"]) == 500
    assert fragment["chars"] == 5000

    whole = check_retrieval(documents, pair, max_chars=20000)  # type: ignore[arg-type]
    assert len(whole["retrieved"][0]["content"]) == 5000

    # And the same number reaches the prompt, which is the point of it.
    _, _, model = _ask(
        monkeypatch,
        ContextMode.MODEL_WITH_CONTEXT,
        documents=documents,
        pair=FakePair(doc_id="d1", file_name="long.md", context=""),
        fragment_max_chars=500,
    )
    ((_system, user),) = model
    assert user.count("x") == 500


def test_only_context_docs_of_what_was_found_reach_the_prompt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Five chunks found, three mixed in — and the other two are not a miss.

    `retrieval_top_k` and `context_docs` are two different numbers: everything
    found is kept, only the top of it is shown to the model.
    """
    documents = [
        {
            "metadata": {"file_name": f"f{number}.md", "doc_id": f"d{number}"},
            "similarity_score": 0.9 - number / 100,
            "content": f"fragment number {number}",
        }
        for number in range(1, 6)
    ]
    asked, _, model = _ask(
        monkeypatch,
        ContextMode.MODEL_WITH_CONTEXT,
        documents=documents,
        pair=FakePair(doc_id="d4", file_name="f4.md", context=""),
        context_docs=3,
    )
    assert len(asked.retrieval["retrieved"]) == 5
    assert asked.retrieval["retrieval_rank"] == 4
    ((_system, user),) = model
    assert "fragment number 3" in user
    assert "fragment number 4" not in user
