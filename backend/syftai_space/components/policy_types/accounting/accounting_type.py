"""Accounting policy type implementation."""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field
from syft_accounting_sdk import UserClient

from syftai_space.components.policy_types.interfaces import (
    BasePolicyType,
    PolicyContext,
)
from syftai_space.components.shared.utils import (
    ConfigSchemaGenerator,
    matches_any_pattern,
)


class PricingMode(str, Enum):
    """Pricing mode for accounting.

    PER_CALL: Fixed price per API call
    PER_TOKEN: Price based on token usage
    """

    PER_CALL = "per_call"


class AccountingConfig(BaseModel):
    """Configuration schema for accounting policy."""

    price: float = Field(
        ...,
        ge=0,
        description="Price per unit",
    )
    pricing_mode: PricingMode = Field(
        default=PricingMode.PER_CALL,
        description="Pricing mode: per_call (fixed per request) or per_token (based on token usage)",
    )
    applied_to: list[str] = Field(
        default_factory=lambda: ["*"],
        description="List of user emails or glob patterns (e.g., '*@company.com'). Use '*' for all users.",
    )


class AccountingCredentials(BaseModel):
    """Credentials for the accounting service."""

    email: str
    password: str
    url: str

    @classmethod
    def from_context(cls, context: PolicyContext) -> "AccountingCredentials":
        """Create credentials from the policy context.

        Credentials are injected into context.metadata by the endpoint handler,
        sourced from the default Marketplace's accounting credentials.
        Credentials are validated upfront before being passed to policies.
        """
        try:
            return cls(
                email=context.metadata["accounting_email"],
                password=context.metadata["accounting_password"],
                url=context.metadata["accounting_url"],
            )
        except KeyError as e:
            raise ValueError(
                f"Missing accounting credential: {e.args[0]}. "
                "Ensure a marketplace is registered with accounting credentials."
            ) from e


class AccountingPolicy(BasePolicyType):
    """Accounting policy type.

    Tracks and bills API usage based on calls or tokens.
    Credentials are injected into PolicyContext.metadata from the Marketplace entity.
    Credentials are validated upfront by the endpoint handler before being passed here.

    This policy is stateless - accounting records are managed by the external accounting SDK.
    """

    NAME = "accounting"

    def __init__(self, config: dict[str, Any]) -> None:
        """Initialize the accounting policy.

        Args:
            config: Configuration dictionary matching AccountingConfig schema
        """
        self.config = AccountingConfig(**config)

    @classmethod
    def name(cls) -> str:
        """Get the name of the policy type."""
        return cls.NAME

    @classmethod
    def description(cls) -> str:
        """Get the description of the policy type."""
        return "Track and bill API usage based on calls or tokens"

    @classmethod
    def icon(cls) -> str:
        """Get the icon for the policy type."""
        return "💰"

    @classmethod
    def configuration_schema(cls) -> dict[str, Any]:
        """Return configuration schema required by this policy type.

        Returns:
            Clean JSON schema with properties and required fields only
        """
        return AccountingConfig.model_json_schema(
            schema_generator=ConfigSchemaGenerator
        )

    def _applies_to_user(self, user_email: str) -> bool:
        """Check if the policy applies to the given user.

        Args:
            user_email: Email of the user

        Returns:
            True if the policy applies to this user
        """
        return matches_any_pattern(user_email, self.config.applied_to)

    def pre_hook(self, context: PolicyContext) -> PolicyContext:
        """Pre-hook to create a delegated transaction before endpoint execution.

        Credentials are read from context.metadata (validated upfront by endpoint handler).

        Args:
            context: Policy context with request information

        Returns:
            Context with transaction_id and transaction_amount in metadata
        """
        user_email = str(context.sender_email)

        # Skip if policy doesn't apply to this user
        if not self._applies_to_user(user_email):
            return context

        if self.config.pricing_mode != PricingMode.PER_CALL:
            raise ValueError("Only PER_CALL pricing mode is supported")

        if self.config.price == 0:
            # No transaction needed for free requests
            return context

        transaction_token = context.request.get("transaction_token")
        if not transaction_token:
            raise ValueError(
                "Transaction token is required. Please add it to the request."
            )

        credentials = AccountingCredentials.from_context(context)
        amount = self.config.price

        try:
            transaction = self._create_transaction(
                credentials,
                context.sender_email,
                amount,
                transaction_token,
                context.endpoint_slug,
            )
        except Exception as e:
            raise ValueError(f"Failed to create accounting transaction: {e}") from e

        context.metadata["transaction_id"] = transaction.id
        context.metadata["transaction_amount"] = amount
        return context

    def _create_transaction(
        self,
        credentials: AccountingCredentials,
        sender_email: str,
        amount: float,
        transaction_token: str,
        endpoint_slug: str,
    ):
        """Create a delegated transaction with the accounting service."""
        accounting_client = UserClient(
            url=credentials.url,
            email=credentials.email,
            password=credentials.password,
        )
        return accounting_client.create_delegated_transaction(
            senderEmail=sender_email,
            amount=amount,
            transaction_token=transaction_token,
            appEpPath=endpoint_slug,
        )

    def post_hook(self, context: PolicyContext) -> PolicyContext:
        """Post-hook to confirm the transaction after successful endpoint execution.

        Args:
            context: Policy context with request and response

        Returns:
            Unmodified context
        """
        user_email = str(context.sender_email)

        # Skip if policy doesn't apply to this user
        if not self._applies_to_user(user_email):
            return context

        if self.config.price == 0:
            # No transaction needed for free requests
            return context

        transaction_id = context.metadata.get("transaction_id")
        if not transaction_id:
            raise ValueError(
                "Transaction ID not found. The pre_hook may have failed or was skipped."
            )

        credentials = AccountingCredentials.from_context(context)

        try:
            self._confirm_transaction(credentials, transaction_id)
        except Exception as e:
            raise ValueError(f"Failed to confirm accounting transaction: {e}") from e

        return context

    def _confirm_transaction(
        self, credentials: AccountingCredentials, transaction_id: str
    ) -> None:
        """Confirm a transaction with the accounting service."""
        accounting_client = UserClient(
            url=credentials.url,
            email=credentials.email,
            password=credentials.password,
        )
        accounting_client.confirm_transaction(id=transaction_id)

    @classmethod
    def enabled(cls) -> bool:
        """Check if this policy type is enabled.

        Returns:
            True (always enabled)
        """
        return True

    @classmethod
    def validate_config(cls, config: dict[str, Any]) -> dict[str, Any]:
        """Validate configuration against AccountingConfig schema.

        Args:
            config: Configuration dictionary to validate

        Returns:
            Validated configuration dictionary

        Raises:
            ValueError: If configuration is invalid
        """
        try:
            validated = AccountingConfig(**config)
            return validated.model_dump()
        except Exception as e:
            raise ValueError(f"Invalid accounting config: {e}") from e
