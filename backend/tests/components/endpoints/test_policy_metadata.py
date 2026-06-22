"""Tests for the policy-metadata contract on the query response (OME-285).

Covers the producer side: the success envelope serialization and the two
rejection rails (402 payment / 403 policy-violation) both carrying the same
`policy_metadata` envelope via QueryRejectedError.
"""

from syft_space.components.endpoints.interfaces import QueryOutcome
from syft_space.components.endpoints.query_handler import QueryEndpointHandler
from syft_space.components.endpoints.schemas import QueryEndpointResponse
from syft_space.components.policy_types.interfaces import (
    PaymentRequiredError,
    PolicyMetadata,
    PolicyMetadataEntry,
    PolicyViolationError,
    Recipient,
    TransactionRef,
)


def _handler() -> QueryEndpointHandler:
    # The rejection helpers only use the passed exception, never self state,
    # so None dependencies are fine for this unit.
    return QueryEndpointHandler(
        endpoint_repository=None,  # type: ignore[arg-type]
        dataset_repository=None,  # type: ignore[arg-type]
        model_repository=None,  # type: ignore[arg-type]
        policy_repository=None,  # type: ignore[arg-type]
        dataset_registry=None,  # type: ignore[arg-type]
        model_registry=None,  # type: ignore[arg-type]
        policy_registry=None,  # type: ignore[arg-type]
    )


def test_success_envelope_serializes_on_response() -> None:
    entry = PolicyMetadataEntry(
        policy_type="mpp_per_request",
        kind="payment",
        status="charged",
        amount=0.01,
        currency="USD",
        recipient=Recipient(username="alice", wallet_address="0xabc"),
        transaction=TransactionRef(rail="mpp", id="0xdeadbeef", reference="ext-1"),
    )
    meta = PolicyMetadata(outcome=QueryOutcome.SUCCESS.value, entries=[entry])
    resp = QueryEndpointResponse(cost=0.01, currency="USD", policy_metadata=meta)

    dumped = resp.model_dump()
    assert dumped["policy_metadata"]["outcome"] == "success"
    e = dumped["policy_metadata"]["entries"][0]
    assert e["status"] == "charged"
    assert e["transaction"] == {"rail": "mpp", "id": "0xdeadbeef", "reference": "ext-1"}
    assert e["recipient"]["username"] == "alice"


def test_reject_payment_envelope_402() -> None:
    entry = PolicyMetadataEntry(
        policy_type="mpp_per_request",
        kind="payment",
        status="rejected",
        amount=0.01,
        currency="USD",
        reason_code="PAYMENT_REQUIRED",
        reason="Payment of $0.01 required",
    )
    err = PaymentRequiredError(
        www_authenticate='MPP realm="alice/x" amount=0.01',
        description="Payment of $0.01 required",
        metadata_entry=entry,
    )
    rejected = _handler()._reject_payment(err)

    assert rejected.status_code == 402
    assert rejected.headers == {"WWW-Authenticate": 'MPP realm="alice/x" amount=0.01'}
    assert rejected.policy_metadata.outcome == "payment_required"
    assert rejected.policy_metadata.entries[0].reason_code == "PAYMENT_REQUIRED"


def test_reject_violation_envelope_403_insufficient_balance() -> None:
    entry = PolicyMetadataEntry(
        policy_type="xendit_per_request",
        kind="payment",
        status="rejected",
        amount=500.0,
        currency="IDR",
        reason_code="INSUFFICIENT_BALANCE",
        reason="Insufficient balance. Please purchase more credits.",
    )
    err = PolicyViolationError(
        "Insufficient balance. Please purchase more credits.",
        policy_type="xendit_per_request",
        outcome="policy_violation",
        metadata_entry=entry,
    )
    rejected = _handler()._reject_violation(err)

    assert rejected.status_code == 403
    assert rejected.headers is None
    assert rejected.policy_metadata.outcome == "policy_violation"
    assert rejected.policy_metadata.entries[0].reason_code == "INSUFFICIENT_BALANCE"


def test_reject_violation_access_denied_outcome() -> None:
    err = PolicyViolationError(
        "Access denied",
        policy_type="access",
        outcome="access_denied",
        metadata_entry=PolicyMetadataEntry(
            policy_type="access",
            kind="access",
            status="rejected",
            reason_code="ACCESS_DENIED",
        ),
    )
    rejected = _handler()._reject_violation(err)
    assert rejected.status_code == 403
    assert rejected.policy_metadata.outcome == "access_denied"
    assert rejected.policy_metadata.entries[0].kind == "access"
