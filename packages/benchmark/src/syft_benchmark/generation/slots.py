"""How many model calls generation and its checks keep in flight at once.

One limit for the whole build: generator calls, the control gate's judge and
the web check (its answer and its grading) all take a slot from the same
``ModelSlots``. A unit of work holds one slot for as long as it runs and makes
its calls one after another, so the units holding slots bound the calls in
flight. Checks ask with ``urgent=True`` and go before waiting generator calls:
a written question is checked as soon as a slot frees, not after the build.

Calls to the endpoint under test (the control gate's retrieval) have their own,
smaller limit: ``endpoint_concurrency``.
"""

from __future__ import annotations

import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager

from syft_benchmark.config import Settings


class ModelSlots:
    """A counting limit with two lanes: urgent waiters go first."""

    def __init__(self, width: int) -> None:
        self.width = max(1, width)
        self._free = self.width
        self._urgent_waiting = 0
        self._cond = threading.Condition()
        # The most slots ever held at once, for tests and logs.
        self.peak = 0

    @contextmanager
    def hold(self, *, urgent: bool = False) -> Iterator[None]:
        with self._cond:
            if urgent:
                self._urgent_waiting += 1
            try:
                while self._free == 0 or (not urgent and self._urgent_waiting):
                    self._cond.wait()
            finally:
                if urgent:
                    self._urgent_waiting -= 1
            self._free -= 1
            self.peak = max(self.peak, self.width - self._free)
        try:
            yield
        finally:
            with self._cond:
                self._free += 1
                self._cond.notify_all()


def model_slots(conf: Settings) -> ModelSlots:
    return ModelSlots(conf.concurrency)


def endpoint_limit(conf: Settings) -> threading.BoundedSemaphore:
    return threading.BoundedSemaphore(max(1, conf.endpoint_concurrency))


def limited(
    retrieve: Callable[[str], list[str]] | None, gate: threading.BoundedSemaphore
) -> Callable[[str], list[str]] | None:
    """``retrieve`` with at most the endpoint's share of requests in flight."""
    if retrieve is None:
        return None
    inner = retrieve

    def call(question: str) -> list[str]:
        with gate:
            return inner(question)

    return call


class Latch:
    """``should_stop`` asked from many threads: once true, it stays true."""

    def __init__(self, should_stop: Callable[[], bool] | None) -> None:
        self._ask = should_stop
        self._lock = threading.Lock()
        self._said = False

    def __call__(self) -> bool:
        if self._said or self._ask is None:
            return self._said
        with self._lock:
            if not self._said and self._ask():
                self._said = True
        return self._said
