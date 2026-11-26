"""Found is not shown: arm C puts only the first ``context_docs`` chunks found
into the prompt.

Arm C records per answer ``retrieval_hit`` and ``retrieval_rank``
(``runs/endpoint.py``, ``check_retrieval``): the first position, among the
``retrieval_top_k`` chunks asked for, of a chunk from the question's source
article. ``retrieval_hit`` is NULL when no retrieval took place (the oracle
source, an endpoint call that failed): the question was not checked, which is
not a miss.

``Result.extra["retrieval_shown"]`` records whether the source chunk was among
the chunks in the prompt; ``shown_of`` reads it, or derives it for an answer
stored without it.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from syft_benchmark.config import ContextSource

SHOWN_KEY = "retrieval_shown"


def shown_in_prompt(
    rank: int | None,
    retrieved: Sequence[Mapping[str, Any]],
    *,
    source: ContextSource,
    context_docs: int,
) -> bool:
    """Whether the source chunk found at ``rank`` reached the model's prompt.

    Over the endpoint's answer alone no chunk is in the prompt, but the endpoint
    wrote that answer from every chunk found: found counts as shown.
    """
    if rank is None:
        return False
    if source is ContextSource.ENDPOINT_ANSWER:
        return True
    if rank > context_docs or rank > len(retrieved):
        return False
    return bool(str(retrieved[rank - 1].get("content") or "").strip())


@dataclass(frozen=True)
class Shown:
    """Whether the model was shown the source chunk.

    Attributes:
        value: None where no retrieval took place
        assumed: The answer was stored without the flag and its run without
            ``context_docs``: ``value`` is "found", which may overstate it
    """

    value: bool | None
    assumed: bool = False


def shown_of(
    hit: bool | None,
    rank: int | None,
    extra: Mapping[str, Any] | None,
    params: Mapping[str, Any] | None,
    context_source: str | None = None,
) -> Shown:
    """The stored flag, else one derived from the rank and the run's settings.

    Args:
        hit: ``Result.retrieval_hit``
        rank: ``Result.retrieval_rank``
        extra: ``Result.extra``
        params: ``Run.params``, for ``context_docs`` and ``context_source``
        context_source: ``Run.context_source`` when ``params`` lacks it
    """
    if hit is None:
        return Shown(None)
    stored = extra.get(SHOWN_KEY) if isinstance(extra, Mapping) else None
    if isinstance(stored, bool):
        return Shown(stored)
    if not hit:
        return Shown(False)
    params = params if isinstance(params, Mapping) else {}
    source = params.get("context_source") or context_source
    if source == ContextSource.ENDPOINT_ANSWER.value:
        return Shown(True)
    limit = params.get("context_docs")
    if isinstance(limit, int) and not isinstance(limit, bool) and rank is not None:
        return Shown(rank <= limit)
    return Shown(True, assumed=True)
