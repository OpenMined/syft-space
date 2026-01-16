"""Accounting policy type implementation."""

from enum import Enum
from typing import Any

from pydantic import BaseModel, EmailStr, Field, HttpUrl
from syft_accounting_sdk import UserClient

from syft_space.components.policy_types.interfaces import (
    BasePolicyType,
    PolicyContext,
    PolicyViolationError,
)
from syft_space.components.shared.utils import (
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

    email: EmailStr
    password: str
    url: HttpUrl

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

    Aggregation: AND logic - ALL accounting policies must succeed.

    This policy is stateless - accounting records are managed by the external accounting SDK.
    """

    NAME = "accounting"

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

    def _applies_to_user(self, user_email: str, config: AccountingConfig) -> bool:
        """Check if the policy applies to the given user.

        Args:
            user_email: Email of the user
            config: Accounting configuration

        Returns:
            True if the policy applies to this user
        """
        return matches_any_pattern(user_email, config.applied_to)

    def pre_hook(
        self, configs: list[dict[str, Any]], context: PolicyContext
    ) -> PolicyContext:
        """Pre-hook to create delegated transactions before endpoint execution.

        AND logic - ALL accounting policies must succeed.
        Credentials are read from context.metadata (validated upfront by endpoint handler).

        Args:
            configs: List of configurations for all accounting policies
            context: Policy context with request information

        Returns:
            Context with transaction_ids and total_amount in metadata

        Raises:
            PolicyViolationError: If any transaction creation fails
        """
        if not configs:
            return context

        user_email = str(context.sender_email)
        transaction_token = context.request.get("transaction_token")

        # Validate all configs upfront
        validated = [AccountingConfig(**c) for c in configs]

        # Track all transactions created for confirmation in post_hook
        transactions = []
        total_amount = 0.0

        for config in validated:
            # Skip if policy doesn't apply to this user
            if not self._applies_to_user(user_email, config):
                continue

            if config.pricing_mode != PricingMode.PER_CALL:
                raise PolicyViolationError(
                    message="Only PER_CALL pricing mode is supported",
                    policy_type=self.NAME,
                    details={"pricing_mode": config.pricing_mode.value},
                )

            if config.price == 0:
                # No transaction needed for free requests
                continue

            if not transaction_token:
                raise PolicyViolationError(
                    message="Transaction token is required. Please add it to the request.",
                    policy_type=self.NAME,
                    details={"user": user_email},
                )

            credentials = AccountingCredentials.from_context(context)
            amount = config.price

            transaction = None
            try:
                transaction = self._create_transaction(
                    credentials,
                    context.sender_email,
                    amount,
                    transaction_token,
                    context.endpoint_slug,
                )
                transactions.append({"id": transaction.id, "amount": amount})
                total_amount += amount
            except Exception as e:
                if transaction:
                    self._cancel_transaction(credentials, transaction.id)

                raise PolicyViolationError(
                    message=f"Failed to create accounting transaction: {e}",
                    policy_type=self.NAME,
                    details={"user": user_email, "amount": amount},
                ) from e

        # Store all transaction info for post_hook
        context.metadata["accounting_transactions"] = transactions
        context.metadata["accounting_total_amount"] = total_amount
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
            url=str(credentials.url),
            email=str(credentials.email),
            password=credentials.password,
        )
        return accounting_client.create_delegated_transaction(
            senderEmail=sender_email,
            amount=amount,
            token=transaction_token,
            appEpPath=endpoint_slug,
        )

    def post_hook(
        self, configs: list[dict[str, Any]], context: PolicyContext
    ) -> PolicyContext:
        """Post-hook to confirm transactions after successful endpoint execution.

        AND logic - ALL transactions must be confirmed.

        Args:
            configs: List of configurations for all accounting policies
            context: Policy context with request and response

        Returns:
            Context with cost information added to response

        Raises:
            PolicyViolationError: If any transaction confirmation fails
        """
        if not configs:
            return context

        transactions = context.metadata.get("accounting_transactions", [])
        total_amount = context.metadata.get("accounting_total_amount", 0.0)

        if not transactions:
            # No transactions to confirm
            return context

        credentials = AccountingCredentials.from_context(context)

        # Confirm all transactions
        for transaction in transactions:
            try:
                self._confirm_transaction(credentials, transaction["id"])
            except Exception as e:
                if transaction.get("id"):
                    self._cancel_transaction(credentials, transaction["id"])

                raise PolicyViolationError(
                    message=f"Failed to confirm accounting transaction: {e}",
                    policy_type=self.NAME,
                    details={
                        "transaction_id": transaction["id"],
                        "amount": transaction["amount"],
                    },
                ) from e

        # Update response with total cost
        if context.response:
            if context.response.get("summary"):
                context.response["summary"]["cost"] = total_amount
            if context.response.get("references"):
                context.response["references"]["cost"] = total_amount

        return context

    def _cancel_transaction(
        self, credentials: AccountingCredentials, transaction_id: str
    ) -> None:
        """Cancel a transaction with the accounting service."""
        accounting_client = UserClient(
            url=str(credentials.url),
            email=str(credentials.email),
            password=credentials.password,
        )
        accounting_client.cancel_transaction(id=transaction_id)

    def _confirm_transaction(
        self, credentials: AccountingCredentials, transaction_id: str
    ) -> None:
        """Confirm a transaction with the accounting service."""
        accounting_client = UserClient(
            url=str(credentials.url),
            email=str(credentials.email),
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
