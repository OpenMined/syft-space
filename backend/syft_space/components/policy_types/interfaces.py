"""Policy type interfaces and domain models."""

from enum import Enum
from typing import Any, Literal, Protocol
from uuid import UUID

from mpp import Challenge, Credential, Receipt
from pydantic import BaseModel, ConfigDict, EmailStr, Field

# --------------------------------------------------------------------------- #
# Policy metadata contract                                                     #
#                                                                              #
# Each policy contributes a PolicyMetadataEntry describing what it did: what   #
# it charged, to whom, the rail-native transaction id, and — for rejections —  #
# why it blocked the query. The endpoints layer aggregates these into the      #
# PolicyMetadata envelope returned on the query response (endpoints.schemas).  #
# It is the authoritative source of price/recipient/outcome for API clients.   #
# --------------------------------------------------------------------------- #


class PolicyRejection(str, Enum):
    """The categories of rejection a policy can produce.

    Owned by `policy_types` because policies are what *produce* these — unlike
    the endpoints-owned `QueryOutcome`, which also covers query-lifecycle
    states no policy emits (success, not_found, not_published, internal_error).
    `QueryOutcome` is a deliberate value-superset; the endpoints layer coerces
    a PolicyRejection into its QueryOutcome twin at the rejection boundary.
    """

    POLICY_VIOLATION = "policy_violation"
    ACCESS_DENIED = "access_denied"
    RATE_LIMITED = "rate_limited"


class ReasonCode(str, Enum):
    """Machine-readable code on a rejected PolicyMetadataEntry.

    A stable contract the SDK can switch on, distinct from the human-readable
    `reason`. Owned by `policy_types` because policies are what produce them.
    """

    NO_PRICING_TIER = "NO_PRICING_TIER"
    INSUFFICIENT_BALANCE = "INSUFFICIENT_BALANCE"
    PAYMENT_REQUIRED = "PAYMENT_REQUIRED"
    ACCESS_DENIED = "ACCESS_DENIED"
    RATE_LIMITED = "RATE_LIMITED"


class TransactionRef(BaseModel):
    """A rail-native payment reference.

    `id` is the underlying rail's own identifier — a Tempo transaction hash
    for MPP, or the prepaid ledger `transaction_id` (a UUID) for
    Xendit/Stripe — disambiguated by `rail`.
    """

    rail: Literal["mpp", "xendit", "stripe", "cluster"] = Field(
        ..., description="Settlement rail that produced this transaction"
    )
    id: str = Field(
        ..., description="Rail-native transaction id (tx hash / ledger UUID)"
    )
    reference: str | None = Field(
        default=None, description="Secondary reference (e.g. MPP external_id)"
    )


class Recipient(BaseModel):
    """Who gets paid for a query — the endpoint owner / publisher."""

    username: str | None = Field(default=None, description="Endpoint owner username")
    email: str | None = Field(default=None, description="Endpoint owner email")
    wallet_address: str | None = Field(
        default=None, description="Public MPP wallet address (never a private key)"
    )


class PolicyMetadataEntry(BaseModel):
    """One policy's contribution to the query's metadata."""

    policy_type: str = Field(
        ..., description="Policy type name, e.g. 'mpp_per_request'"
    )
    kind: Literal["payment", "access", "transform", "rate_limit"] = Field(
        ..., description="Category of policy that produced this entry"
    )
    status: Literal["charged", "refunded", "free", "rejected", "applied", "skipped"] = (
        Field(..., description="What happened for this policy on this query")
    )
    amount: float | None = Field(default=None, description="Amount charged/refunded")
    currency: str | None = Field(default=None, description="Currency of the amount")
    recipient: Recipient | None = Field(
        default=None, description="Who was/would be paid (payment policies)"
    )
    transaction: TransactionRef | None = Field(
        default=None, description="Settled transaction reference (payment policies)"
    )
    reason_code: ReasonCode | None = Field(
        default=None, description="Machine-readable rejection code (see ReasonCode)"
    )
    reason: str | None = Field(default=None, description="Human-readable explanation")
    details: dict[str, Any] = Field(
        default_factory=dict, description="Extra context, e.g. {'documents': 3}"
    )


class PolicyViolationError(Exception):
    """Raised when a policy rule is violated.

    This exception is used by policy hooks to signal that the request
    should be blocked (pre-hook) or the response should not be returned (post-hook).
    """

    def __init__(
        self,
        message: str,
        policy_type: str,
        details: dict[str, Any] | None = None,
        *,
        outcome: PolicyRejection = PolicyRejection.POLICY_VIOLATION,
        metadata_entry: "PolicyMetadataEntry | None" = None,
    ) -> None:
        """Initialize the PolicyViolationError.

        Args:
            message: Human-readable error message
            policy_type: Name of the policy type that raised the error
            details: Optional additional details about the error
            outcome: The rejection category (defaults to POLICY_VIOLATION)
            metadata_entry: The rejected PolicyMetadataEntry to surface to the client
        """
        super().__init__(message)
        self.policy_type = policy_type
        self.details = details or {}
        self.outcome: PolicyRejection = outcome
        self.metadata_entry = metadata_entry


class PaymentRequiredError(Exception):
    """Raised when MPP charge returns a Challenge (payment required).

    This is NOT a policy violation - it's a payment flow signal.
    The endpoint handler should catch this and return HTTP 402.
    """

    def __init__(
        self,
        www_authenticate: str,
        description: str | None = None,
        *,
        metadata_entry: "PolicyMetadataEntry | None" = None,
    ):
        self.www_authenticate = www_authenticate
        self.description = description
        self.metadata_entry = metadata_entry
        super().__init__(description or "Payment required")


class PolicyAttachError(Exception):
    """Base for policy-attach failures.

    Subclasses describe the *kind* of failure in domain terms; the handler
    layer maps each subclass to an HTTP status. Domain code never references
    HTTP — `raise PolicyAttachNotFoundError("Wallet not found")` is enough.
    """


class PolicyAttachInputError(PolicyAttachError):
    """Invalid or missing input on the attach request (e.g., wallet_id
    missing for a wallet-bound policy, or wallet_id supplied for a
    non-wallet policy)."""


class PolicyAttachNotFoundError(PolicyAttachError):
    """A referenced entity (wallet, endpoint, ...) was not found for the
    current tenant."""


class PolicyAttachConflictError(PolicyAttachError):
    """Semantic conflict between the policy and the surrounding system —
    e.g., wallet type mismatch, sibling policies disagree on wallet,
    per-document pricing on an LLM endpoint."""


def add_response_cost(response: dict[str, Any], amount: float, currency: str) -> None:
    """Accumulate a charge into the response's top-level `cost` + `currency`.

    Payment policy post-hooks call this once per policy that applied, so
    multiple policies on the same query (e.g. per-request + per-document)
    sum cleanly. Currency is required to be homogeneous across policies on
    one endpoint — enforced upstream by sharing a single wallet — so each
    call just overwrites the currency field with the same value.

    Zero is intentionally permitted (negative is rejected as a non-event):
    a free-tier match, empty response, or zero-document search should
    record `cost=0` so consumers can distinguish "this query was free
    under our pricing" (cost=0, currency set) from "this endpoint has no
    pricing configured" (cost=None).

    Top-level `cost`/`currency` is the canonical answer to "what did this
    query cost the user?" Per-component cost (on `summary` / `references`)
    is intentionally not used: different policies bill against different
    components, and summing per-component fields would lie about the total.
    """
    if amount < 0:
        return
    # `cost` may already be present-but-None when the response dict was
    # serialized from QueryEndpointResponse (Field default = None), so
    # `.get("cost", 0)` would return None. Coalesce instead.
    response["cost"] = (response.get("cost") or 0) + amount
    response["currency"] = currency


class BalanceShortfallError(Exception):
    """Raised by PrepaidBalanceCharger.reserve when the user's balance is
    below the required amount.

    Policy-facing exception owned by this layer. The underlying
    InsufficientBalanceError from the balance service stays internal to
    payments/ — the adapter translates so policy_types never imports it.
    """

    def __init__(self, *, balance: float, required: float, currency: str) -> None:
        self.balance = balance
        self.required = required
        self.currency = currency
        super().__init__(
            f"Balance {balance} {currency} below required {required} {currency}"
        )


class MppCharger(Protocol):
    """MPP wallet-bound charger for a single request.

    Constructed by the framework with the endpoint's MPP wallet config
    (address, secret key, realm) and the request's X-Payment header bound.
    Policies call .charge() without threading credentials through every call.
    """

    async def charge(
        self, *, amount: float, description: str
    ) -> Challenge | tuple[Credential, Receipt]:
        """Attempt to charge `amount`.

        Returns a Challenge if no credential is bound or the bound
        credential is insufficient — the policy raises PaymentRequiredError
        from it. Returns (credential, receipt) on successful settlement.
        """
        ...


class PrepaidBalanceCharger(Protocol):
    """Wallet-bound charger for prepaid-balance gateways (Xendit, Stripe, …).

    Constructed by the framework with wallet_id, currency, tenant_id, and
    endpoint_id bound. Policies pass only request-scoped data. All
    prepaid-balance providers spend balance the same way once it's been
    topped up — only the top-up rail differs — so a single Protocol covers
    them all. The concrete implementation lives in
    ``payments.gateway.balance_charger.WalletBalanceCharger``.
    """

    @property
    def currency(self) -> str:
        """Wallet currency code (e.g., 'IDR', 'USD'). Surfaced on responses."""
        ...

    @property
    def wallet_type(self) -> str:
        """Underlying prepaid provider (e.g., 'xendit', 'stripe').

        Exposed for observability — log lines, audit metadata, response
        annotations. Policies should not branch on this value; behavioral
        differences between prepaid rails are absorbed by the implementation.
        """
        ...

    async def get_balance(self, user_email: str) -> float:
        """Return the user's current spendable balance in the wallet's currency."""
        ...

    async def reserve(
        self,
        *,
        user_email: str,
        amount: float,
        charge_unit: str,
        charge_quantity: int,
    ) -> UUID:
        """Reserve `amount` against the user's balance.

        Raises:
            BalanceShortfallError: balance is below `amount`.
        """
        ...

    async def cancel(self, transaction_id: UUID) -> None:
        """Cancel a previously reserved transaction (e.g., empty response)."""
        ...


class PaymentChargers:
    """Per-request bag of payment chargers, accessed by mechanism.

    An endpoint is constrained to a single wallet, so at most one of `mpp`
    and `prepaid` is populated per request. Methods raise if the requested
    charger isn't built: by the time a policy's hook runs, CapabilityChecker
    has already validated that any declared required_wallet_type has a
    matching wallet attached, so a missing charger indicates a framework
    bug rather than user input.
    """

    def __init__(
        self,
        *,
        mpp: MppCharger | None = None,
        prepaid: PrepaidBalanceCharger | None = None,
    ) -> None:
        self._mpp = mpp
        self._prepaid = prepaid

    def mpp(self) -> MppCharger:
        if self._mpp is None:
            raise RuntimeError(
                "MPP charger requested but no MPP wallet is attached to this endpoint"
            )
        return self._mpp

    def prepaid(self) -> PrepaidBalanceCharger:
        if self._prepaid is None:
            raise RuntimeError(
                "Prepaid-balance charger requested but no prepaid wallet "
                "(Xendit, Stripe, …) is attached to this endpoint"
            )
        return self._prepaid


class Capabilities(BaseModel):
    """Declarative facts a policy type declares about itself.

    Read by CapabilityChecker at policy creation time to validate that the
    system honors what the policy needs. New requirement kinds are added by
    extending this model — policy classes don't import anything outside this
    module to express their needs.

    Defaults describe a policy with no special requirements (e.g., access
    and rate_limit policies). Wallet-bound policies override requires_wallet
    and required_wallet_type. Policies that count retrieved documents (e.g.,
    per-document pricing) override requires_endpoint_dataset since they need
    a data source attached to the endpoint — whether or not an LLM step is
    also present is irrelevant.
    """

    requires_wallet: bool = False
    required_wallet_type: str | None = None
    requires_endpoint_dataset: bool = False


class PolicyContext(BaseModel):
    """Domain context for policy execution.

    Passed to policy hooks with request/response information.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    endpoint_slug: str = Field(..., description="Slug of the endpoint being accessed")
    sender_email: EmailStr = Field(..., description="Email of the request sender")
    request: dict[str, Any] = Field(..., description="Request payload")
    response: dict[str, Any] | None = Field(
        default=None, description="Response payload (for post hooks)"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Cross-hook scratch (transaction id handoff, etc.)",
    )
    payment_chargers: PaymentChargers | None = Field(
        default=None,
        description="Per-request payment chargers, built from attached wallets",
    )
    recipient: Recipient | None = Field(
        default=None,
        description="Endpoint owner identity (the 'to whom' for payment entries)",
    )
    policy_metadata: list[PolicyMetadataEntry] = Field(
        default_factory=list,
        description="Accumulated per-policy metadata entries for this query",
    )

    def add_policy_metadata(self, entry: PolicyMetadataEntry) -> None:
        """Append a policy's metadata entry, surfaced on the query response."""
        self.policy_metadata.append(entry)


class BasePolicyType(Protocol):
    """Base policy type interface.

    All concrete policy types must implement this protocol.
    Policies are pre/post hooks applied to endpoint requests.

    One instance is created per policy type, and all configurations
    for that type are passed to the hooks. This allows the policy type
    to determine its own aggregation logic (AND/OR/custom).
    """

    NAME: str

    def __init__(self) -> None:
        """Initialize the policy type.

        No configuration is passed here - configurations are passed to hooks.
        """
        ...

    @classmethod
    def name(cls) -> str:
        """Get the name of the policy type."""
        ...

    @classmethod
    def description(cls) -> str:
        """Get the description of the policy type."""
        ...

    @classmethod
    def icon(cls) -> str:
        """Get the icon for the policy type."""
        ...

    @classmethod
    def configuration_schema(cls) -> dict[str, Any]:
        """Return configuration schema required by this policy type.

        This will be displayed in the frontend/SDK as configurable values
        when creating a policy.

        Returns:
            Dictionary describing the configuration schema
        """
        ...

    @classmethod
    def capabilities(cls) -> Capabilities:
        """Declare facts about this policy type for the CapabilityChecker.

        Default: no special requirements (no wallet, no endpoint constraints).
        Override on subclasses that need a wallet, forbid certain endpoint
        kinds, etc. See `Capabilities` for the fields.
        """
        return Capabilities()

    async def pre_hook(
        self, configs: list[dict[str, Any]], context: PolicyContext
    ) -> PolicyContext:
        """Pre-hook executed before endpoint processing.

        Receives ALL configurations for this policy type attached to the endpoint.
        The policy type decides its own aggregation logic (AND/OR/custom).

        Args:
            configs: List of configurations for all policies of this type
            context: Policy context with request information

        Returns:
            Modified context (can add metadata, modify request, etc.)

        Raises:
            PolicyViolationError: To abort request processing
        """
        ...

    async def post_hook(
        self, configs: list[dict[str, Any]], context: PolicyContext
    ) -> PolicyContext:
        """Post-hook executed after endpoint processing.

        Receives ALL configurations for this policy type attached to the endpoint.
        The policy type decides its own aggregation logic (AND/OR/custom).

        Args:
            configs: List of configurations for all policies of this type
            context: Policy context with request and response

        Returns:
            Modified context (can modify response, add metadata, etc.)

        Raises:
            PolicyViolationError: To abort response (data integrity - e.g., if
                accounting transaction confirmation fails)
        """
        ...

    @classmethod
    def enabled(cls) -> bool:
        """Check if this policy type is enabled.

        Returns:
            True if enabled, False otherwise
        """
        ...

    @classmethod
    async def validate_config(cls, config: dict[str, Any]) -> dict[str, Any]:
        """Validate and normalize configuration.

        Any additional network connection tests can be performed here.

        Args:
            config: Configuration dictionary to validate

        Returns:
            Validated configuration dictionary

        Raises:
            ValueError: If configuration is invalid
        """
        ...
