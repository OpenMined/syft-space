"""What a job spent at the provider, call by call.

OpenRouter returns ``usage.cost`` (USD, credits charged) in every chat
response; chat() copies it to ``usage["cost_usd"]`` and adds it to the active
meter. https://openrouter.ai/docs/guides/administration/usage-accounting

A meter is found in this order:

  1. the meter set in this thread's context (``cost_meter()`` sets it in the
     thread that opens it; ``pool_kwargs()`` / ``bind()`` carry it into pool
     workers, since contextvars do not cross into ThreadPoolExecutor threads);
  2. otherwise the only meter open in the process, if there is exactly one.
     The job worker runs one job at a time, so pool workers that were not given
     the meter still charge the right job. With two meters open and no context
     the cost is not attributed.

Usage::

    with cost_meter(job_id=job.id) as meter:
        before = openrouter_spend(conf)
        ...  # chat() calls, in this thread or in pools
        after = openrouter_spend(conf)
    meter.total_usd

    ThreadPoolExecutor(max_workers=n, **pool_kwargs())  # exact attribution
"""

from __future__ import annotations

import contextvars
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any, ParamSpec, TypeVar

from syft_benchmark.llm.openrouter import openrouter_spend

__all__ = [
    "CostMeter",
    "bind",
    "charge",
    "cost_meter",
    "cost_of",
    "current",
    "meter_for",
    "openrouter_spend",
    "pool_kwargs",
]

_P = ParamSpec("_P")
_R = TypeVar("_R")


class CostMeter:
    """A thread-safe sum of per-call costs for one job."""

    def __init__(self, job_id: Any = None) -> None:
        self.job_id = job_id
        self._lock = threading.Lock()
        self._total = 0.0
        self._calls = 0
        self._unpriced = 0

    def add(self, cost_usd: float | None) -> None:
        """Count one call; None is a call the provider did not price."""
        with self._lock:
            if cost_usd is None:
                self._unpriced += 1
            else:
                self._total += cost_usd
                self._calls += 1

    @property
    def total_usd(self) -> float:
        """USD of all priced calls so far."""
        with self._lock:
            return self._total

    @property
    def priced_calls(self) -> int:
        with self._lock:
            return self._calls

    @property
    def unpriced_calls(self) -> int:
        with self._lock:
            return self._unpriced


_ACTIVE: contextvars.ContextVar[CostMeter | None] = contextvars.ContextVar(
    "cost_meter", default=None
)
_OPEN: list[CostMeter] = []
_OPEN_LOCK = threading.Lock()


@contextmanager
def cost_meter(job_id: Any = None) -> Iterator[CostMeter]:
    """Open a meter for the block; chat() calls inside it are charged to it."""
    meter = CostMeter(job_id)
    token = _ACTIVE.set(meter)
    with _OPEN_LOCK:
        _OPEN.append(meter)
    try:
        yield meter
    finally:
        with _OPEN_LOCK:
            _OPEN.remove(meter)
        _ACTIVE.reset(token)


def current() -> CostMeter | None:
    """The meter a call made here is charged to; None — nowhere."""
    meter = _ACTIVE.get()
    if meter is not None:
        return meter
    with _OPEN_LOCK:
        return _OPEN[0] if len(_OPEN) == 1 else None


def meter_for(job_id: Any) -> CostMeter | None:
    """The open meter of this job; None — none is open."""
    with _OPEN_LOCK:
        return next((m for m in _OPEN if m.job_id == job_id), None)


def _adopt(meter: CostMeter | None) -> None:
    _ACTIVE.set(meter)


def pool_kwargs() -> dict[str, Any]:
    """ThreadPoolExecutor keyword arguments that give its workers this meter."""
    return {"initializer": _adopt, "initargs": (current(),)}


def bind(fn: Callable[_P, _R]) -> Callable[_P, _R]:
    """``fn`` run under the meter that is current here, in whatever thread."""
    meter = current()

    def bound(*args: _P.args, **kwargs: _P.kwargs) -> _R:
        token = _ACTIVE.set(meter)
        try:
            return fn(*args, **kwargs)
        finally:
            _ACTIVE.reset(token)

    return bound


def cost_of(usage: dict[str, Any]) -> float | None:
    """USD the provider charged for one response; None — not reported."""
    raw = usage.get("cost")
    if raw is None or isinstance(raw, bool):
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def charge(cost_usd: float | None) -> None:
    """Add one response's cost to the current meter, if any."""
    meter = current()
    if meter is not None:
        meter.add(cost_usd)
