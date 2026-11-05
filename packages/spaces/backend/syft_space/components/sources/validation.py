"""Helpers for a source's configuration validation.

Shape checks are pydantic's job. These cover what a source does around
them: reading the stored row it is replacing, deciding which connection
fields an edit touched, and probing many items without serialising them.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Iterable
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

M = TypeVar("M", bound=BaseModel)
T = TypeVar("T")
R = TypeVar("R")

PROBE_CONCURRENCY = 8


def parse_config(model: type[M], configuration: dict[str, Any], what: str) -> M:
    """``configuration`` read as ``model``, or ``ValueError`` naming ``what``."""
    try:
        return model.model_validate(configuration)
    except ValidationError as e:
        raise ValueError(f"Invalid {what}: {e}") from e


def previous_config(model: type[M], previous: dict[str, Any] | None) -> M | None:
    """The stored row read as ``model``; absent or unreadable is ``None``.

    ``None`` means nothing is trusted, so the caller probes everything.
    """
    if previous is None:
        return None
    try:
        return model.model_validate(previous)
    except ValidationError:
        return None


def changed_fields(
    model: type[BaseModel], current: BaseModel, previous: BaseModel | None
) -> set[str]:
    """Names of ``model``'s fields whose value differs; no previous, every field.

    Compared on the parsed models, so spelling and coercion do not count.
    """
    names = set(model.model_fields)
    if previous is None:
        return names
    return {n for n in names if getattr(current, n) != getattr(previous, n)}


async def gather_bounded(
    items: Iterable[T],
    fn: Callable[[T], Awaitable[R]],
    *,
    limit: int = PROBE_CONCURRENCY,
) -> list[R | BaseException]:
    """``gather(return_exceptions=True)`` over ``fn(item)``, ``limit`` in flight.

    Results come back in item order; the caller decides how failures read.
    """
    semaphore = asyncio.Semaphore(limit)

    async def bounded(item: T) -> R:
        async with semaphore:
            return await fn(item)

    return await asyncio.gather(
        *(bounded(item) for item in items), return_exceptions=True
    )
