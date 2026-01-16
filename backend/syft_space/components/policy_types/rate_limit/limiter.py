"""Rate limiter module with pluggable storage backends.

This module provides a centralized rate limiter that can be configured
at application startup. The policy class uses this module-level limiter
instead of maintaining its own state, keeping the policy stateless.

Usage:
    # At startup
    from syft_space.components.policy_types.rate_limit.limiter import (
        set_storage, InMemoryRateLimitStorage
    )
    set_storage(InMemoryRateLimitStorage())

    # In policy
    from syft_space.components.policy_types.rate_limit.limiter import check_rate_limit
    is_allowed, count = check_rate_limit(key, limit, window_seconds)
"""

import threading
from abc import ABC, abstractmethod
from collections import defaultdict
from datetime import datetime, timedelta, timezone


class RateLimitStorage(ABC):
    """Abstract base class for rate limit storage backends.

    Implementations must be thread-safe.
    """

    @abstractmethod
    def check_and_record(
        self,
        key: str,
        limit: int,
        window_seconds: int,
    ) -> tuple[bool, int]:
        """Atomically check rate limit and record request if allowed.

        Args:
            key: Unique identifier for the rate limit scope
            limit: Maximum number of requests allowed in the window
            window_seconds: Size of the sliding window in seconds

        Returns:
            Tuple of (is_allowed, current_count)
            - is_allowed: True if request is within limit
            - current_count: Number of requests in current window (after this request)
        """
        ...

    @abstractmethod
    def get_stats(
        self,
        key: str,
        limit: int,
        window_seconds: int,
    ) -> tuple[int, int]:
        """Get current rate limit statistics.

        Args:
            key: Unique identifier for the rate limit scope
            limit: Maximum number of requests allowed in the window
            window_seconds: Size of the sliding window in seconds

        Returns:
            Tuple of (remaining, reset_seconds)
            - remaining: Number of requests remaining in current window
            - reset_seconds: Seconds until the oldest request expires
        """
        ...


class InMemoryRateLimitStorage(RateLimitStorage):
    """Thread-safe in-memory rate limit storage using sliding window.

    Stores request timestamps per key and uses a sliding window algorithm
    to determine if requests are within the rate limit.
    """

    def __init__(self) -> None:
        """Initialize the in-memory storage."""
        self._history: dict[str, list[datetime]] = defaultdict(list)
        self._lock = threading.Lock()

    def check_and_record(
        self,
        key: str,
        limit: int,
        window_seconds: int,
    ) -> tuple[bool, int]:
        """Atomically check rate limit and record request if allowed."""
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(seconds=window_seconds)

        with self._lock:
            # Clean up expired timestamps
            self._history[key] = [ts for ts in self._history[key] if ts > window_start]

            current_count = len(self._history[key])

            # Check if limit exceeded
            if current_count >= limit:
                return False, current_count

            # Record this request
            self._history[key].append(now)
            return True, current_count + 1

    def get_stats(
        self,
        key: str,
        limit: int,
        window_seconds: int,
    ) -> tuple[int, int]:
        """Get current rate limit statistics."""
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(seconds=window_seconds)

        with self._lock:
            # Clean up expired timestamps
            self._history[key] = [ts for ts in self._history[key] if ts > window_start]

            current_count = len(self._history[key])
            remaining = max(0, limit - current_count)

            # Calculate reset time (when oldest request expires)
            if self._history[key]:
                oldest = min(self._history[key])
                reset_seconds = int(
                    (oldest + timedelta(seconds=window_seconds) - now).total_seconds()
                )
                reset_seconds = max(0, reset_seconds)
            else:
                reset_seconds = 0

            return remaining, reset_seconds


# Module-level storage instance
_storage: RateLimitStorage | None = None


def set_storage(storage: RateLimitStorage) -> None:
    """Configure the rate limit storage backend.

    Should be called at application startup.

    Args:
        storage: The storage backend to use
    """
    global _storage
    _storage = storage


def get_storage() -> RateLimitStorage:
    """Get the configured storage, creating default if needed.

    Returns:
        The configured RateLimitStorage instance
    """
    global _storage
    if _storage is None:
        _storage = InMemoryRateLimitStorage()
    return _storage


def check_rate_limit(
    key: str,
    limit: int,
    window_seconds: int,
) -> tuple[bool, int]:
    """Check if a request is within the rate limit.

    Args:
        key: Unique identifier for the rate limit scope
        limit: Maximum number of requests allowed in the window
        window_seconds: Size of the sliding window in seconds

    Returns:
        Tuple of (is_allowed, current_count)
    """
    storage = get_storage()
    return storage.check_and_record(key, limit, window_seconds)


def get_rate_limit_stats(
    key: str,
    limit: int,
    window_seconds: int,
) -> tuple[int, int]:
    """Get current rate limit statistics.

    Args:
        key: Unique identifier for the rate limit scope
        limit: Maximum number of requests allowed in the window
        window_seconds: Size of the sliding window in seconds

    Returns:
        Tuple of (remaining, reset_seconds)
    """
    storage = get_storage()
    return storage.get_stats(key, limit, window_seconds)
