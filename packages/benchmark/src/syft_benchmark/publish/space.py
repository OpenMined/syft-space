"""Handing the card to the Space and retracting what was published.

The benchmark does not go to SyftHub. It has no account there and must not have
one: it hands the numbers to the Space that owns the endpoint, and the Space
publishes them under its own account — exactly as it already does with health.

**Only aggregates** leave the perimeter (invariant 3). No questions, no answers,
no corpus chunks: `Card` does not contain them and cannot.

The first version of the payload returned six flat numbers. It is unfit for
three reasons at once, and all three came to light on a live rig:

* the headline number was computed over the answerable half of the set, while
  the control half — the one the halves were introduced for — never left at all;
* the arm was not named, although it was set by a setting: two nodes published
  "71%" measured by different arms, and the storefront could not tell them apart;
* a ``raw`` endpoint has no arm B — it refuses to run — and such a node was left
  with no numbers at all despite excellent retrieval.

So ``version``, ``kind`` and ``arm`` appeared in the payload, and the numbers
were split by half of the set. ``version`` is mandatory: the receiving side has
to know what it is reading, and an old Space must be able to refuse rather than
to misunderstand.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from syft_benchmark.config import SpaceConfig
from syft_benchmark.report.card import CARD_VERSION, Card


@dataclass(frozen=True, slots=True)
class PublishOutcome:
    """How the attempt to hand over the card ended."""

    ok: bool
    detail: str
    supported: bool = True


def _headers(space: SpaceConfig) -> dict[str, str] | None:
    return {"Authorization": f"Bearer {space.token}"} if space.token else None


def payload_for(card: Card) -> dict[str, Any]:
    """The card in the shape the Space accepts it in.

    The composition of this dictionary is the boundary between the benchmark
    internal analytics and what the outside world sees. Everything here is
    shares and counters; everything not here stays with the owner.
    """
    body: dict[str, Any] = {
        "version": CARD_VERSION,
        # The kind of product. Mandatory: on a retrieval node the headline
        # number is the retrieval hit, on an answering one the accuracy of the
        # answer, and naming them alike means passing one off as the other.
        "kind": card.kind,
        "arm": card.arm,
        "checked_at": card.checked_at.isoformat() if card.checked_at else "",
        "score": card.score,
        "fabrication_rate": card.fabrication,
        "reliable": card.reliable,
        "samples": card.trust.samples if card.trust else 0,
    }

    if card.answerable is not None:
        body["answerable"] = {
            "samples": card.answerable.graded,
            "correct": round(card.answerable.accuracy, 4),
            "abstain": round(card.answerable.abstain_rate, 4),
            "hallucinate": round(card.answerable.hallucination_rate, 4),
            "lmi": (
                round(card.answerable.lmi, 4)
                if card.answerable.lmi is not None
                else None
            ),
        }
    if card.control is not None:
        body["unanswerable"] = {
            "samples": card.control.graded,
            "fabricated": round(card.control.fabrication_rate, 4),
        }

    body["discrimination"] = card.discrimination
    body["retrieval"] = card.retrieval

    # Nine models as a list, not as an average. An average over them would
    # measure the composition of our config: add a tenth and the number moves,
    # although nothing happened to the node.
    body["models"] = [
        {
            "model": row.model,
            "samples": row.samples,
            "accuracy": row.accuracy,
            "fabrication": row.fabrication,
            "lmi": row.lmi,
            "context_gain": row.context_gain,
        }
        for row in card.models
    ]
    body["skills"] = [
        {
            "generator": row.generator,
            "samples": row.samples,
            "accuracy": row.accuracy,
        }
        for row in card.skills
    ]

    if card.trust is not None:
        body["trust"] = {
            "judges": card.trust.judges,
            "agreement": card.trust.agreement,
            "consistency": card.trust.consistency,
            "even_coverage": card.trust.even_coverage,
            "failed": card.trust.failed,
            "pending": card.trust.pending,
            # Codes, not prose: the wording is written by the storefront — it
            # has its own reader and its own language, and text does not cross
            # the perimeter without need.
            "flags": card.trust.flags,
        }
    if card.dataset is not None:
        body["dataset"] = {
            "mode": card.dataset.mode,
            "window_days": card.dataset.window_days,
            "cohort": card.dataset.cohort,
            "questions": card.dataset.questions,
        }
    if card.instrument is not None:
        # The instrument identity. Within one installation several Spaces are
        # measured by one and the same thing and are comparable with one
        # another; between different installations nothing is guaranteed, and
        # the storefront has to see that, otherwise it will silently compare
        # the incomparable.
        body["instrument"] = {
            "profile": card.instrument.profile,
            "judge": card.instrument.judge,
            "judges": card.instrument.judges,
            "subjects": card.instrument.subjects,
        }
    return body


def publish(
    space: SpaceConfig, card: Card, *, timeout: float = 120.0
) -> PublishOutcome:
    """Hand the card to the Space to publish.

    Args:
        space: The node the endpoint belongs to
        card: The card assembled from the run
        timeout: How long to wait for an answer

    Returns:
        PublishOutcome; supported=False if the Space cannot accept a card (an
        old version) or acceptance is switched off by the benchmarks_mode setting
    """
    if card.trust is None or card.trust.samples < 1:
        return PublishOutcome(False, "nothing to publish: not a single assessed answer")

    try:
        resp = httpx.post(
            f"{space.url}/api/v1/endpoints/{space.endpoint}/quality",
            json=payload_for(card),
            headers=_headers(space),
            timeout=timeout,
        )
    except (httpx.TimeoutException, httpx.TransportError) as exc:
        return PublishOutcome(False, f"{type(exc).__name__}: {exc}")

    if resp.status_code == 404:
        # There is no such route: either the Space is older than this feature,
        # or benchmarks_mode is off — and then 404 means "there is nothing here"
        # rather than a refusal. For the benchmark this is not a failure: the
        # owner has not given consent.
        return PublishOutcome(
            False,
            "the Space does not accept a card "
            "(benchmarks_mode is off or the version is old)",
            supported=False,
        )
    if resp.status_code == 422:
        # The format was not understood. Usually this is a Space that knows only
        # the first version of the payload: it is entitled to refuse, and
        # silently adapting to it is not allowed — that payload meant something
        # else.
        return PublishOutcome(
            False,
            f"the Space did not accept format version {CARD_VERSION}: "
            f"{resp.text[:200]}",
            supported=False,
        )
    if resp.status_code >= 400:
        return PublishOutcome(False, f"HTTP {resp.status_code}: {resp.text[:300]}")

    try:
        data = resp.json()
    except ValueError as exc:
        return PublishOutcome(False, f"unreadable response: {exc}")
    stored = bool(data.get("stored"))
    results = data.get("results") or []
    delivered = sum(1 for r in results if r.get("success"))
    return PublishOutcome(
        stored,
        f"stored in the Space: {stored}, delivered to marketplaces: {delivered}",
    )


def retract(space: SpaceConfig, *, timeout: float = 120.0) -> PublishOutcome:
    """Retract the published card through the Space.

    The right of retraction belongs to the owner, not to the benchmark: this
    function merely calls a Space route which itself decides who is allowed. The
    benchmark cannot erase what it did not publish.
    """
    try:
        resp = httpx.delete(
            f"{space.url}/api/v1/endpoints/{space.endpoint}/quality",
            headers=_headers(space),
            timeout=timeout,
        )
    except (httpx.TimeoutException, httpx.TransportError) as exc:
        return PublishOutcome(False, f"{type(exc).__name__}: {exc}")

    if resp.status_code == 404:
        return PublishOutcome(True, "there is nothing to retract", supported=False)
    if resp.status_code >= 400:
        return PublishOutcome(False, f"HTTP {resp.status_code}: {resp.text[:300]}")

    try:
        data = resp.json()
    except ValueError as exc:
        return PublishOutcome(False, f"unreadable response: {exc}")
    return PublishOutcome(True, f"retracted: {bool(data.get('cleared'))}")
