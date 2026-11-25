"""A cancel signal that work running in another thread can react to."""

from __future__ import annotations

import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager


class CancelToken:
    """Set once to ask the holder to stop.

    Thread-safe: the work it stops usually runs in a worker thread while
    ``cancel`` is called from the event loop.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._cancelled = False
        self._actions: list[Callable[[], None]] = []

    @property
    def cancelled(self) -> bool:
        return self._cancelled

    def cancel(self) -> None:
        """Mark as cancelled and run every registered action. Idempotent."""
        with self._lock:
            if self._cancelled:
                return
            self._cancelled = True
            actions = list(self._actions)
        for action in actions:
            action()

    @contextmanager
    def on_cancel(self, action: Callable[[], None]) -> Iterator[None]:
        """Run ``action`` if cancelled while the block is active.

        Runs it at once when the token is already cancelled.
        """
        with self._lock:
            already_cancelled = self._cancelled
            if not already_cancelled:
                self._actions.append(action)
        if already_cancelled:
            action()
        try:
            yield
        finally:
            with self._lock:
                if action in self._actions:
                    self._actions.remove(action)
