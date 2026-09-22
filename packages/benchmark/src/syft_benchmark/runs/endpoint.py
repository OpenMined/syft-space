"""Calling the endpoint under test.

The endpoint is the only party in the measurement that is not ours: its model,
its retrieval, its system prompt and its capacity. So the entire conversation
with it is gathered in one place, apart from the arms: the arms decide WHAT to
ask, here it is decided HOW to ask and how to read the answer.

Three things both sides need:

  * **the retrieval** — the chunks and their ranks. For arm B this is the cut
    without which its verdict is uninterpretable; for arm C it is the very
    material that gets mixed in with the question.
  * **the prose** — the answer the endpoint formulated. Arm B needs it whole,
    and arm C when the model credulity towards a foreign conclusion is measured.
  * **the endpoint mode** — raw / summary / both. It is set by the owner, and it
    decides which arm is measurable on this endpoint at all.
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

# The answer ceiling when only the retrieval is needed from the endpoint.
#
# The response mode is set by the owner, and on a `both` endpoint one request
# ALWAYS starts generation — even when only the chunks are needed from it: the
# control-question gate and arm C over chunks do not read the prose at all.
# Generation cannot be cancelled by the request, but it can be asked for a
# single token.
#
# Observed on a live DemoSyft run: the node model was gemma3:4b on CPU, and
# every such call cost three and a half minutes of waiting for text that was
# thrown away immediately.
RETRIEVAL_ONLY_TOKENS = 1


def ask_endpoint(
    space: SpaceConfig,
    question: str,
    *,
    settings: Settings | None = None,
    top_k: int | None = None,
    threshold: float | None = None,
    max_tokens: int | None = None,
    temperature: float | None = None,
    timeout: float = 900.0,
) -> dict[str, Any]:
    """Put a question to the endpoint the way the hub storefront does.

    Nothing is added to the question: the system prompt, the retrieval and the
    assembly of the context are the endpoint own business, and in arm B it is
    precisely its behaviour that is tested. In arm C what is needed from this
    same call is not the prose but the retrieval.

    The retrieval parameters are taken from the Space settings, and from the
    shared ones in their absence. The similarity threshold is an axis of the
    measurement, not a constant: at zero the endpoint is obliged to return top-k
    for any question, including one whose answer is not in the corpus, and it is
    physically unable to stay silent.
    """
    conf = settings or get_settings()
    default_k, default_threshold = conf.retrieval_for(space)

    started = time.time()
    headers = {"Authorization": f"Bearer {space.token}"} if space.token else None
    try:
        resp = httpx.post(
            f"{space.url}/api/v1/endpoints/{space.endpoint}/preview",
            json={
                "messages": question,
                "limit": default_k if top_k is None else top_k,
                "similarity_threshold": (
                    default_threshold if threshold is None else threshold
                ),
                "max_tokens": (
                    conf.endpoint_max_tokens if max_tokens is None else max_tokens
                ),
                "temperature": (
                    conf.endpoint_temperature if temperature is None else temperature
                ),
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

    Needed by generation, to screen out a negative that retrieval does in fact
    answer. Handed over as a callable rather than a client: generation must not
    depend on the runs module, and the gate has to be testable offline.
    """
    conf = settings or get_settings()

    def retrieve(question: str) -> list[str]:
        outcome = ask_endpoint(
            space, question, settings=conf, max_tokens=RETRIEVAL_ONLY_TOKENS
        )
        return [
            str(doc.get("content") or "")
            for doc in outcome["documents"]
            if doc.get("content")
        ]

    return retrieve


def check_retrieval(documents: list[dict[str, Any]], pair: QaPair) -> dict[str, Any]:
    """The rank, among what was found, of the document the question grew from.

    For ``raw`` mode this is the measurement itself: no model takes part, and
    "the accuracy of the answer" means whether the right chunk landed in the
    retrieval and in which position. For arm C it is the cut without which it is
    uninterpretable: an abstention on a retrieval miss is correct behaviour by
    the model, an abstention on a hit is its blindness, and in one share they
    are indistinguishable.
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
                # The text of the chunk found. The Space returns it in the
                # content field, and without it there is nothing to ground an
                # answer in: a judge shown a list of file names issues a verdict
                # about nothing. In arm C this same text goes into the model prompt.
                "content": str(doc.get("content") or "")[:2000],
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
