"""A finished item, before it is written to the database.

A separate module, because the type is needed both by the generator registry
and by the generators themselves: without it they would import one another in
a circle.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class Pair:
    """One item: the question, the gold answer and all that judging will need."""

    question: str
    answer: str
    distractors: list[str]
    meta: dict[str, Any]
