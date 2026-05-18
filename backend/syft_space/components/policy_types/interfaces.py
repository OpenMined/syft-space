"""Policy type interfaces and domain models."""

from typing import Any, Protocol
from uuid import UUID

from mpp import Challenge, Credential, Receipt
from pydantic import BaseModel, ConfigDict, EmailStr, Field


class PolicyViolationError(Exception):
    """Raised when a policy rule is violated.

    This exception is used by policy hooks to signal that the request
    should be blocked (pre-hook) or the response should not be returned (post-hook).
    """

    def __init__(
        self, message: str, policy_type: str, details: dict[str, Any] | None = None
    ) -> None:
        """Initialize the PolicyViolationError.

        Args:
            message: Human-readable error message
            policy_type: Name of the policy type that raised the error
            details: Optional additional details about the error
        """
        super().__init__(message)
        self.policy_type = policy_type
        self.details = details or {}


class PaymentRequiredError(Exception):
    """Raised when MPP charge returns a Challenge (payment required).

    This is NOT a policy violation - it's a payment flow signal.
    The endpoint handler should catch this and return HTTP 402.
    """

    def __init__(self, www_authenticate: str, description: str | None = None):
        self.www_authenticate = www_authenticate
        self.description = description
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


class BalanceShortfallError(Exception):
    """Raised by XenditCharger.reserve when the user's balance is below
    the required amount.

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


class XenditCharger(Protocol):
    """Xendit wallet-bound charger for a single request.

    Constructed by the framework with wallet_id, currency, tenant_id, and
    endpoint_id bound. Policies pass only request-scoped data.
    """

    @property
    def currency(self) -> str:
        """Wallet currency code (e.g., 'IDR', 'USD'). Surfaced on responses."""
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

    Methods raise if the requested charger isn't built: by the time a
    policy's hook runs, CapabilityChecker has already validated that any
    declared required_wallet_type has a matching wallet attached. Missing
    chargers therefore indicate a framework bug, not a user-input error.

    Adding a new payment mechanism is one new method on this class plus a
    new branch in build_payment_chargers (see endpoints/policy_charging.py).
    """

    def __init__(
        self,
        *,
        mpp: MppCharger | None = None,
        xendit: XenditCharger | None = None,
    ) -> None:
        self._mpp = mpp
        self._xendit = xendit

    def mpp(self) -> MppCharger:
        if self._mpp is None:
            raise RuntimeError(
                "MPP charger requested but no MPP wallet is attached to this endpoint"
            )
        return self._mpp

    def xendit(self) -> XenditCharger:
        if self._xendit is None:
            raise RuntimeError(
                "Xendit charger requested but no Xendit wallet is attached to this endpoint"
            )
        return self._xendit


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
    wallet_shared_with_siblings: bool = True
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
        default_factory=dict, description="Additional metadata"
    )
    payment_chargers: PaymentChargers | None = Field(
        default=None,
        description="Per-request payment chargers, built from attached wallets",
    )


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
