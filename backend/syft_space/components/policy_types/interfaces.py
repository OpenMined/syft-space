"""Policy type interfaces and domain models."""

from typing import Any, Protocol

from pydantic import BaseModel, EmailStr, Field


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


class PolicyContext(BaseModel):
    """Domain context for policy execution.

    Passed to policy hooks with request/response information.
    """

    endpoint_slug: str = Field(..., description="Slug of the endpoint being accessed")
    sender_email: EmailStr = Field(..., description="Email of the request sender")
    request: dict[str, Any] = Field(..., description="Request payload")
    response: dict[str, Any] | None = Field(
        default=None, description="Response payload (for post hooks)"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
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
