"""Concurrency for a run: lanes for calls, a cache of what was asked, progress.

**Waiting.** A run computes almost nothing: its time is an open socket to the
model under test, the judge or the endpoint, so calls are kept in flight in a
batch. There are two lanes: a model provider takes dozens of simultaneous
requests, while the endpoint under test is one foreign node whose queue only
accumulates timeouts.

**Repeats.** The endpoint's retrieval for a question is a property of the
corpus, shared by every model under test and every block; a model's answer at
zero temperature is the same in every block (``denial_loop`` starts from the
direct test's answer). The cache asks each once, and concurrent askers of the
same thing wait for the one call in flight.

The blocking code (``chat``, judging, the blocks) stays blocking and single;
calls go off to worker threads. There are no async twins of it: two copies of
the retry and truncation logic would diverge.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from functools import partial
from typing import Any

from loguru import logger

from syft_benchmark.config import Settings, SpaceConfig
from syft_benchmark.llm import Provider, chat, cost
from syft_benchmark.llm.web_search import search_mechanism
from syft_benchmark.runs.endpoint import RETRIEVAL_ONLY_TOKENS, ask_endpoint
from syft_benchmark.runs.timing import ANSWER, CallClock

# After how many finished tasks to log how many are left: a silent console
# looks like a hung one.
_PROGRESS_EVERY = 10

# How many database writes to keep in flight, off the event loop.
_STORAGE_LANE = 4


class Pool:
    """How many calls are kept in flight — separately by addressee.

    The holder of the worker threads and of the two lanes. It lives for exactly one
    event loop: the semaphores bind to the loop on the first wait, and a pool that
    outlived ``asyncio.run`` would fail on the next run.
    """

    def __init__(self, settings: Settings, *, clock: CallClock | None = None) -> None:
        # Model call latencies of everything asked through this pool.
        self.clock = clock if clock is not None else CallClock()
        self.model_limit = settings.concurrency
        self.endpoint_limit = settings.endpoint_concurrency
        self._model = asyncio.Semaphore(self.model_limit)
        self._endpoint = asyncio.Semaphore(self.endpoint_limit)
        self._storage = asyncio.Semaphore(_STORAGE_LANE)
        # As many threads as calls allowed in flight: the asyncio default is
        # sized by cores and would become a second, undeclared ceiling.
        self._workers = ThreadPoolExecutor(
            max_workers=self.model_limit + self.endpoint_limit + _STORAGE_LANE,
            thread_name_prefix="bench",
        )

    def close(self) -> None:
        self._workers.shutdown(wait=False)

    async def to_model[T](self, fn: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        """Make a call to a model — the one under test or a judge."""
        return await self._offload(self._model, fn, *args, **kwargs)

    async def to_endpoint[T](
        self, fn: Callable[..., T], *args: Any, **kwargs: Any
    ) -> T:
        """Make a call to the endpoint under test."""
        return await self._offload(self._endpoint, fn, *args, **kwargs)

    async def to_storage[T](self, fn: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        """Write a result to the database.

        The lane is separate and narrow: writing must not take room from the calls
        the run exists for, but there is no reason to hold the loop on it either.
        """
        return await self._offload(self._storage, fn, *args, **kwargs)

    async def _offload[T](
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

    One object serves every arm, block and model of a launch, so it holds
    nothing bound to the event loop except tasks that finish within it.
    Switched off by ``reuse_answers``, for measuring the spread of repeated
    calls itself.
    """

    def __init__(self, *, enabled: bool = True) -> None:
        self.enabled = enabled
        self.savings = Savings()
        self._endpoint: dict[tuple[str, str], _Cached] = {}
        self._answers: dict[
            tuple[str, str, str, str, tuple[str, str, int] | None],
            tuple[str, dict[str, Any]],
        ] = {}
        self._running: dict[Any, asyncio.Task[Any]] = {}

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

        A recorded retrieval with prose serves a caller that does not need the
        prose; the converse is not true — for the prose one has to go again.
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

    async def answer(
        self,
        provider: Provider,
        system: str,
        user: str,
        *,
        pool: Pool,
        settings: Settings,
        web_search: bool = False,
        web_search_engine: str = "auto",
    ) -> tuple[str, dict[str, Any]]:
        """A model answer to a prompt at zero temperature, asked once.

        Keyed by the whole prompt (in arm C it carries the material) and the
        search setup. The repeats of ``monte_carlo`` go past the cache: their
        temperature is not zero and their spread is what is measured.
        """
        # Searching or not, and how, changes the answer: all of it is in the key.
        searching = (
            (
                web_search_engine,
                search_mechanism(provider.model, settings),
                settings.web_search_max_results,
            )
            if web_search
            else None
        )
        key = (provider.url, provider.model, system, user, searching)
        cached = self._answers.get(key) if self.enabled else None
        if cached is not None:
            self.savings.model_reused += 1
            return cached[0], {**cached[1], "reused": True}

        async def call() -> tuple[str, dict[str, Any]]:
            self.savings.model_asked += 1
            started = time.monotonic()
            answer, usage = await pool.to_model(
                pool.clock.timed(provider.model, ANSWER, chat),
                system,
                user,
                provider=provider,
                temperature=0.0,
                max_tokens=settings.answer_max_tokens,
                settings=settings,
                web_search=web_search,
                web_search_engine=web_search_engine,
                role=cost.SUBJECTS,
            )
            # What the call took, so a reused answer carries it rather than
            # the time of a dictionary lookup.
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

    async def _once[T](
        self,
        key: Any,
        make: Callable[[], Awaitable[T]],
        *,
        on_wait: Callable[[], None],
    ) -> T:
        """Create the call once, however many tasks are waiting for it.

        Concurrent askers all miss the dictionary at once; they wait for the one
        call in flight instead. With the cache off every asker makes its own
        call: the spread of repeated calls is then what is measured.
        """
        if not self.enabled:
            return await make()
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

    A pass stops after ``give_up_after`` consecutive failures: a wrong key,
    spent credits, a rejected name or a node that is down fail every question,
    while a single failure can be a one-off. ``watch`` is the one observer of
    the progress, and it ends the pass by calling ``stop``.
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
    # The answerer's streak over all its passes running at once; None — this
    # pass counts its own.
    shared: Streak | None = None

    def step(self, *, failed: bool = False, refused: str = "") -> None:
        self.done += 1
        if refused:
            # Every pass of the answerer, so the streak this refusal also
            # feeds does not stop the others under its own reason.
            self.refuse(refused)
            for member in self.shared.members if self.shared else []:
                member.refuse(refused)
        if failed:
            self.failures += 1
            if self.shared is not None:
                self.shared.count += 1
                self.streak = self.shared.count
            else:
                self.streak += 1
            if self.give_up_after and self.streak >= self.give_up_after:
                reason = (
                    f"{self.streak} questions in a row failed — the answerer "
                    f"is not answering, and there is nothing to carry on with"
                )
                for member in self.shared.members if self.shared else [self]:
                    member.stop(reason)
        else:
            self.streak = 0
            if self.shared is not None:
                self.shared.count = 0
        if self.done % _PROGRESS_EVERY == 0 or self.done == self.total:
            logger.info(
                f"{self.label}: {self.done}/{self.total}"
                + (f", failures {self.failures}" if self.failures else "")
            )
        if self.watch is not None:
            try:
                self.watch(self)
            except Exception as exc:  # noqa: BLE001 - the observer outranks nothing
                # A failed progress record is not worth failing the run over.
                logger.warning(f"{self.label}: the progress observer failed: {exc}")

    @property
    def stopped(self) -> bool:
        return bool(self.fatal)

    def refuse(self, model: str) -> None:
        """The provider refused this name outright — stop now, not after a streak.

        A refusal (key, money, name) says no question will be answered, and
        the streak threshold, counted within one pass, may never be reached by
        a short pass. ``give_up_after`` of zero switches this off along with
        the streak: the owner chose not to abandon a run early.
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


@dataclass(slots=True)
class Streak:
    """Failed questions in a row of one answerer, across its concurrent passes.

    Passes of one model run at the same time and interleave; a model that has
    gone quiet fails in all of them, and a streak counted per pass would buy
    the threshold once per pass. A success anywhere resets it.
    """

    count: int = 0
    members: list[Progress] = field(default_factory=list)


class Launch:
    """What the passes of one launch share while they run at the same time.

    One loop, one pool: the model and endpoint lanes are global. ``units``
    bounds the questions in work over all passes, so a stop is read before a
    question is dispatched rather than after a backlog of them. ``refused``
    holds the names the provider refused outright: a refused answerer's passes
    stop, a refused judge stands down in every pass.
    """

    # How often the owner's stop is asked for (it is a database read).
    HALT_EVERY = 1.0

    def __init__(
        self, settings: Settings, *, halt: Callable[[], bool] | None = None
    ) -> None:
        self.units = asyncio.Semaphore(settings.concurrency)
        self.refused: set[str] = set()
        self._streaks: dict[str, Streak] = {}
        self._halt = halt
        self._halted = False
        self._asked_at = 0.0

    def streak(self, model: str) -> Streak:
        return self._streaks.setdefault(model, Streak())

    def halted(self) -> bool:
        """Whether the owner asked to stop; asked at most once a second."""
        if self._halted or self._halt is None:
            return self._halted
        now = time.monotonic()
        if now - self._asked_at >= self.HALT_EVERY:
            self._asked_at = now
            self._halted = bool(self._halt())
        return self._halted
