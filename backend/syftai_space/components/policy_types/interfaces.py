"""Policy type interfaces and domain models."""

from typing import Any, Optional, Protocol

from pydantic import BaseModel, EmailStr, Field


class PolicyContext(BaseModel):
    """Domain context for policy execution.

    Passed to policy hooks with request/response information.
    """

    endpoint_slug: str = Field(..., description="Slug of the endpoint being accessed")
    sender_email: EmailStr = Field(..., description="Email of the request sender")
    request: dict[str, Any] = Field(..., description="Request payload")
    response: Optional[dict[str, Any]] = Field(
        default=None, description="Response payload (for post hooks)"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )


class BasePolicyType(Protocol):
    """Base policy type interface.

    All concrete policy types must implement this protocol.
    Policies are pre/post hooks applied to endpoint requests.
    """

    NAME: str

    def __init__(self, config: dict[str, Any]) -> None:
        """Initialize the policy type with configuration.

        Args:
            config: Configuration dictionary for this policy type
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

    def pre_hook(self, context: PolicyContext) -> PolicyContext:
        """Pre-hook executed before endpoint processing.

        Can modify context or raise exceptions to block requests.

        Args:
            context: Policy context with request information

        Returns:
            Modified context (can add metadata, modify request, etc.)

        Raises:
            Exception: To block the request
        """
        ...

    def post_hook(self, context: PolicyContext) -> PolicyContext:
        """Post-hook executed after endpoint processing.

        Can modify response or perform logging/accounting.

        Args:
            context: Policy context with request and response

        Returns:
            Modified context (can modify response, add metadata, etc.)
        """
        ...

    @classmethod
    def enabled(cls) -> bool:
        """Check if this policy type is enabled.

        Returns:
            True if enabled, False otherwise
        """
        ...
