"""Where a job's time went: phases, passes and model calls.

Kept with the job (``jobs.params["timing"]``) and shown in the technical view.
The shape is the "Timing" section of the report API.
"""

from __future__ import annotations

import math
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, TypeVar

T = TypeVar("T")

ANSWER = "answer"
JUDGE = "judge"


def _s(value: float) -> float:
    return round(value, 2)


def p90(values: list[float]) -> float:
    """The nearest-rank 90th percentile."""
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[max(0, math.ceil(0.9 * len(ordered)) - 1)]


class CallClock:
    """Model call latencies by model and role; thread-safe."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._times: dict[tuple[str, str], list[float]] = {}
        self._failed: dict[tuple[str, str], int] = {}

    def record(
        self, model: str, role: str, seconds: float, *, failed: bool = False
    ) -> None:
        key = (model, role)
        with self._lock:
            self._times.setdefault(key, []).append(max(0.0, float(seconds)))
            if failed:
                self._failed[key] = self._failed.get(key, 0) + 1

    def timed(
        self,
        model: str,
        role: str,
        fn: Callable[..., T],
        *,
        failed: Callable[[T], bool] | None = None,
        counted: Callable[[T], bool] | None = None,
    ) -> Callable[..., T]:
        """``fn`` that records its own duration; run it in the worker thread so
        the wait for a free slot is not counted.

        ``counted`` says whether a result came from a call at all (a letter
        matched without a judge is not one).
        """

        def run(*args: Any, **kwargs: Any) -> T:
            started = time.monotonic()
            try:
                result = fn(*args, **kwargs)
            except Exception:
                self.record(model, role, time.monotonic() - started, failed=True)
                raise
            if counted is None or counted(result):
                self.record(
                    model,
                    role,
                    time.monotonic() - started,
                    failed=bool(failed and failed(result)),
                )
            return result

        return run

    def stats(self) -> list[dict[str, Any]]:
        with self._lock:
            items = sorted(self._times.items(), key=lambda kv: (kv[0][1], kv[0][0]))
            failed = dict(self._failed)
        return [
            {
                "model": model,
                "role": role,
                "count": len(times),
                "failed": failed.get((model, role), 0),
                "mean_s": _s(sum(times) / len(times)),
                "p90_s": _s(p90(times)),
                "max_s": _s(max(times)),
                "total_s": _s(sum(times)),
            }
            for (model, role), times in items
            if times
        ]


@dataclass(slots=True)
class PassTime:
    """One evaluation pass, start to finish."""

    arm: str
    block: str
    model: str
    seconds: float = 0.0
    questions: int = 0
    stopped: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "arm": self.arm,
            "block": self.block,
            "model": self.model,
            "s": _s(self.seconds),
            "questions": self.questions,
            "stopped": self.stopped,
        }


@dataclass(slots=True)
class JobClock:
    """Phase durations of one job, closed on every phase change."""

    started: float = field(default_factory=time.monotonic)
    phases: list[tuple[str, float]] = field(default_factory=list)
    _current: str = ""
    _since: float = 0.0

    def enter(self, phase: str) -> None:
        if phase == self._current:
            return
        now = time.monotonic()
        self._close(now)
        self._current, self._since = phase, now

    def _close(self, now: float) -> None:
        if self._current:
            self.phases.append((self._current, now - self._since))
            self._current = ""

    def payload(
        self,
        *,
        passes: list[PassTime] | None = None,
        calls: list[dict[str, Any]] | None = None,
        concurrency: dict[str, int] | None = None,
    ) -> dict[str, Any]:
        """The ``timing`` value; closes the phase still open."""
        now = time.monotonic()
        self._close(now)
        merged: dict[str, float] = {}
        for phase, seconds in self.phases:
            merged[phase] = merged.get(phase, 0.0) + seconds
        return {
            "total_s": _s(now - self.started),
            "phases": [{"phase": p, "s": _s(s)} for p, s in merged.items()],
            "passes": [p.as_dict() for p in passes or []],
            "calls": calls or [],
            "concurrency": concurrency,
        }
