"""Endpoint access policy type implementation."""

from typing import Any

from pydantic import BaseModel, EmailStr, Field

from syftai_space.components.policy_types.interfaces import (
    BasePolicyType,
    PolicyContext,
)
from syftai_space.components.shared.utils import ConfigSchemaGenerator


class AccessPolicyConfig(BaseModel):
    """Configuration schema for access policy.

    Access control logic:
    1. If user is in denied_users -> DENY (blacklist takes priority)
    2. If allowed_users is empty -> ALLOW (open to everyone except denied)
    3. If user is in allowed_users -> ALLOW
    4. Otherwise -> DENY
    """

    allowed_users: list[EmailStr] = Field(
        default_factory=list,
        description="List of user emails allowed to access. Empty means everyone is allowed (except denied users).",
    )
    denied_users: list[EmailStr] = Field(
        default_factory=list,
        description="List of user emails explicitly denied access. Takes priority over allowed_users.",
    )


class EndpointAccessPolicy(BasePolicyType):
    """Endpoint access policy type.

    Controls which users can access an endpoint based on whitelist/blacklist rules.
    Blacklist (denied_users) always takes priority over whitelist (allowed_users).

    This policy is stateless.
    """

    NAME = "access"

    def __init__(self, config: dict[str, Any]) -> None:
        """Initialize the access policy.

        Args:
            config: Configuration dictionary matching AccessPolicyConfig schema
        """
        self.config = AccessPolicyConfig(**config)

    @classmethod
    def name(cls) -> str:
        """Get the name of the policy type."""
        return cls.NAME

    @classmethod
    def description(cls) -> str:
        """Get the description of the policy type."""
        return (
            "Control access to endpoints using whitelist and blacklist rules. "
            "Denied users are always blocked, even if in the allowed list."
        )

    @classmethod
    def icon(cls) -> str:
        """Get the icon for the policy type."""
        return "🔐"

    @classmethod
    def configuration_schema(cls) -> dict[str, Any]:
        """Return configuration schema required by this policy type.

        Returns:
            Clean JSON schema with properties and required fields only
        """
        return AccessPolicyConfig.model_json_schema(
            schema_generator=ConfigSchemaGenerator
        )

    def pre_hook(self, context: PolicyContext) -> PolicyContext:
        """Pre-hook to enforce access control.

        Args:
            context: Policy context with request information

        Returns:
            Modified context with access metadata

        Raises:
            Exception: If user is denied access
        """
        user_email = str(context.sender_email)

        # Check access
        is_allowed, reason = self._check_access(user_email)

        if not is_allowed:
            raise Exception(f"Access denied: {reason}")

        # Add metadata about access status
        context.metadata[self.NAME] = {
            "allowed": True,
            "reason": reason,
            "user": user_email,
        }

        return context

    def post_hook(self, context: PolicyContext) -> PolicyContext:
        """Post-hook (no-op for access control).

        Args:
            context: Policy context with request and response

        Returns:
            Unmodified context
        """
        return context

    @classmethod
    def enabled(cls) -> bool:
        """Check if this policy type is enabled.

        Returns:
            True (always enabled)
        """
        return True

    def _check_access(self, user_email: str) -> tuple[bool, str]:
        """Check if a user has access.

        Args:
            user_email: Email of the user

        Returns:
            Tuple of (is_allowed, reason)
        """
        # Normalize email for comparison
        user_email_lower = user_email.lower()
        denied_lower = [str(e).lower() for e in self.config.denied_users]
        allowed_lower = [str(e).lower() for e in self.config.allowed_users]

        # Rule 1: Blacklist takes priority
        if user_email_lower in denied_lower:
            return False, "User is in denied list"

        # Rule 2: If allowed_users is empty, everyone is allowed (except denied)
        if not self.config.allowed_users:
            return True, "Open access (no whitelist configured)"

        # Rule 3: Check if user is in whitelist
        if user_email_lower in allowed_lower:
            return True, "User is in allowed list"

        # Rule 4: User not in whitelist
        return False, "User is not in allowed list"
