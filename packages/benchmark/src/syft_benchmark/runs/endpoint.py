"""Calling the endpoint under test: the one party in the measurement that is not ours.

The arms decide WHAT to ask; this module asks and reads the answer: the
retrieval (chunks and ranks, the material arm C mixes in), the prose (the
endpoint's own answer) and the endpoint mode (raw / summary / both, set by the
owner), which decides which arms are measurable at all.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

import httpx
from loguru import logger

from syft_benchmark.config import Settings, SpaceConfig, get_settings
from syft_benchmark.db import QaPair
from syft_benchmark.runs.judge import ERROR_PREFIX

# The answer ceiling when only the retrieval is needed. On a `both` endpoint a
# request always starts generation, which cannot be cancelled but can be held
# to a single token: on a small CPU model the full text costs minutes.
RETRIEVAL_ONLY_TOKENS = 1


class EndpointFailed(RuntimeError):
    """The endpoint call failed (HTTP error, timeout, transport): not an empty
    retrieval, so a gate must treat the question as not checked."""


def ask_endpoint(
    space: SpaceConfig,
    question: str,
    *,
    settings: Settings | None = None,
    max_tokens: int | None = None,
    timeout: float = 900.0,
) -> dict[str, Any]:
    """Put a question to the endpoint the way a consumer does.

    Nothing is added to the question: the system prompt, the retrieval and the
    context are the endpoint's own business. The retrieval parameters come from
    the settings; the similarity threshold is an axis of the measurement (at
    zero the endpoint returns top-k for any question).
    """
    conf = settings or get_settings()

    started = time.time()
    headers = {"Authorization": f"Bearer {space.token}"} if space.token else None
    try:
        resp = httpx.post(
            f"{space.url}/api/v1/endpoints/{space.endpoint}/preview",
            json={
                "messages": question,
                "limit": conf.retrieval_top_k,
                "similarity_threshold": conf.similarity_threshold,
                "max_tokens": (
                    conf.endpoint_max_tokens if max_tokens is None else max_tokens
                ),
                "temperature": conf.endpoint_temperature,
            },
            headers=headers,
            timeout=timeout,
        )
        if resp.status_code >= 400:
            return {
                "answer": f"{ERROR_PREFIX} HTTP {resp.status_code}: {resp.text[:300]}",
                "documents": [],
                "latency": time.time() - started,
                "failed": True,
            }
        data = resp.json()
    except (httpx.TimeoutException, httpx.TransportError) as exc:
        return {
            "answer": f"{ERROR_PREFIX} {type(exc).__name__}: {exc}",
            "documents": [],
            "latency": time.time() - started,
            "failed": True,
        }

    summary = data.get("summary") or {}
    answer = ((summary.get("message") or {}).get("content") or "").strip()
    documents = (data.get("references") or {}).get("documents") or []
    if not answer:
        answer = f"{ERROR_PREFIX} the endpoint returned an empty answer"

    return {
        "answer": answer,
        "documents": documents,
        "latency": time.time() - started,
        "failed": False,
    }


def endpoint_retriever(
    space: SpaceConfig, settings: Settings | None = None
) -> Callable[[str], list[str]]:
    """What to check control questions with: a question in, texts back.

    Generation uses it to screen out a negative that retrieval does answer.
    A callable rather than a client, so generation does not depend on this
    package and the gate is testable offline.

    Raises ``EndpointFailed`` when the call fails, so a failure never reads as
    "retrieval found nothing".
    """
    conf = settings or get_settings()

    def retrieve(question: str) -> list[str]:
        outcome = ask_endpoint(
            space, question, settings=conf, max_tokens=RETRIEVAL_ONLY_TOKENS
        )
        if outcome["failed"]:
            error = str(outcome["answer"]).removeprefix(ERROR_PREFIX).strip()
            raise EndpointFailed(f"{space.key}: {error}")
        return [
            str(doc.get("content") or "")
            for doc in outcome["documents"]
            if doc.get("content")
        ]

    return retrieve


def check_retrieval(
    documents: list[dict[str, Any]], pair: QaPair, *, max_chars: int = 2000
) -> dict[str, Any]:
    """The rank, among what was found, of the document the question grew from.

    In arm C it tells an abstention on a retrieval miss (correct behaviour)
    from one on a hit (blindness).

    Args:
        documents: What the endpoint returned, in its own order
        pair: The item, for recognising the chunk it grew from
        max_chars: The ceiling on one chunk's text. Not a storage limit: arm
            C's prompt is assembled from what this returns, so it decides what
            the model is shown. Callers inside a run pass
            ``fragment_max_chars``.
    """
    rank = 0
    for position, doc in enumerate(documents, start=1):
        meta = doc.get("metadata") or {}
        if meta.get("doc_id") == pair.doc_id or (
            pair.file_name and meta.get("file_name") == pair.file_name
        ):
            rank = position
            break

    return {
        "retrieval_hit": bool(rank),
        "retrieval_rank": rank or None,
        "retrieved": [
            {
                "file_name": (doc.get("metadata") or {}).get("file_name", ""),
                "score": round(float(doc.get("similarity_score") or 0), 3),
                # The chunk's text: what grounding is checked against and what
                # arm C puts into the model's prompt.
                "content": str(doc.get("content") or "")[:max_chars],
                # The length before the cut, so a shortened chunk can say so.
                "chars": len(str(doc.get("content") or "")),
            }
            for doc in documents
        ],
    }


def endpoint_mode(space: SpaceConfig) -> str:
    """The endpoint mode at run time: raw / summary / both.

    It is read now and recorded beside the answer: the mode can be switched, and
    an old verdict relates to the previous one.
    """
    try:
        resp = httpx.get(f"{space.url}/api/v1/endpoints/{space.endpoint}", timeout=30)
        if resp.status_code < 400:
            return str(resp.json().get("response_type") or "")
    except (httpx.TimeoutException, httpx.TransportError) as exc:
        logger.debug(f"{space.key}: the endpoint mode was not read: {exc}")
    return ""
