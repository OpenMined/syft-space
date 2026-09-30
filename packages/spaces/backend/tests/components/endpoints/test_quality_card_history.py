"""Choosing which measured run stands in the owner's name.

The card an endpoint shows is "the newest one nobody withdrew". Putting an
earlier run back on top therefore moves no rows and rewrites no figures: the
runs measured after it are marked withdrawn, and the chosen one has its own
withdrawal cleared. These tests hold that rule, because the alternative — a
column saying which row is current — would let this table and the marketplaces
disagree about what is published.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from syft_space.components.endpoints.entities import Endpoint, EndpointQualityCard
from syft_space.components.endpoints.repository import EndpointRepository
from syft_space.components.shared.database import AsyncDatabase
from syft_space.components.tenants.entities import Tenant

CARD = {
    "version": 1,
    "kind": "answering",
    "arm": "open_book",
    "models": [{"model": "anthropic/claude-sonnet-4", "samples": 10, "accuracy": 0.8}],
    "instrument": {"profile": "default", "judge": "gemma3", "judges": 3, "subjects": 1},
}


async def _endpoint(db: AsyncDatabase, tenant: Tenant) -> UUID:
    """One endpoint in the table, identified by id.

    The id rather than the row: the session commits and closes here, and an
    ORM object outliving its session refuses to be read again.
    """
    endpoint_id = uuid4()
    async with db.get_session() as session:
        session.add(
            Endpoint(
                id=endpoint_id,
                tenant_id=tenant.id,
                name="Knowledge base",
                slug="kb",
                response_type="both",
                dataset_id=uuid4(),
                model_id=uuid4(),
            )
        )
        await session.commit()
    return endpoint_id


async def _record(
    repository: EndpointRepository,
    endpoint_id: UUID,
    tenant: Tenant,
    *,
    day: int,
    score: float,
) -> EndpointQualityCard:
    card = await repository.record_quality(
        endpoint_id,
        tenant.id,
        kind="answering",
        score=score,
        fabrication_rate=0.04,
        samples=100,
        reliable=True,
        checked_at=datetime(2026, 9, day, 3, tzinfo=timezone.utc),
        report=CARD,
    )
    assert card is not None
    return card


@pytest.mark.asyncio
async def test_an_earlier_run_becomes_the_one_that_stands(
    main_db: AsyncDatabase, endpoint_repository: EndpointRepository, tenant: Tenant
) -> None:
    """The chosen run is published; everything measured after it steps down."""
    endpoint_id = await _endpoint(main_db, tenant)
    july = await _record(endpoint_repository, endpoint_id, tenant, day=1, score=0.64)
    august = await _record(endpoint_repository, endpoint_id, tenant, day=14, score=0.78)
    september = await _record(
        endpoint_repository, endpoint_id, tenant, day=28, score=0.71
    )

    restored = await endpoint_repository.restore_quality_card(
        endpoint_id, tenant.id, august.id
    )

    assert restored is not None and restored.id == august.id
    current = await endpoint_repository.get_current_quality(endpoint_id, tenant.id)
    assert current is not None and current.id == august.id

    history = {
        card.id: card
        for card in await endpoint_repository.get_quality_history(
            endpoint_id, tenant.id
        )
    }
    # The later run is withdrawn, not deleted — it is still a fact about this
    # endpoint, and the owner can put it back.
    assert history[september.id].retracted_at is not None
    assert history[august.id].retracted_at is None
    # An earlier run was never the standing one, so nothing about it changed.
    assert history[july.id].retracted_at is None
    assert len(history) == 3


@pytest.mark.asyncio
async def test_the_move_is_reversible(
    main_db: AsyncDatabase, endpoint_repository: EndpointRepository, tenant: Tenant
) -> None:
    """Choosing the newer run again undoes it, with nothing lost in between."""
    endpoint_id = await _endpoint(main_db, tenant)
    august = await _record(endpoint_repository, endpoint_id, tenant, day=14, score=0.78)
    september = await _record(
        endpoint_repository, endpoint_id, tenant, day=28, score=0.71
    )

    await endpoint_repository.restore_quality_card(endpoint_id, tenant.id, august.id)
    await endpoint_repository.restore_quality_card(endpoint_id, tenant.id, september.id)

    current = await endpoint_repository.get_current_quality(endpoint_id, tenant.id)
    assert current is not None and current.id == september.id


@pytest.mark.asyncio
async def test_a_withdrawn_run_comes_back_when_it_is_chosen(
    main_db: AsyncDatabase, endpoint_repository: EndpointRepository, tenant: Tenant
) -> None:
    """Retraction is a claim about what may be shown, not a deletion."""
    endpoint_id = await _endpoint(main_db, tenant)
    august = await _record(endpoint_repository, endpoint_id, tenant, day=14, score=0.78)
    await endpoint_repository.retract_quality(endpoint_id, tenant.id)
    assert await endpoint_repository.get_current_quality(endpoint_id, tenant.id) is None

    await endpoint_repository.restore_quality_card(endpoint_id, tenant.id, august.id)

    current = await endpoint_repository.get_current_quality(endpoint_id, tenant.id)
    assert current is not None and current.id == august.id


@pytest.mark.asyncio
async def test_a_card_of_another_endpoint_is_not_restored(
    main_db: AsyncDatabase, endpoint_repository: EndpointRepository, tenant: Tenant
) -> None:
    """An id alone makes nothing stand."""
    endpoint_id = await _endpoint(main_db, tenant)
    await _record(endpoint_repository, endpoint_id, tenant, day=14, score=0.78)

    assert (
        await endpoint_repository.restore_quality_card(endpoint_id, tenant.id, uuid4())
        is None
    )


@pytest.mark.asyncio
async def test_two_cards_of_one_measurement_are_not_a_coin_toss(
    main_db: AsyncDatabase, endpoint_repository: EndpointRepository, tenant: Tenant
) -> None:
    """Rebuilding one measurement and publishing it twice is an ordinary thing.

    Both rows then carry the same `checked_at`, and ordered by that alone which
    of them stands is whatever the database happened to return first — while
    restoring one breaks the tie by when the row was written. The two must
    agree, or the table would name one card as published and the endpoint show
    the other.
    """
    endpoint_id = await _endpoint(main_db, tenant)
    first = await _record(endpoint_repository, endpoint_id, tenant, day=14, score=0.78)
    second = await _record(endpoint_repository, endpoint_id, tenant, day=14, score=0.78)

    current = await endpoint_repository.get_current_quality(endpoint_id, tenant.id)
    assert current is not None and current.id == second.id

    await endpoint_repository.restore_quality_card(endpoint_id, tenant.id, first.id)

    current = await endpoint_repository.get_current_quality(endpoint_id, tenant.id)
    assert current is not None and current.id == first.id
