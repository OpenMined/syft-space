"""The parallel progress of a run and a cache of what has already been asked.

A port of the design of `eval_arena/base.py` from LiveTruth, brought to three
arms and a panel of judges. Two different troubles of one run are solved here.

**The first is waiting.** The benchmark computes almost nothing: its time is an
open socket to the model under test, to the judge, to the endpoint. A sequential
walk pays each such wait once, and on a live set the count runs into days: a
measurement interrupted at fifteen percent after seventeen hours is exactly that
case. Waits add up, so they are kept in flight in a batch rather than one at a time.

There are two lanes, and that is not configuration for its own sake. An external
model provider is built for dozens of simultaneous requests; the endpoint under
test is one foreign node with one model, and a queue to it does not speed it up
but accumulates timeouts. One number for both would mean choosing between an idle
provider and a swamped node.

**The second is repeats.** One and the same work is ordered many times over, and
that is visible directly in the design of the measurement:

  * arm C puts the same question to the endpoint for the sake of the same
    retrieval — once per model under test. Nine models mean nine identical trips
    to RAG, and `denial_loop` and `monte_carlo` multiply them again, because each
    block starts from a question of its own;
  * arm B has already been to the endpoint with the same question before them;
  * a model first answer at zero temperature is the same in every block:
    `denial_loop` starts its pressure from exactly the answer the direct test has
    already obtained.

The retrieval for one question is a property of the corpus, not of the model under
test, and it cannot change depending on who is shown it afterwards. Which means
there is nothing to ask a second time.

The cache does not merely "look in a dictionary": nine tasks start at once and all
nine would miss. The first asker creates the call, the rest wait for its result —
and then even at the start the question goes out once.

The responsibilities are split deliberately: the blocking code of the run stays
blocking and the only one, while parallelism lives outside — a call goes off to a
thread and the event loop gets on with the next. There are no async twins of
``chat``, of judging or of the blocks, and there must not be: two copies of the
delicate logic of retries and truncations will diverge on the very first edit.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from functools import partial
from typing import Any, TypeVar

from loguru import logger

from syft_benchmark.config import Settings, SpaceConfig
from syft_benchmark.llm import Provider, chat
from syft_benchmark.runs.endpoint import RETRIEVAL_ONLY_TOKENS, ask_endpoint

T = TypeVar("T")

# After how many finished tasks to say how many are left. A run goes for hours,
# and a silent console is indistinguishable from a hung one.
_PROGRESS_EVERY = 10

# How many database writes to keep in flight. The database is ours and close, but
# it is still a socket: waiting for it right in the loop means stopping, for that
# time, all the other answers that are in flight at that moment.
_STORAGE_LANE = 4


class Pool:
    """How many calls are kept in flight — separately by addressee.

    The holder of the worker threads and of the two lanes. It lives for exactly one
    event loop: the semaphores bind to the loop on the first wait, and a pool that
    outlived ``asyncio.run`` would fail on the next run.
    """

    def __init__(self, settings: Settings) -> None:
        self.model_limit = settings.concurrency
        self.endpoint_limit = settings.endpoint_concurrency
        self._model = asyncio.Semaphore(self.model_limit)
        self._endpoint = asyncio.Semaphore(self.endpoint_limit)
        self._storage = asyncio.Semaphore(_STORAGE_LANE)
        # There are exactly as many threads as calls are allowed in flight: the
        # asyncio default is computed from the number of cores and has nothing to do
        # with the number of sockets — with a generous lane it would become a second,
        # undeclared ceiling.
        self._workers = ThreadPoolExecutor(
            max_workers=self.model_limit + self.endpoint_limit + _STORAGE_LANE,
            thread_name_prefix="bench",
        )

    def close(self) -> None:
        self._workers.shutdown(wait=False)

    async def to_model(self, fn: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        """Make a call to a model — the one under test or a judge."""
        return await self._offload(self._model, fn, *args, **kwargs)

    async def to_endpoint(self, fn: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        """Make a call to the endpoint under test."""
        return await self._offload(self._endpoint, fn, *args, **kwargs)

    async def to_storage(self, fn: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        """Write a result to the database.

        The lane is separate and narrow: writing must not take room from the calls
        the run exists for, but there is no reason to hold the loop on it either.
        """
        return await self._offload(self._storage, fn, *args, **kwargs)

    async def _offload(
        self, gate: asyncio.Semaphore, fn: Callable[..., T], *args: Any, **kwargs: Any
    ) -> T:
        async with gate:
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(
                self._workers, partial(fn, *args, **kwargs)
            )


@dataclass(slots=True)
class Savings:
    """How many calls the cache did not make. Goes into the run log."""

    endpoint_asked: int = 0
    endpoint_reused: int = 0
    model_asked: int = 0
    model_reused: int = 0

    def line(self) -> str:
        return (
            f"endpoint: {self.endpoint_asked} requests, "
            f"{self.endpoint_reused} reused; "
            f"models: {self.model_asked} calls, "
            f"{self.model_reused} reused"
        )


@dataclass(slots=True)
class _Cached:
    """The endpoint answer and what is in it."""

    outcome: dict[str, Any]
    prose: bool


class RunCache:
    """What has already been asked and is therefore not asked again.

    It lives longer than one run: one object is passed into all the arms, blocks and
    models of a single launch, and for that reason it holds nothing bound to the
    event loop except tasks that finish within that loop.

    Switched off by the ``reuse_answers`` setting: measuring the spread of repeated
    calls itself is a legitimate task, and the cache gets directly in its way.
    """

    def __init__(self, *, enabled: bool = True) -> None:
        self.enabled = enabled
        self.savings = Savings()
        self._endpoint: dict[tuple[str, str], _Cached] = {}
        self._answers: dict[tuple[str, str, str, str], tuple[str, dict[str, Any]]] = {}
        self._running: dict[Any, asyncio.Task[Any]] = {}

    # --- the endpoint -----------------------------------------------------

    async def endpoint(
        self,
        space: SpaceConfig,
        question: str,
        *,
        need_prose: bool,
        pool: Pool,
        settings: Settings,
    ) -> dict[str, Any]:
        """The endpoint retrieval for a question, asked no more than once.

        ``need_prose`` says whether a formulated answer is needed. When it is not —
        and arm C over chunks and the control-question gate do not need it —
        generation is asked for a single token: the response mode is set by the
        owner, and on a ``both`` endpoint it cannot be cancelled by the request.

        A recorded retrieval is reused even by someone who does NOT need the prose:
        the arm B answer contains both, so after it arm C has no reason to go to the
        endpoint. The converse is not true — for the prose after a truncated call one
        has to go again.
        """
        key = (space.key, question)
        cached = self._endpoint.get(key) if self.enabled else None
        if cached is not None and (cached.prose or not need_prose):
            self.savings.endpoint_reused += 1
            return cached.outcome

        async def fetch() -> dict[str, Any]:
            self.savings.endpoint_asked += 1
            return await pool.to_endpoint(
                ask_endpoint,
                space,
                question,
                settings=settings,
                max_tokens=None if need_prose else RETRIEVAL_ONLY_TOKENS,
            )

        outcome = await self._once(
            (*key, need_prose),
            fetch,
            on_wait=lambda: setattr(
                self.savings, "endpoint_reused", self.savings.endpoint_reused + 1
            ),
        )

        # A failed call is not recorded: a node reboot must not turn into one and
        # the same failure across all nine models. Empty prose under a truncated
        # ceiling is not a failure — it was not asked for.
        if self.enabled and not outcome.get("failed"):
            keep = self._endpoint.get(key)
            if keep is None or (need_prose and not keep.prose):
                self._endpoint[key] = _Cached(outcome=outcome, prose=need_prose)
        return outcome

    # --- the models -------------------------------------------------------

    async def answer(
        self,
        provider: Provider,
        system: str,
        user: str,
        *,
        pool: Pool,
        settings: Settings,
    ) -> tuple[str, dict[str, Any]]:
        """A model answer to a prompt at zero temperature.

        The key is the pair of prompts itself, not the question: in arm C material
        is mixed in with the question, and the answer to a question with material is
        not the same as without it. If the whole prompt matched, the answer will
        match too, because the temperature is zero; that is the condition under
        which a repeat measures nothing.

        This is the only thing the blocks use: ``denial_loop`` starts its pressure
        from the same first answer the direct test has already obtained, and there
        is no reason to pay for it twice. The repeats of ``monte_carlo`` go past the
        cache — their temperature is different, and the spread is precisely what is
        being measured.
        """
        key = (provider.url, provider.model, system, user)
        cached = self._answers.get(key) if self.enabled else None
        if cached is not None:
            self.savings.model_reused += 1
            return cached[0], {**cached[1], "reused": True}

        async def call() -> tuple[str, dict[str, Any]]:
            self.savings.model_asked += 1
            started = time.monotonic()
            answer, usage = await pool.to_model(
                chat,
                system,
                user,
                provider=provider,
                temperature=0.0,
                max_tokens=settings.answer_max_tokens,
                settings=settings,
            )
            # What the answer really cost. A reused answer would otherwise be
            # recorded as instantaneous: there was no call, and timing it would show
            # the cost of a dictionary lookup. In the log that would look like a
            # model answering in zero seconds — a number an auditor must not and
            # cannot believe.
            usage = dict(usage)
            usage["elapsed"] = round(time.monotonic() - started, 3)
            return answer, usage

        waited = False

        def mark_wait() -> None:
            nonlocal waited
            waited = True
            self.savings.model_reused += 1

        answer, usage = await self._once(key, call, on_wait=mark_wait)
        if self.enabled:
            self._answers[key] = (answer, usage)
        return (answer, {**usage, "reused": True}) if waited else (answer, usage)

    # --- one call for everyone waiting ------------------------------------

    async def _once(
        self,
        key: Any,
        make: Callable[[], Awaitable[T]],
        *,
        on_wait: Callable[[], None],
    ) -> T:
        """Create the call once, however many tasks are waiting for it.

        Without this the cache would not help where it is needed most: nine models
        come to one question at the same time, all nine miss — and all nine go to
        the endpoint. A dictionary saves only those who arrive later, and they start
        together.
        """
        running = self._running.get(key)
        if running is not None:
            on_wait()
            return await running  # type: ignore[no-any-return]

        task: asyncio.Task[T] = asyncio.ensure_future(make())
        self._running[key] = task
        try:
            return await task
        finally:
            self._running.pop(key, None)


@dataclass(slots=True)
class Progress:
    """How much is done out of how much — and when it is time to stop.

    A progress report is needed not for elegance: a run goes for hours, and a silent
    console is indistinguishable from a hung one.

    The threshold of consecutive failures is a port of ``max_consecutive_failures``
    from LiveTruth. A wrong key, exhausted credits, a rejected model name, a node
    that has gone down — failures a retry does not cure: a sequential run found out
    about them anew on every question and honestly paid for that in hours, and the
    result was a table of nothing but failures. Not the first failure but a series:
    a single failure can also be a one-off — too long a prompt, one unlucky pair —
    and dropping the whole measurement over it would be a trade in the wrong
    direction.

    ``watch`` is the only point through which anyone besides the log learns about
    the progress of a run. The observer both sees the movement and stops it: to end
    a run at the owner request it is enough for it to call ``stop``. A separate
    cancellation check would be a second walk over the same questions and a second
    place where it is decided whether to carry on.
    """

    total: int
    label: str = ""
    give_up_after: int = 0
    done: int = 0
    failures: int = 0
    streak: int = 0
    fatal: str = ""
    # The name the provider refused outright, when it did. Told apart from a
    # streak of failures because the two deserve different answers: a streak is
    # evidence, a refusal is a statement. The caller reads this to know which
    # name not to ask again — the streak says only that this pass went badly.
    refused: str = ""
    watch: Callable[[Progress], None] | None = None

    def step(self, *, failed: bool = False, refused: str = "") -> None:
        self.done += 1
        if refused:
            self.refuse(refused)
        if failed:
            self.failures += 1
            self.streak += 1
            if self.give_up_after and self.streak >= self.give_up_after:
                self.stop(
                    f"{self.streak} questions in a row failed — the answerer "
                    f"is not answering, and there is nothing to carry on with"
                )
        else:
            self.streak = 0
        if self.done % _PROGRESS_EVERY == 0 or self.done == self.total:
            logger.info(
                f"{self.label}: {self.done}/{self.total}"
                + (f", failures {self.failures}" if self.failures else "")
            )
        if self.watch is not None:
            try:
                self.watch(self)
            except Exception as exc:  # noqa: BLE001 - the observer outranks nothing
                # A failed progress record is not worth the run itself: it goes for
                # hours and costs money, whereas a bar in a UI does not.
                logger.warning(f"{self.label}: the progress observer failed: {exc}")

    @property
    def stopped(self) -> bool:
        return bool(self.fatal)

    def refuse(self, model: str) -> None:
        """The provider refused this name outright — stop now, not in twenty.

        The streak threshold is the right grain for "the answerer has gone
        quiet": a node that has rebooted answers again, and abandoning it over
        one failure would be a trade in the wrong direction. A refusal is not
        that. The key, the money, the name — the provider has already said that
        no question will be answered, and every further one buys the same
        sentence at the price of a call.

        The threshold cannot cover this case even in principle: it counts
        within one pass, and a trial run's pass is shorter than the threshold.
        On the rig a single misspelt model name went through every pass of
        every arm and came back, eighteen minutes later, with nothing.

        ``give_up_after`` of zero switches this off along with the streak. The
        setting names a streak and this is not one, but what an owner turns off
        there is abandoning a run early, and a rig deliberately measured while
        hostile is exactly the case the zero was left in for. An explicit
        decision outranks a saving.
        """
        if not self.give_up_after:
            return
        if not self.refused:
            self.refused = model
        self.stop(f"the provider refused {model} outright")

    def stop(self, reason: str) -> None:
        """End the run: from here on there will be only the same failures."""
        if self.fatal:
            return
        self.fatal = reason
        logger.error(
            f"{self.label}: the run was stopped — {reason}. "
            f"What was done is saved; the cause must be fixed and the run started again"
        )
