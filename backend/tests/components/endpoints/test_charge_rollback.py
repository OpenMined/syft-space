"""Refund-on-failure: uncommitted prepaid charges roll back when a query dies.

The buyer never pays for an answer they did not receive. PaymentChargers
wraps its prepaid charger in a RecordingPrepaidCharger: delivering the
response is the implicit commit, and ``query_endpoint`` rolls back every
still-uncommitted reservation on any non-success exit — including a charge
a post-hook had already decided to keep.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from syft_space.components.endpoints.entities import Endpoint
from syft_space.components.endpoints.query_handler import (
    QueryEndpointHandler,
    QueryRejectedError,
)
from syft_space.components.endpoints.schemas import AuthenticatedQueryRequest
from syft_space.components.model_types.interfaces import (
    ChatMessageResult,
    ChatResult,
    TokenUsage,
)
from syft_space.components.policy_types.interfaces import (
    PaymentChargers,
    PolicyContext,
    PolicyViolationError,
    RecordingPrepaidCharger,
)
from syft_space.components.policy_types.xendit.xendit_per_request import (
    XenditPerRequestPolicy,
)
from syft_space.components.shared.search_types import SearchedDocument, SearchResult

TENANT_ID = uuid4()
DATASET_ID = uuid4()
MODEL_ID = uuid4()
WALLET_ID = uuid4()
TX = uuid4()  # the transaction id every reserve in these tests mints
PRICE = 2.5


# ============== RecordingPrepaidCharger / PaymentChargers ==============


class FakeCharger:
    """Bare PrepaidBalanceCharger with a scriptable cancel failure."""

    currency = "USD"
    wallet_type = "xendit"

    def __init__(self) -> None:
        self.cancelled: list = []
        self.fail_cancel = False

    async def get_balance(self, user_email: str) -> float:
        return 100.0

    async def reserve(self, *, user_email, amount, charge_unit, charge_quantity):
        return uuid4()

    async def cancel(self, transaction_id) -> None:
        if self.fail_cancel:
            raise RuntimeError("provider down")
        self.cancelled.append(transaction_id)


async def _reserve(bag: PaymentChargers):
    return await bag.prepaid().reserve(
        user_email="buyer@test.com",
        amount=PRICE,
        charge_unit="request",
        charge_quantity=1,
    )


async def test_bag_wraps_prepaid_in_recorder():
    bag = PaymentChargers(prepaid=FakeCharger())
    charger = bag.prepaid()
    assert isinstance(charger, RecordingPrepaidCharger)
    # The wrapper is transparent to policies.
    assert charger.currency == "USD"
    assert charger.wallet_type == "xendit"
    assert await charger.get_balance("buyer@test.com") == 100.0


async def test_rollback_refunds_a_reserved_charge():
    fake = FakeCharger()
    bag = PaymentChargers(prepaid=fake)
    tx = await _reserve(bag)

    await bag.rollback()

    assert fake.cancelled == [tx]


async def test_policy_self_cancel_leaves_nothing_to_roll_back():
    fake = FakeCharger()
    bag = PaymentChargers(prepaid=fake)
    tx = await _reserve(bag)

    await bag.prepaid().cancel(tx)  # the empty-response refund path
    await bag.rollback()

    assert fake.cancelled == [tx]  # exactly once — rollback added nothing


async def test_rollback_without_prepaid_wallet_is_a_noop():
    await PaymentChargers().rollback()


async def test_rollback_swallows_cancel_failures_and_gives_up():
    fake = FakeCharger()
    bag = PaymentChargers(prepaid=fake)
    await _reserve(bag)
    fake.fail_cancel = True

    await bag.rollback()  # must not raise — the query's own error surfaces

    # The attempt is spent (manual reverse is the escape hatch): a later
    # rollback must not retry stale transactions.
    fake.fail_cancel = False
    await bag.rollback()
    assert fake.cancelled == []


# ============== query_endpoint wiring ==============


class BoomPostPolicy:
    """Passes pre_hook; post_hook dies — the live charge-leak shape."""

    async def pre_hook(self, configs, context: PolicyContext) -> PolicyContext:
        return context

    async def post_hook(self, configs, context: PolicyContext) -> PolicyContext:
        raise RuntimeError("post-hook bookkeeping crashed")


class BoomPrePolicy:
    """Rejects every query in pre_hook (after earlier policies reserved)."""

    async def pre_hook(self, configs, context: PolicyContext) -> PolicyContext:
        raise PolicyViolationError(message="blocked", policy_type="boom")

    async def post_hook(self, configs, context: PolicyContext) -> PolicyContext:
        return context


def _policy_rows(policy_types: dict[str, type]) -> dict[str, list]:
    """Grouped policy rows as the policy repository returns them."""
    config = {"price": PRICE, "applied_to": ["*"], "unit_type": "request"}
    return {
        name: [SimpleNamespace(configuration=config, wallet_id=WALLET_ID)]
        for name in policy_types
    }


def _make_handler(
    policy_types: dict[str, type],
) -> tuple[QueryEndpointHandler, MagicMock, MagicMock]:
    """Handler with a mocked pipeline, a real xendit wallet path, and the
    given policy types registered. Returns (handler, model_instance,
    balance_service) for failure injection and refund assertions."""
    endpoint = Endpoint(
        name="ep",
        slug="ep",
        tenant_id=TENANT_ID,
        dataset_id=DATASET_ID,
        model_id=MODEL_ID,
        response_type="both",
        published=True,
    )
    endpoint_repository = MagicMock()
    endpoint_repository.get_by_slug = AsyncMock(return_value=endpoint)

    policy_repository = MagicMock()
    policy_repository.get_by_endpoint_id_grouped = AsyncMock(
        return_value=_policy_rows(policy_types)
    )
    policy_registry = MagicMock()
    policy_registry.get_policy_type = MagicMock(
        side_effect=lambda name: policy_types[name]
    )

    dataset = SimpleNamespace(
        id=DATASET_ID, tenant_id=TENANT_ID, dtype="chroma", configuration={}
    )
    dataset_repository = MagicMock()
    dataset_repository.get_by_id = AsyncMock(return_value=dataset)
    dataset_instance = MagicMock()
    dataset_instance.search = AsyncMock(
        return_value=SearchResult(
            documents=[
                SearchedDocument(
                    document_id="doc-1", content="content", similarity_score=0.9
                )
            ]
        )
    )
    dataset_registry = MagicMock()
    dataset_registry.get_dataset_type = MagicMock(
        return_value=MagicMock(return_value=dataset_instance)
    )

    model = SimpleNamespace(
        id=MODEL_ID, tenant_id=TENANT_ID, dtype="openai", configuration={}
    )
    model_repository = MagicMock()
    model_repository.get_by_id = AsyncMock(return_value=model)
    model_instance = MagicMock()
    model_instance.chat = AsyncMock(
        return_value=ChatResult(
            id="chat-id",
            model="test-model",
            messages=[ChatMessageResult(role="assistant", content="answer", tokens=1)],
            finish_reason="stop",
            usage=TokenUsage(prompt_tokens=1, completion_tokens=1, total_tokens=2),
        )
    )
    model_instance.aclose = AsyncMock()
    model_registry = MagicMock()
    model_registry.get_model_type = MagicMock(
        return_value=MagicMock(return_value=model_instance)
    )

    wallet = SimpleNamespace(
        id=WALLET_ID, wallet_type="xendit", currency="USD", configuration={}
    )
    wallet_repository = MagicMock()
    wallet_repository.get_by_id = AsyncMock(return_value=wallet)
    balance_service = MagicMock()
    balance_service.reserve = AsyncMock(return_value=TX)
    balance_service.cancel = AsyncMock()

    handler = QueryEndpointHandler(
        endpoint_repository=endpoint_repository,
        dataset_repository=dataset_repository,
        model_repository=model_repository,
        policy_repository=policy_repository,
        dataset_registry=dataset_registry,
        model_registry=model_registry,
        policy_registry=policy_registry,
        wallet_repository=wallet_repository,
        balance_service=balance_service,
    )
    return handler, model_instance, balance_service


def _request() -> AuthenticatedQueryRequest:
    return AuthenticatedQueryRequest(
        messages="what is up?", sender_email="buyer@test.com"
    )


def _tenant() -> SimpleNamespace:
    return SimpleNamespace(id=TENANT_ID)


async def test_success_keeps_the_charge():
    handler, _, balance_service = _make_handler(
        {"xendit_per_request": XenditPerRequestPolicy}
    )

    response = await handler.query_endpoint("ep", _request(), _tenant())

    assert response.summary is not None
    balance_service.reserve.assert_awaited_once()
    balance_service.cancel.assert_not_awaited()


async def test_model_crash_rolls_back_the_charge():
    handler, model_instance, balance_service = _make_handler(
        {"xendit_per_request": XenditPerRequestPolicy}
    )
    model_instance.chat.side_effect = RuntimeError("model exploded")

    with pytest.raises(HTTPException):
        await handler.query_endpoint("ep", _request(), _tenant())

    balance_service.cancel.assert_awaited_once_with(TX)


async def test_post_hook_crash_rolls_back_a_kept_charge():
    # The live-bug shape: the payment policy's post-hook already recorded
    # the charge as kept, then a later post-hook died. The buyer got a 500
    # and no answer — the kept charge must still be refunded.
    handler, _, balance_service = _make_handler(
        {"xendit_per_request": XenditPerRequestPolicy, "boom": BoomPostPolicy}
    )

    with pytest.raises(RuntimeError, match="bookkeeping crashed"):
        await handler.query_endpoint("ep", _request(), _tenant())

    balance_service.cancel.assert_awaited_once_with(TX)


async def test_rejection_after_reserve_rolls_back():
    handler, _, balance_service = _make_handler(
        {"xendit_per_request": XenditPerRequestPolicy, "boom": BoomPrePolicy}
    )

    with pytest.raises(QueryRejectedError):
        await handler.query_endpoint("ep", _request(), _tenant())

    balance_service.reserve.assert_awaited_once()
    balance_service.cancel.assert_awaited_once_with(TX)
