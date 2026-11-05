"""The one order questions are listed in, everywhere (report API, "Question order").

Kind in the setup page's order (unknown kinds last, alphabetically), then the
pair's creation time, then its id. Answers of one question follow by arm,
block, model and judge. Lists that page in SQL use ``pair_order``; lists built
in Python sort with ``pair_key``: both give the same order.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import case

KIND_ORDER = (
    "named_entity_masking",
    "numeric_masking",
    "temporal_masking",
    "mcq",
    "two_truths_one_lie",
    "multihop_synthesis",
    "tiered_explanation",
    "qa",
    "unanswerable_property",
    "false_premise",
)
ARM_ORDER = ("closed_book", "model_with_context")
BLOCK_ORDER = ("direct", "denial_loop", "monte_carlo")

_KIND_RANK = {kind: n for n, kind in enumerate(KIND_ORDER)}


def kind_rank(generator: str | None) -> int:
    """The kind's place; every unknown kind shares the place after the known."""
    return _KIND_RANK.get(generator or "", len(KIND_ORDER))


def pair_key(
    generator: str | None, created_at: datetime | None, pair_id: str
) -> tuple[Any, ...]:
    """The sort key of a pair (or a row about one pair)."""
    return (
        kind_rank(generator),
        generator or "",
        created_at is None,
        created_at.timestamp() if created_at is not None else 0.0,
        pair_id,
    )


def _rank(column: Any, names: tuple[str, ...]) -> Any:
    return case(
        {name: n for n, name in enumerate(names)}, value=column, else_=len(names)
    )


def pair_order(generator: Any, created_at: Any, pair_id: Any) -> tuple[Any, ...]:
    """ORDER BY clauses for the pair columns given; same order as ``pair_key``."""
    return (
        _rank(generator, KIND_ORDER),
        generator.asc().nulls_last(),
        created_at.asc().nulls_last(),
        pair_id.asc().nulls_last(),
    )


def answer_order(
    context_mode: Any, block: Any, model: Any, judge: Any, created_at: Any, row_id: Any
) -> tuple[Any, ...]:
    """ORDER BY clauses for the rows of one question, after ``pair_order``."""
    return (
        _rank(context_mode, ARM_ORDER),
        context_mode.asc(),
        _rank(block, BLOCK_ORDER),
        block.asc(),
        model.asc().nulls_first(),
        judge.asc(),
        created_at.asc(),
        row_id.asc(),
    )
