"""A generated item before it is stored (``Pair``) and a dropped draft (``Dropped``).

Kept apart from the registry, which the generator modules would otherwise
import in a circle.
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


@dataclass(frozen=True, slots=True)
class Dropped:
    """A draft thrown away as written, and why."""

    reason: str
    question: str = ""
    answer: str = ""
