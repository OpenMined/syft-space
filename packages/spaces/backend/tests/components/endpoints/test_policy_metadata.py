"""Tests for the policy-metadata contract on the query response.

Covers the producer side: the success envelope serialization and the two
rejection rails (402 payment / 403 policy-violation) both carrying the same
`policy_metadata` envelope via QueryRejectedError.
"""

from syft_space.components.endpoints.interfaces import QueryOutcome
from syft_space.components.endpoints.query_handler import QueryRejectedError
from syft_space.components.endpoints.schemas import (
    PolicyMetadata,
    QueryEndpointResponse,
)
from syft_space.components.policy_types.interfaces import (
    PaymentRequiredError,
    PolicyMetadataEntry,
    PolicyRejection,
    PolicyViolationError,
    ReasonCode,
    Recipient,
    TransactionRef,
)


def test_policy_rejection_subset_of_query_outcome() -> None:
    """The handler coerces PolicyRejection -> QueryOutcome by value, so every
    PolicyRejection value must have a QueryOutcome twin. Locks the invariant
    that makes the boundary coercion total (no mapping table needed)."""
    assert {r.value for r in PolicyRejection} <= {o.value for o in QueryOutcome}


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
        reason_code=ReasonCode.PAYMENT_REQUIRED,
        reason="Payment of $0.01 required",
    )
    err = PaymentRequiredError(
        www_authenticate='MPP realm="alice/x" amount=0.01',
        description="Payment of $0.01 required",
        metadata_entry=entry,
    )
    rejected = QueryRejectedError.from_payment(err)

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
        reason_code=ReasonCode.INSUFFICIENT_BALANCE,
        reason="Insufficient balance. Please purchase more credits.",
    )
    err = PolicyViolationError(
        "Insufficient balance. Please purchase more credits.",
        policy_type="xendit_per_request",
        outcome=PolicyRejection.POLICY_VIOLATION,
        metadata_entry=entry,
    )
    rejected = QueryRejectedError.from_violation(err)

    assert rejected.status_code == 403
    assert rejected.headers is None
    assert rejected.policy_metadata.outcome == "policy_violation"
    assert rejected.policy_metadata.entries[0].reason_code == "INSUFFICIENT_BALANCE"


def test_reject_violation_access_denied_outcome() -> None:
    err = PolicyViolationError(
        "Access denied",
        policy_type="access",
        outcome=PolicyRejection.ACCESS_DENIED,
        metadata_entry=PolicyMetadataEntry(
            policy_type="access",
            kind="access",
            status="rejected",
            reason_code=ReasonCode.ACCESS_DENIED,
        ),
    )
    rejected = QueryRejectedError.from_violation(err)
    assert rejected.status_code == 403
    assert rejected.policy_metadata.outcome == "access_denied"
    assert rejected.policy_metadata.entries[0].kind == "access"


def test_rejection_envelope_includes_prior_entries() -> None:
    """A policy that already ran (e.g. charged) before a later policy rejects
    must still appear in the rejection envelope — prior entries first, then
    the rejecting policy's own entry."""
    charged = PolicyMetadataEntry(
        policy_type="xendit_per_request",
        kind="payment",
        status="charged",
        amount=5.0,
        currency="USD",
    )
    err = PolicyViolationError(
        "Rate limit exceeded",
        policy_type="rate_limit",
        outcome=PolicyRejection.RATE_LIMITED,
        metadata_entry=PolicyMetadataEntry(
            policy_type="rate_limit",
            kind="rate_limit",
            status="rejected",
            reason_code=ReasonCode.RATE_LIMITED,
        ),
    )
    rejected = QueryRejectedError.from_violation(err, prior_entries=[charged])

    assert rejected.policy_metadata.outcome == "rate_limited"
    statuses = [e.status for e in rejected.policy_metadata.entries]
    assert statuses == ["charged", "rejected"]
