"""The web check gate: only filtered questions reach the tested models.

An active question is asked when ``web_check.passed_filter`` lets it through:
a passing verdict from the current web check model, a control question, or a
hand-set status while ``manual_status_priority`` is "manual". Every place that
picks questions for asking goes through ``evaluable``.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

from syft_benchmark.config import Settings

if TYPE_CHECKING:
    from syft_benchmark.db import QaPair

# The refusal for a launch that would ask questions without a web check model.
FILTER_REQUIRED = "Choose a web check model"


def filter_missing(conf: Settings) -> bool:
    """Whether the effective settings name no web check model."""
    return not str(conf.filter_model or "").strip()


def passes(row: QaPair, conf: Settings) -> bool:
    """``web_check.passed_filter``; imported here to keep the import graph acyclic."""
    from syft_benchmark.generation.web_check import passed_filter

    return passed_filter(row, conf)


def evaluable(rows: Sequence[QaPair], conf: Settings) -> list[QaPair]:
    """The rows that may be asked, in the order given."""
    return [row for row in rows if passes(row, conf)]


def nothing_passed(waiting: int, conf: Settings) -> str:
    """The message for a set where no question passed the web check."""
    if filter_missing(conf):
        return f"{FILTER_REQUIRED}: no question can be asked without a web check"
    return (
        f"no question has passed the web check by {conf.filter_model} yet: "
        f"{waiting} active questions are waiting for it"
    )
