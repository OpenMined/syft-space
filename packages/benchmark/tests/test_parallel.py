"""The parallel progress of a run and the cache of repeated calls.

What is tested is what all of this was set up for: a question goes to RAG once for
all the models under test and all the blocks, an answer at zero temperature is not
requested twice, waits add up into a batch, and a streak of failures ends an arm
instead of being paid for in hours.
"""

from __future__ import annotations

import asyncio
import pathlib
import time
from typing import Any

from syft_benchmark.config import ContextMode, ContextSource, Settings, SpaceConfig
from syft_benchmark.llm import Provider
from syft_benchmark.runs import Pool, Progress, RunCache
from syft_benchmark.runs.execute import aask_once

SPACE = SpaceConfig(key="docs", url="http://node.local", endpoint="kb")


def _settings(**kwargs: object) -> Settings:
    return Settings(**kwargs)  # type: ignore[arg-type]


def _provider(model: str) -> Provider:
    return Provider(
        role="subject", url="http://localhost:11434", api_key="", model=model
    )


class _Pair:
    """An item in the volume a question needs."""

    def __init__(self, number: int = 1) -> None:
        self.id = f"pair-{number}"
        self.question = f"What port does rig {number} use?"
        self.answer = "5442"
        self.context = "The port is published as 5442."
        self.task_type = "open"
        self.expected_behavior = "answer"
        self.generator = "cloze"
        self.meta: dict[str, Any] = {}
        self.doc_id = "doc-1"
        self.file_name = "setup.md"


def _outcome(answer: str = "Port 5442.") -> dict[str, Any]:
    return {
        "answer": answer,
        "documents": [
            {
                "content": "The port is published as 5442.",
                "metadata": {"doc_id": "doc-1", "file_name": "setup.md"},
                "similarity_score": 0.81,
            }
        ],
        "latency": 0.1,
        "failed": False,
    }


class _Node:
    """An endpoint that counts how many times it was actually asked."""

    def __init__(self, *, delay: float = 0.0) -> None:
        self.calls: list[dict[str, Any]] = []
        self.delay = delay

    def __call__(self, space: SpaceConfig, question: str, **kwargs: Any) -> Any:
        self.calls.append({"question": question, **kwargs})
        if self.delay:
            time.sleep(self.delay)
        return _outcome()


class _Model:
    """A model that counts its calls."""

    def __init__(self, *, delay: float = 0.0, answer: str = "Port 5442.") -> None:
        self.calls: list[tuple[str, str]] = []
        self.delay = delay
        self.answer = answer

    def __call__(self, system: str, user: str, **kwargs: Any) -> Any:
        self.calls.append((system, user))
        if self.delay:
            time.sleep(self.delay)
        return self.answer, {"finish_reason": "stop"}


def _run(coro: Any, settings: Settings) -> Any:
    async def go() -> Any:
        pool = Pool(settings)
        try:
            return await coro(pool)
        finally:
            pool.close()

    return asyncio.run(go())


# --- the endpoint cache ----------------------------------------------------


def test_one_question_costs_the_rag_one_call(monkeypatch: Any) -> None:
    """The main thing the cache exists for.

    The retrieval for a question is a property of the corpus, not of the model under
    test. Nine models in arm C meant nine identical trips to RAG for one and the
    same result, and on a node with a model on CPU every such trip costs minutes.
    """
    node = _Node()
    model = _Model()
    monkeypatch.setattr("syft_benchmark.runs.parallel.ask_endpoint", node)
    monkeypatch.setattr("syft_benchmark.runs.parallel.chat", model)

    conf = _settings(context_source=ContextSource.ENDPOINT_FRAGMENTS)
    cache = RunCache()
    pair = _Pair()

    async def ask_all(pool: Pool) -> None:
        await asyncio.gather(
            *(
                aask_once(
                    pair,  # type: ignore[arg-type]
                    ContextMode.MODEL_WITH_CONTEXT,
                    space=SPACE,
                    settings=conf,
                    subject=_provider(f"vendor/model-{i}"),
                    source=ContextSource.ENDPOINT_FRAGMENTS,
                    pool=pool,
                    cache=cache,
                )
                for i in range(9)
            )
        )

    _run(ask_all, conf)

    assert len(node.calls) == 1, "nine models — one question to the endpoint"
    assert len(model.calls) == 9, "while all nine models were asked"
    assert cache.savings.endpoint_reused == 8


def test_the_rag_is_asked_once_even_when_everyone_starts_together(
    monkeypatch: Any,
) -> None:
    """A dictionary saves those who arrive later, and they all start together.

    Without a single call for everyone waiting, the cache would miss exactly where
    it is needed most: nine tasks come to a question at the same time and all nine
    see an empty dictionary.
    """
    node = _Node(delay=0.05)
    model = _Model()
    monkeypatch.setattr("syft_benchmark.runs.parallel.ask_endpoint", node)
    monkeypatch.setattr("syft_benchmark.runs.parallel.chat", model)

    conf = _settings(endpoint_concurrency=8)
    cache = RunCache()
    pair = _Pair()

    async def ask_all(pool: Pool) -> None:
        await asyncio.gather(
            *(
                aask_once(
                    pair,  # type: ignore[arg-type]
                    ContextMode.MODEL_WITH_CONTEXT,
                    space=SPACE,
                    settings=conf,
                    subject=_provider(f"vendor/model-{i}"),
                    source=ContextSource.ENDPOINT_FRAGMENTS,
                    pool=pool,
                    cache=cache,
                )
                for i in range(8)
            )
        )

    _run(ask_all, conf)
    assert len(node.calls) == 1


def test_arm_b_fills_the_cache_for_arm_c(monkeypatch: Any) -> None:
    """Arm B has already been for this question — arm C has no reason to go.

    The endpoint answer carries both the prose and the chunks that were found. Arm C
    over chunks needs the second, and it already has it.
    """
    node = _Node()
    model = _Model()
    monkeypatch.setattr("syft_benchmark.runs.parallel.ask_endpoint", node)
    monkeypatch.setattr("syft_benchmark.runs.parallel.chat", model)

    conf = _settings()
    cache = RunCache()
    pair = _Pair()

    async def both_arms(pool: Pool) -> None:
        await aask_once(
            pair,  # type: ignore[arg-type]
            ContextMode.OPEN_BOOK,
            space=SPACE,
            settings=conf,
            subject=None,
            source=ContextSource.ENDPOINT_OWN,
            pool=pool,
            cache=cache,
        )
        await aask_once(
            pair,  # type: ignore[arg-type]
            ContextMode.MODEL_WITH_CONTEXT,
            space=SPACE,
            settings=conf,
            subject=_provider("vendor/model"),
            source=ContextSource.ENDPOINT_FRAGMENTS,
            pool=pool,
            cache=cache,
        )

    _run(both_arms, conf)
    assert len(node.calls) == 1
    assert node.calls[0].get("max_tokens") is None, "arm B asks for the whole prose"


def test_prose_is_fetched_when_the_cache_holds_only_retrieval(
    monkeypatch: Any,
) -> None:
    """The reverse order does not work that way, and that is no idle symmetry.

    A truncated call brings no prose: generation was asked for a single token. One
    has to go for it again — otherwise arm C over the endpoint finished answer would
    be measuring the model credulity towards an empty string.
    """
    node = _Node()
    model = _Model()
    monkeypatch.setattr("syft_benchmark.runs.parallel.ask_endpoint", node)
    monkeypatch.setattr("syft_benchmark.runs.parallel.chat", model)

    conf = _settings()
    cache = RunCache()
    pair = _Pair()

    async def fragments_then_prose(pool: Pool) -> None:
        for source in (
            ContextSource.ENDPOINT_FRAGMENTS,
            ContextSource.ENDPOINT_ANSWER,
        ):
            await aask_once(
                pair,  # type: ignore[arg-type]
                ContextMode.MODEL_WITH_CONTEXT,
                space=SPACE,
                settings=conf,
                subject=_provider("vendor/model"),
                source=source,
                pool=pool,
                cache=cache,
            )

    _run(fragments_then_prose, conf)
    assert len(node.calls) == 2
    assert node.calls[0]["max_tokens"] == 1, "chunks do not need the prose"
    assert node.calls[1]["max_tokens"] is None


def test_a_broken_node_is_not_remembered(monkeypatch: Any) -> None:
    """A failed call is not recorded.

    A node reboot in the middle of a run must not turn into one and the same failure
    across all nine models: that is no longer a measurement but a replicated accident.
    """
    calls: list[str] = []

    def flaky(space: SpaceConfig, question: str, **kwargs: Any) -> dict[str, Any]:
        calls.append(question)
        if len(calls) == 1:
            return {
                "answer": "ERROR: ConnectError",
                "documents": [],
                "latency": 0.1,
                "failed": True,
            }
        return _outcome()

    monkeypatch.setattr("syft_benchmark.runs.parallel.ask_endpoint", flaky)
    conf = _settings()
    cache = RunCache()

    async def twice(pool: Pool) -> list[dict[str, Any]]:
        first = await cache.endpoint(
            SPACE, "question", need_prose=True, pool=pool, settings=conf
        )
        second = await cache.endpoint(
            SPACE, "question", need_prose=True, pool=pool, settings=conf
        )
        return [first, second]

    first, second = _run(twice, conf)
    assert first["failed"] is True
    assert second["failed"] is False, "a failure must not have settled in the cache"


def test_the_cache_can_be_switched_off(monkeypatch: Any) -> None:
    """Measuring the spread of repeated calls itself is a legitimate task."""
    node = _Node()
    monkeypatch.setattr("syft_benchmark.runs.parallel.ask_endpoint", node)
    conf = _settings()
    cache = RunCache(enabled=False)

    async def twice(pool: Pool) -> None:
        for _ in range(2):
            await cache.endpoint(
                SPACE, "question", need_prose=True, pool=pool, settings=conf
            )

    _run(twice, conf)
    assert len(node.calls) == 2


# --- the model answer cache ------------------------------------------------


def test_the_same_prompt_is_not_asked_twice(monkeypatch: Any) -> None:
    """At zero temperature a repeat measures nothing.

    This is what the blocks live on: ``denial_loop`` starts its pressure from exactly
    the first answer the direct test has already obtained.
    """
    model = _Model()
    monkeypatch.setattr("syft_benchmark.runs.parallel.chat", model)
    conf = _settings()
    cache = RunCache()
    subject = _provider("vendor/model")

    async def twice(pool: Pool) -> None:
        for _ in range(2):
            await cache.answer(subject, "system", "question", pool=pool, settings=conf)

    _run(twice, conf)
    assert len(model.calls) == 1
    assert cache.savings.model_reused == 1


def test_a_different_model_is_a_different_answer(monkeypatch: Any) -> None:
    """The key remembers who was asked: otherwise one model would be measured."""
    model = _Model()
    monkeypatch.setattr("syft_benchmark.runs.parallel.chat", model)
    conf = _settings()
    cache = RunCache()

    async def two_models(pool: Pool) -> None:
        for name in ("vendor/a", "vendor/b"):
            await cache.answer(
                _provider(name), "system", "question", pool=pool, settings=conf
            )

    _run(two_models, conf)
    assert len(model.calls) == 2


def test_context_makes_the_prompt_another_question(monkeypatch: Any) -> None:
    """The answer to a question with material is not the same as without it.

    So the key is the whole prompt rather than the question: otherwise arm C would
    get the arm A answer and the difference between the arms would collapse to zero.
    """
    node = _Node()
    model = _Model()
    monkeypatch.setattr("syft_benchmark.runs.parallel.ask_endpoint", node)
    monkeypatch.setattr("syft_benchmark.runs.parallel.chat", model)

    conf = _settings()
    cache = RunCache()
    pair = _Pair()
    subject = _provider("vendor/model")

    async def arms_a_and_c(pool: Pool) -> None:
        await aask_once(
            pair,  # type: ignore[arg-type]
            ContextMode.CLOSED_BOOK,
            space=SPACE,
            settings=conf,
            subject=subject,
            source=ContextSource.NONE,
            pool=pool,
            cache=cache,
        )
        await aask_once(
            pair,  # type: ignore[arg-type]
            ContextMode.MODEL_WITH_CONTEXT,
            space=SPACE,
            settings=conf,
            subject=subject,
            source=ContextSource.ENDPOINT_FRAGMENTS,
            pool=pool,
            cache=cache,
        )

    _run(arms_a_and_c, conf)
    assert len(model.calls) == 2, "arm C must not get the arm A answer"
    assert "Material:" in model.calls[1][1]


# --- the lanes -------------------------------------------------------------


def test_waiting_is_done_in_parallel(monkeypatch: Any) -> None:
    """Exactly what made a run overrun a day.

    Eight questions of a tenth of a second each: sequentially that is eight tenths,
    in parallel roughly one.
    """
    model = _Model(delay=0.1)
    monkeypatch.setattr("syft_benchmark.runs.parallel.chat", model)
    conf = _settings(concurrency=8)
    cache = RunCache()

    async def eight(pool: Pool) -> None:
        await asyncio.gather(
            *(
                cache.answer(
                    _provider(f"vendor/m{i}"),
                    "system",
                    f"question {i}",
                    pool=pool,
                    settings=conf,
                )
                for i in range(8)
            )
        )

    started = time.perf_counter()
    _run(eight, conf)
    elapsed = time.perf_counter() - started

    assert len(model.calls) == 8
    assert elapsed < 0.5, f"the calls went one after another: {elapsed:.2f}s"


def test_the_node_keeps_its_own_narrower_lane(monkeypatch: Any) -> None:
    """A queue to a foreign node does not speed it up but accumulates timeouts.

    So there are two lanes: a model provider is built for dozens of simultaneous
    requests, the endpoint under test is one node with one model.
    """
    inflight = 0
    peak = 0

    def counting(space: SpaceConfig, question: str, **kwargs: Any) -> dict[str, Any]:
        nonlocal inflight, peak
        inflight += 1
        peak = max(peak, inflight)
        time.sleep(0.05)
        inflight -= 1
        return _outcome()

    monkeypatch.setattr("syft_benchmark.runs.parallel.ask_endpoint", counting)
    conf = _settings(concurrency=16, endpoint_concurrency=2)
    cache = RunCache(enabled=False)

    async def many(pool: Pool) -> None:
        await asyncio.gather(
            *(
                cache.endpoint(
                    SPACE, f"question {i}", need_prose=True, pool=pool, settings=conf
                )
                for i in range(8)
            )
        )

    _run(many, conf)
    assert peak <= 2, f"{peak} requests went to the node at once, two allowed"


# --- when it is time to stop -----------------------------------------------


def test_a_streak_of_failures_stops_the_arm() -> None:
    """A node that is down must not be paid for in hours and a table of failures."""
    progress = Progress(total=100, label="trial", give_up_after=5)
    for _ in range(5):
        progress.step(failed=True)
    assert progress.stopped
    assert "in a row" in progress.fatal


def test_a_single_failure_does_not_stop_anything() -> None:
    """A single failure can be a one-off: too long a prompt, one pair."""
    progress = Progress(total=100, label="trial", give_up_after=5)
    for _ in range(4):
        progress.step(failed=True)
    progress.step()
    progress.step(failed=True)
    assert not progress.stopped
    assert progress.failures == 5


def test_a_refusal_stops_the_pass_at_once_not_in_twenty() -> None:
    """A streak is evidence; a refusal is a sentence already passed.

    The provider has said the name, the key or the money is wrong. Nothing in
    the remaining questions changes any of those, and each one is a call paid
    for to hear the same thing again.
    """
    progress = Progress(total=100, label="trial", give_up_after=20)
    progress.step(failed=True, refused="qwen/qwen3.6-plus")
    assert progress.stopped
    assert progress.refused == "qwen/qwen3.6-plus"
    assert "refused" in progress.fatal


def test_a_refusal_stops_a_pass_shorter_than_the_threshold() -> None:
    """The case the streak cannot reach even in principle.

    The threshold counts within one pass and starts again at the next. A trial
    run's pass is shorter than the threshold — so on the very run meant to be a
    quick probe the streak never fires, and eighteen minutes of passes each ask
    their whole set to be told the same 400.
    """
    progress = Progress(total=16, label="trial", give_up_after=20)
    for _ in range(15):
        progress.step(failed=True)
    assert not progress.stopped, "the streak cannot fire on a pass this short"

    progress = Progress(total=16, label="trial", give_up_after=20)
    progress.step(failed=True, refused="qwen/qwen3.6-plus")
    assert progress.stopped


def test_the_guard_can_be_switched_off() -> None:
    """Zero means "do not stop": a run happens on a knowingly hostile rig too."""
    progress = Progress(total=10, label="trial", give_up_after=0)
    for _ in range(10):
        progress.step(failed=True)
    assert not progress.stopped

    # A refusal goes off with it. The setting names a streak and a refusal is
    # not one, but what the zero turns off is giving up early, and the owner
    # who set it said so about this rig.
    progress.step(failed=True, refused="qwen/qwen3.6-plus")
    assert not progress.stopped
    assert not progress.refused


# --- the whole run ---------------------------------------------------------


class _Stand:
    """A rig with the node, the models and the database substituted.

    It counts not reports but calls: the question to the run is one and the same,
    and the whole point of the check is how many times it actually went outside.
    """

    def __init__(self, monkeypatch: Any, pairs: int = 6) -> None:
        import syft_benchmark.runs.blocks as blocks
        import syft_benchmark.runs.execute as execute
        import syft_benchmark.runs.judge as judge
        import syft_benchmark.runs.parallel as parallel

        self.node = _Node()
        self.pairs = [_Pair(i) for i in range(pairs)]
        self.saved: list[Any] = []
        self.answers: list[tuple[str, str]] = []
        self.judged = 0
        self.answer = "Port 5442."

        def chat(system: str, user: str, **kwargs: Any) -> Any:
            if "Is the model answer correct" in user:
                self.judged += 1
                return '{"correct": true, "reasoning": "ok"}', {}
            if "Is the answer grounded" in user:
                return '{"grounded": true, "reasoning": "ok"}', {}
            self.answers.append((system, user))
            return self.answer, {"finish_reason": "stop"}

        stand = self

        class _Session:
            def add(self, obj: Any) -> None:
                stand.saved.append(obj)

        class _Scope:
            def __enter__(self) -> Any:
                return _Session()

            def __exit__(self, *exc: Any) -> bool:
                return False

        monkeypatch.setattr(parallel, "ask_endpoint", self.node)
        monkeypatch.setattr(parallel, "chat", chat)
        monkeypatch.setattr(execute, "chat", chat)
        monkeypatch.setattr(judge, "chat", chat)
        monkeypatch.setattr(blocks, "chat", chat)
        monkeypatch.setattr(execute, "endpoint_mode", lambda space: "both")
        monkeypatch.setattr(
            execute, "_active_pairs", lambda key, limit, conf=None: self.pairs
        )
        monkeypatch.setattr(execute, "session_scope", lambda *a, **k: _Scope())


def test_the_rag_is_asked_once_per_question_across_the_whole_run(
    monkeypatch: Any,
) -> None:
    """Exactly what made a run overrun a day.

    Three models, arms B and C, the direct test and the repeats: previously every
    combination went to the node for its own copy of one and the same retrieval. Now
    the question goes there once for the whole launch.
    """
    from syft_benchmark.config import EvalBlock
    from syft_benchmark.runs import run_pass

    stand = _Stand(monkeypatch, pairs=6)
    conf = _settings(
        concurrency=8,
        endpoint_concurrency=2,
        context_source=ContextSource.ENDPOINT_FRAGMENTS,
        monte_carlo_temperatures=[0.1],
        monte_carlo_trials=1,
    )
    cache = RunCache()
    judges = [
        Provider(
            role="judge",
            url="http://localhost:11434",
            api_key="",
            model="judge/one",
        )
    ]
    subjects = [_provider(f"vendor-{i}/m") for i in range(3)]

    run_pass(
        SPACE,
        ContextMode.OPEN_BOOK,
        settings=conf,
        subject=None,
        block=EvalBlock.DIRECT,
        judges=judges,
        cache=cache,
    )
    for block in (EvalBlock.DIRECT, EvalBlock.DENIAL_LOOP, EvalBlock.MONTE_CARLO):
        for subject in subjects:
            run_pass(
                SPACE,
                ContextMode.MODEL_WITH_CONTEXT,
                settings=conf,
                subject=subject,
                block=block,
                judges=judges,
                cache=cache,
            )

    assert len(stand.node.calls) == len(stand.pairs), (
        f"{len(stand.node.calls)} requests went to the node instead of "
        f"{len(stand.pairs)} — one per question"
    )


def test_pressure_starts_from_the_answer_direct_already_got(monkeypatch: Any) -> None:
    """denial_loop does not re-ask the first answer — it already has it.

    An answer at zero temperature is the same for the same prompt, and there is no
    reason to pay for it a second time.
    """
    from syft_benchmark.config import EvalBlock
    from syft_benchmark.runs import run_pass

    stand = _Stand(monkeypatch, pairs=4)
    conf = _settings(concurrency=4, denial_rounds=1)
    cache = RunCache()
    judges = [
        Provider(
            role="judge",
            url="http://localhost:11434",
            api_key="",
            model="judge/one",
        )
    ]
    subject = _provider("vendor/m")

    run_pass(
        SPACE,
        ContextMode.CLOSED_BOOK,
        settings=conf,
        subject=subject,
        block=EvalBlock.DIRECT,
        judges=judges,
        cache=cache,
    )
    first = len(stand.answers)
    assert first == len(stand.pairs)

    run_pass(
        SPACE,
        ContextMode.CLOSED_BOOK,
        settings=conf,
        subject=subject,
        block=EvalBlock.DENIAL_LOOP,
        judges=judges,
        cache=cache,
    )
    added = len(stand.answers) - first

    # One round of pressure per pair — and not a single repeated first question:
    # the rounds go in a dialogue, and the first answer is taken from what was recorded.
    assert added == len(stand.pairs), f"extra calls: {added}"
    assert cache.savings.model_reused >= len(stand.pairs)


# --- resuming --------------------------------------------------------------


def test_resume_asks_only_what_is_missing(monkeypatch: Any) -> None:
    """An interrupted measurement continues rather than starting over.

    A run goes for hours: the node rebooted, the balance ran out, a human pressed
    Ctrl-C. What is expensive in it is not what was recorded but what will have to
    be asked again.
    """
    import syft_benchmark.runs.execute as execute
    from syft_benchmark.config import EvalBlock
    from syft_benchmark.runs import run_pass

    stand = _Stand(monkeypatch, pairs=6)
    judge = Provider(
        role="judge", url="http://localhost:11434", api_key="", model="judge/one"
    )
    # The previous attempt managed to get through the first four items.
    monkeypatch.setattr(
        execute,
        "done_units",
        lambda *a, **k: {"judge/one": {p.id for p in stand.pairs[:4]}},
    )

    reports = run_pass(
        SPACE,
        ContextMode.CLOSED_BOOK,
        settings=_settings(concurrency=4),
        subject=_provider("vendor/m"),
        block=EvalBlock.DIRECT,
        judges=[judge],
        cache=RunCache(),
        resume=True,
    )

    assert len(stand.answers) == 2, "only the two not done were asked"
    assert reports[0].asked == 2
    assert reports[0].resumed == 4
    assert any("resumed" in note for note in reports[0].notes)


def test_resume_still_asks_a_question_one_judge_of_two_has_not_graded(
    monkeypatch: Any,
) -> None:
    """The answer is one for the whole panel, and for one judge it has to be obtained.

    The second judge, though, does not reissue its verdict: it already has one.
    """
    import syft_benchmark.runs.execute as execute
    from syft_benchmark.config import EvalBlock
    from syft_benchmark.runs import run_pass

    stand = _Stand(monkeypatch, pairs=3)
    judges = [
        Provider(role="judge", url="http://localhost:11434", api_key="", model=name)
        for name in ("judge/a", "judge/b")
    ]
    monkeypatch.setattr(
        execute,
        "done_units",
        lambda *a, **k: {"judge/a": {p.id for p in stand.pairs}},
    )

    reports = run_pass(
        SPACE,
        ContextMode.CLOSED_BOOK,
        settings=_settings(concurrency=4),
        subject=_provider("vendor/m"),
        block=EvalBlock.DIRECT,
        judges=judges,
        cache=RunCache(),
        resume=True,
    )

    assert len(stand.answers) == 3, "asked: the second judge needs the questions"
    by_judge = {r.judge: r for r in reports}
    assert by_judge["judge/a"].asked == 0
    assert by_judge["judge/a"].resumed == 3
    assert by_judge["judge/b"].asked == 3
    assert stand.judged == 3, "the first judge does not reissue its verdict"


def test_a_finished_pass_is_not_reopened(monkeypatch: Any) -> None:
    """Everything done — no run is created at all.

    An empty Run in the database would look like completed work, and the report will
    find the previous verdicts without it anyway: it counts by the latest verdict per
    question, not by the last run.
    """
    import syft_benchmark.runs.execute as execute
    from syft_benchmark.config import EvalBlock
    from syft_benchmark.runs import run_pass

    stand = _Stand(monkeypatch, pairs=3)
    judge = Provider(
        role="judge", url="http://localhost:11434", api_key="", model="judge/one"
    )
    monkeypatch.setattr(
        execute,
        "done_units",
        lambda *a, **k: {"judge/one": {p.id for p in stand.pairs}},
    )

    reports = run_pass(
        SPACE,
        ContextMode.CLOSED_BOOK,
        settings=_settings(),
        subject=_provider("vendor/m"),
        block=EvalBlock.DIRECT,
        judges=[judge],
        cache=RunCache(),
        resume=True,
    )

    assert stand.answers == []
    assert stand.saved == [], "not a single Run and not a single Result"
    assert reports[0].run_id == ""
    assert reports[0].resumed == 3


def test_without_the_flag_nothing_is_skipped(monkeypatch: Any) -> None:
    """A repeat launch without --resume measures afresh, and that is the default.

    Otherwise a second launch in a day would silently measure nothing, and a human
    would see yesterday numbers as today.
    """
    import syft_benchmark.runs.execute as execute
    from syft_benchmark.config import EvalBlock
    from syft_benchmark.runs import run_pass

    stand = _Stand(monkeypatch, pairs=3)
    asked_for_done = False

    def never_called(*args: Any, **kwargs: Any) -> dict[str, set[str]]:
        nonlocal asked_for_done
        asked_for_done = True
        return {}

    monkeypatch.setattr(execute, "done_units", never_called)

    run_pass(
        SPACE,
        ContextMode.CLOSED_BOOK,
        settings=_settings(),
        subject=_provider("vendor/m"),
        block=EvalBlock.DIRECT,
        judges=[
            Provider(
                role="judge", url="http://localhost:11434", api_key="", model="j/one"
            )
        ],
        cache=RunCache(),
    )

    assert not asked_for_done, "the database is not even asked about what is done"
    assert len(stand.answers) == 3


# --- deferred judging ------------------------------------------------------


def test_deferred_judging_records_the_answer_without_a_verdict(
    monkeypatch: Any,
) -> None:
    """Answers are collected by machine, verdicts issued by a console judge later.

    The judge is not called even once — that is the whole point: the judge line drops
    out of the bill, and a subscription takes its place.
    """
    from syft_benchmark.config import EvalBlock, Verdict
    from syft_benchmark.runs import run_pass

    stand = _Stand(monkeypatch, pairs=4)
    reports = run_pass(
        SPACE,
        ContextMode.CLOSED_BOOK,
        settings=_settings(concurrency=4),
        subject=_provider("vendor/m"),
        block=EvalBlock.DIRECT,
        judges=[
            Provider(
                role="judge", url="http://localhost:11434", api_key="", model="j/one"
            )
        ],
        cache=RunCache(),
        defer_judging=True,
    )

    assert len(stand.answers) == 4, "the model was asked"
    assert stand.judged == 0, "while the judge was not called even once"
    assert reports[0].deferred == 4
    verdicts = {r.verdict for r in stand.saved if hasattr(r, "verdict")}
    assert verdicts == {Verdict.PENDING.value}


def test_a_deferred_run_still_settles_what_costs_no_judge(monkeypatch: Any) -> None:
    """Deferring what is free means doing the work twice.

    A recognised abstention needs no judge — and its verdict is issued at once rather
    than left as a hole in the report.
    """
    from syft_benchmark.config import EvalBlock, Verdict
    from syft_benchmark.runs import run_pass

    stand = _Stand(monkeypatch, pairs=3)
    stand.answer = "I don't know"

    run_pass(
        SPACE,
        ContextMode.CLOSED_BOOK,
        settings=_settings(concurrency=4),
        subject=_provider("vendor/m"),
        block=EvalBlock.DIRECT,
        judges=[
            Provider(
                role="judge", url="http://localhost:11434", api_key="", model="j/one"
            )
        ],
        cache=RunCache(),
        defer_judging=True,
    )

    verdicts = {r.verdict for r in stand.saved if hasattr(r, "verdict")}
    assert verdicts == {Verdict.ABSTAIN.value}
    assert stand.judged == 0


# --- one set of questions for everyone -------------------------------------


def test_every_subject_model_is_asked_the_same_questions(monkeypatch: Any) -> None:
    """Models can only be compared on one set of questions.

    The selection is applied anew for every run — one run per arm, block and model
    under test — and if it were random or unstable, the difference between models
    would include the difference between questions with nothing to show for it.
    """
    from syft_benchmark.config import EvalBlock
    from syft_benchmark.runs import run_pass

    stand = _Stand(monkeypatch, pairs=12)
    judge = Provider(
        role="judge", url="http://localhost:11434", api_key="", model="j/one"
    )

    asked: dict[str, list[str]] = {}
    for name in ("vendor-a/m", "vendor-b/m", "vendor-c/m"):
        stand.answers.clear()
        run_pass(
            SPACE,
            ContextMode.CLOSED_BOOK,
            settings=_settings(concurrency=4),
            subject=_provider(name),
            block=EvalBlock.DIRECT,
            judges=[judge],
            cache=RunCache(),
        )
        asked[name] = sorted(user for _system, user in stand.answers)

    first = asked["vendor-a/m"]
    assert len(first) == 12
    assert all(
        questions == first for questions in asked.values()
    ), "the models got different questions"


def test_the_selection_is_deterministic() -> None:
    """The same set and the same limit — the same questions.

    Otherwise a repeat run would measure a different set, and the difference in
    numbers between days would mean not the behaviour of the model but a coin toss.
    """
    from syft_benchmark.runs import pick_pairs

    rows = [_Pair(i) for i in range(20)]
    for pair in rows[:10]:
        pair.generator = "mcq"

    first = [p.id for p in pick_pairs(rows, 3)]  # type: ignore[arg-type]
    second = [p.id for p in pick_pairs(rows, 3)]  # type: ignore[arg-type]
    assert first == second


def test_the_database_order_is_total() -> None:
    """The order decides which items the limit takes.

    If two items had equal timestamps, the database would be free to return them in
    a different order to different queries — and the query is made anew for every
    run, that is, for every model under test. The identifier in the sort makes the
    order total, and that possibility disappears.
    """
    import re

    source = pathlib.Path("src/syft_benchmark/runs/execute.py").read_text(
        encoding="utf-8"
    )
    order_by = re.search(r"\.order_by\(QaPair\.([^)]+)\)", source)
    assert order_by is not None
    assert "created_at" in order_by.group(1)
    assert "id" in order_by.group(1), "the order is partial: time without a tiebreak"
