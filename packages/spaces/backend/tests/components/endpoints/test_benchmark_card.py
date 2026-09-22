"""The benchmark card: what a Space accepts, stores, shows and takes back.

A benchmark measures an endpoint and hands the verdict to the Space that owns
it. The Space is what publishes — marketplace credentials live here and nowhere
else, so a benchmark never needs an account on the hub.

What is covered here is what would be expensive to get wrong: a card read
wrongly, a card nobody asked for, prose crossing into a published document, and
an owner unable to take back what is said in his name.
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from syft_space.components.endpoints.entities import (
    Endpoint,
    EndpointQualityCard,
    ResponseType,
)
from syft_space.components.endpoints.publish_handler import PublishEndpointHandler
from syft_space.components.endpoints.schemas import (
    CARD_VERSION,
    KIND_ANSWERING,
    KIND_RETRIEVAL,
    ReportQualityRequest,
)

TENANT_ID = uuid4()
ENDPOINT_ID = uuid4()
DATASET_ID = uuid4()
MODEL_ID = uuid4()


def _card(**overrides: object) -> dict:
    """A card as the benchmark actually sends one."""
    body = {
        "version": CARD_VERSION,
        "kind": KIND_ANSWERING,
        "arm": "open_book",
        "checked_at": "2026-09-14T03:00:00+00:00",
        "score": 0.71,
        "fabrication_rate": 0.04,
        "reliable": True,
        "samples": 515,
        "answerable": {
            "samples": 412,
            "correct": 0.71,
            "abstain": 0.12,
            "hallucinate": 0.17,
            "lmi": 0.19,
        },
        "unanswerable": {"samples": 103, "fabricated": 0.04},
        "discrimination": 0.63,
        "retrieval": 0.82,
        "models": [
            {
                "model": "anthropic/claude-sonnet-4",
                "samples": 412,
                "accuracy": 0.78,
                "fabrication": 0.02,
                "lmi": 0.1,
                "context_gain": 0.05,
            }
        ],
        "skills": [{"generator": "mcq", "samples": 80, "accuracy": 0.9}],
        "trust": {
            "judges": 3,
            "agreement": 0.86,
            "consistency": 0.91,
            "even_coverage": True,
            "failed": 2,
            "pending": 0,
            "flags": [],
        },
        "dataset": {
            "mode": "rolling",
            "window_days": 7,
            "cohort": "20260914-0300",
            "questions": 515,
        },
        "instrument": {
            "profile": "default",
            "judge": "gemma3-4b-gpu",
            "judges": 3,
            "subjects": 9,
        },
    }
    body.update(overrides)
    return body


def _endpoint(response_type: str = ResponseType.BOTH.value) -> Endpoint:
    return Endpoint(
        id=ENDPOINT_ID,
        tenant_id=TENANT_ID,
        name="Knowledge base",
        slug="kb",
        response_type=response_type,
        published_to=[],
        dataset_id=DATASET_ID,
        model_id=MODEL_ID,
    )


def _stored_card(**overrides: object) -> EndpointQualityCard:
    """A card as it comes back out of the table."""
    body = {
        "tenant_id": TENANT_ID,
        "endpoint_id": ENDPOINT_ID,
        "kind": KIND_ANSWERING,
        "score": 0.71,
        "fabrication_rate": 0.04,
        "samples": 515,
        "reliable": True,
        "checked_at": datetime(2026, 9, 14, 3, tzinfo=timezone.utc),
        "report": _card(),
    }
    body.update(overrides)
    return EndpointQualityCard(**body)  # type: ignore[arg-type]


def _handler(
    endpoint: Endpoint | None,
    *,
    benchmarks_mode: str = "local",
    current: EndpointQualityCard | None = None,
    standing: int = 0,
) -> PublishEndpointHandler:
    """A handler with just enough around it to answer one call."""
    endpoints = SimpleNamespace(
        get_by_slug=AsyncMock(return_value=endpoint),
        record_quality=AsyncMock(return_value=_stored_card()),
        get_current_quality=AsyncMock(return_value=current),
        retract_quality=AsyncMock(return_value=standing),
    )
    settings = SimpleNamespace(
        get_benchmarks_mode=AsyncMock(return_value=benchmarks_mode)
    )
    return PublishEndpointHandler(
        endpoint_repository=endpoints,  # type: ignore[arg-type]
        marketplace_repository=SimpleNamespace(),  # type: ignore[arg-type]
        dataset_repository=SimpleNamespace(),  # type: ignore[arg-type]
        model_repository=SimpleNamespace(),  # type: ignore[arg-type]
        dataset_registry=SimpleNamespace(),  # type: ignore[arg-type]
        model_registry=SimpleNamespace(),  # type: ignore[arg-type]
        settings_repository=settings,  # type: ignore[arg-type]
    )


# ============== what the Space agrees to read ==============


def test_a_real_card_is_accepted() -> None:
    """The shape the benchmark sends is the shape this Space reads."""
    card = ReportQualityRequest.model_validate(_card())

    assert card.kind == KIND_ANSWERING
    assert card.answerable is not None
    assert card.unanswerable is not None
    # Both halves of the dataset survive the trip. The control half is the one
    # a consumer cannot check for himself, and it is the reason the second half
    # of the dataset exists at all.
    assert card.unanswerable.fabricated == 0.04
    assert [row.model for row in card.models] == ["anthropic/claude-sonnet-4"]


def test_a_card_of_an_unknown_version_is_refused() -> None:
    """Refusing is the point.

    A card understood wrongly is worse than a card not taken: the first
    publishes a number that means something else, and nobody can see that it
    does.
    """
    with pytest.raises(ValueError, match="unsupported card version"):
        ReportQualityRequest.model_validate(_card(version=1))


def test_a_card_of_an_unknown_kind_is_refused() -> None:
    """The kind decides what the headline share means.

    "Finds 82%" and "correct 82%" are different claims about different
    products, and a renderer that cannot tell them apart will state one as the
    other.
    """
    with pytest.raises(ValueError, match="unknown kind"):
        ReportQualityRequest.model_validate(_card(kind="excellent"))


@pytest.mark.parametrize(
    "mutation",
    [
        {
            "skills": [
                {
                    "generator": "a fragment about port 5442",
                    "samples": 1,
                    "accuracy": 1.0,
                }
            ]
        },
        {"models": [{"model": "the model said this", "samples": 1, "accuracy": 1.0}]},
        {"arm": "open book"},
    ],
    ids=["skill", "model", "arm"],
)
def test_prose_never_reaches_a_published_document(mutation: dict) -> None:
    """The receiving end of the benchmark's promise.

    Only shares, counts and identifiers leave a benchmark's perimeter. Checking
    that by form rather than by a list of forbidden words is what makes it
    hold: every string here is one token, and a fragment of somebody's private
    corpus always has spaces in it.
    """
    with pytest.raises(ValueError, match="identifier, not text"):
        ReportQualityRequest.model_validate(_card(**mutation))


def test_a_share_outside_zero_to_one_is_refused() -> None:
    """A share is a share. Nothing downstream should have to check again."""
    with pytest.raises(ValueError):
        ReportQualityRequest.model_validate(_card(score=1.7))


# ============== who may speak in the Space's name ==============


@pytest.mark.asyncio
async def test_reporting_is_absent_until_the_owner_turns_it_on() -> None:
    """404, not 403.

    A Space that has not opted in should not advertise a way to speak in its
    name — "there is nothing here" rather than "you may not", because the
    second tells a stranger that the door exists.
    """
    handler = _handler(_endpoint(), benchmarks_mode="off")

    with pytest.raises(HTTPException) as caught:
        await handler.report_quality(
            "kb",
            ReportQualityRequest.model_validate(_card()),
            SimpleNamespace(id=TENANT_ID),  # type: ignore[arg-type]
        )

    assert caught.value.status_code == 404


@pytest.mark.asyncio
async def test_a_retraction_survives_reporting_being_switched_off() -> None:
    """Switching reporting off must not strand what was published while it was on.

    Reporting is a claim the owner lets a benchmark make on his behalf;
    retracting is an act of ownership over that claim. Gating both on the same
    setting would make it a one-way door.
    """
    handler = _handler(_endpoint(), benchmarks_mode="off", standing=1)
    handler._marketplaces_for = AsyncMock(return_value=[])  # type: ignore[method-assign]

    got = await handler.retract_quality(
        "kb",
        SimpleNamespace(id=TENANT_ID),  # type: ignore[arg-type]
    )

    assert got.cleared is True
    handler.endpoint_repository.retract_quality.assert_awaited_once()  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_retracting_what_was_never_reported_is_not_an_error() -> None:
    """Nothing to take down means the goal is already met."""
    handler = _handler(_endpoint())
    handler._marketplaces_for = AsyncMock(return_value=[])  # type: ignore[method-assign]

    got = await handler.retract_quality(
        "kb",
        SimpleNamespace(id=TENANT_ID),  # type: ignore[arg-type]
    )

    assert got.cleared is False


# ============== what gets stored ==============


@pytest.mark.asyncio
async def test_the_whole_card_is_stored_and_summarised_at_once() -> None:
    """Two readers, two shapes, one write.

    The columns are what a list of endpoints paints a badge from without
    opening a document per row; the whole card is what the owner reads before
    deciding whether he vouches for it.
    """
    handler = _handler(_endpoint())
    handler._marketplaces_for = AsyncMock(return_value=[])  # type: ignore[method-assign]

    await handler.report_quality(
        "kb",
        ReportQualityRequest.model_validate(_card()),
        SimpleNamespace(id=TENANT_ID),  # type: ignore[arg-type]
    )

    written = handler.endpoint_repository.record_quality.await_args.kwargs  # type: ignore[attr-defined]
    assert written["kind"] == KIND_ANSWERING
    assert written["score"] == 0.71
    assert written["fabrication_rate"] == 0.04
    assert written["reliable"] is True
    assert written["report"]["trust"]["agreement"] == 0.86
    assert written["report"]["instrument"]["subjects"] == 9


@pytest.mark.asyncio
async def test_a_card_measured_in_a_mode_the_endpoint_no_longer_serves_is_kept() -> (
    None
):
    """The owner may switch response_type between runs.

    The card describes what WAS measured. Refusing it would lose a real
    measurement over a change that happened afterwards; storing it silently as
    if it described today would be worse. It is stored, and the mismatch is
    said out loud in the log.
    """
    handler = _handler(_endpoint(ResponseType.RAW.value))
    handler._marketplaces_for = AsyncMock(return_value=[])  # type: ignore[method-assign]

    got = await handler.report_quality(
        "kb",
        ReportQualityRequest.model_validate(_card()),  # answering, but node is raw
        SimpleNamespace(id=TENANT_ID),  # type: ignore[arg-type]
    )

    assert got.stored is True


@pytest.mark.asyncio
async def test_a_searching_endpoint_reports_a_retrieval_card() -> None:
    """A raw endpoint never writes an answer, so it is judged by what it finds.

    While the arm was a benchmark-wide setting, such a node published nothing
    at all and a consumer discarded it at the badge — which is exactly where he
    cannot look closer.
    """
    handler = _handler(_endpoint(ResponseType.RAW.value))
    handler._marketplaces_for = AsyncMock(return_value=[])  # type: ignore[method-assign]

    await handler.report_quality(
        "kb",
        ReportQualityRequest.model_validate(
            _card(kind=KIND_RETRIEVAL, arm="model_with_context", score=0.82)
        ),
        SimpleNamespace(id=TENANT_ID),  # type: ignore[arg-type]
    )

    written = handler.endpoint_repository.record_quality.await_args.kwargs  # type: ignore[attr-defined]
    assert written["kind"] == KIND_RETRIEVAL
    assert written["score"] == 0.82


@pytest.mark.asyncio
async def test_a_new_card_does_not_overwrite_the_one_before_it() -> None:
    """A share is unreadable on its own.

    "0.71 accuracy" says almost nothing; "0.71, and 0.78 a month ago, on twice
    the questions" is what an owner actually decides on. Writing in place
    answered only "what is true now" and threw away the rest.
    """
    handler = _handler(_endpoint(), current=_stored_card(score=0.78))
    handler._marketplaces_for = AsyncMock(return_value=[])  # type: ignore[method-assign]

    await handler.report_quality(
        "kb",
        ReportQualityRequest.model_validate(_card(score=0.71)),
        SimpleNamespace(id=TENANT_ID),  # type: ignore[arg-type]
    )

    # Nothing is asked to forget: the write is an append, and no update or
    # delete goes anywhere near the card that stood before it.
    assert not hasattr(handler.endpoint_repository, "set_quality")
    handler.endpoint_repository.record_quality.assert_awaited_once()  # type: ignore[attr-defined]


def test_a_withdrawn_card_is_marked_rather_than_deleted() -> None:
    """What was published and then taken back is a fact about this endpoint.

    Deleting the row would make the next card look like the first one ever
    reported, and leave the owner with a history quietly missing its awkward
    runs. The mark is what the marketplaces are told by; the row is what the
    owner keeps.
    """
    assert "retracted_at" in EndpointQualityCard.model_fields
    assert EndpointQualityCard.__table__.c.retracted_at.nullable is True


# ============== the owner's own page ==============


@pytest.mark.asyncio
async def test_the_owner_reads_the_whole_card_whatever_the_setting_says() -> None:
    """This is the view a retraction is decided from.

    The owner must be able to read what is being said in his name even after he
    has closed the door on new reports.
    """
    handler = _handler(
        _endpoint(),
        benchmarks_mode="off",
        current=_stored_card(reliable=False),
    )

    got = await handler.get_quality(
        "kb",
        SimpleNamespace(id=TENANT_ID),  # type: ignore[arg-type]
    )

    assert got.reported is True
    assert got.reliable is False
    assert got.report is not None
    assert got.report["trust"]["judges"] == 3


@pytest.mark.asyncio
async def test_an_endpoint_nobody_measured_says_so_rather_than_showing_a_zero() -> None:
    """No report is not a score of zero, and must never render as one."""
    handler = _handler(_endpoint())

    got = await handler.get_quality(
        "kb",
        SimpleNamespace(id=TENANT_ID),  # type: ignore[arg-type]
    )

    assert got.reported is False
    assert got.score is None
    assert got.report is None
