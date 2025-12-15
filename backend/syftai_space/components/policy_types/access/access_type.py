"""Endpoint access policy type implementation."""

from typing import Any

from pydantic import BaseModel, Field

from syftai_space.components.policy_types.interfaces import (
    BasePolicyType,
    PolicyContext,
)
from syftai_space.components.shared.utils import (
    ConfigSchemaGenerator,
    matches_any_pattern,
)


class AccessPolicyConfig(BaseModel):
    """Configuration schema for access policy.

    Access control logic:
    1. If user matches denied_users pattern -> DENY (blacklist takes priority)
    2. If allowed_users is empty -> ALLOW (open to everyone except denied)
    3. If user matches allowed_users pattern -> ALLOW
    4. Otherwise -> DENY

    Supports glob patterns: `*` (all), `*@company.com` (domain), `admin-*@*` (prefix).
    """

    allowed_users: list[str] = Field(
        default_factory=list,
        description="Glob patterns for allowed users. Examples: '*@company.com', 'admin-*@*', '*'. Empty means everyone allowed.",
    )
    denied_users: list[str] = Field(
        default_factory=list,
        description="Glob patterns for denied users. Takes priority over allowed_users. Examples: 'banned@*', '*@competitor.com'.",
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

    @classmethod
    def validate_config(cls, config: dict[str, Any]) -> dict[str, Any]:
        """Validate configuration against AccessPolicyConfig schema.

        Args:
            config: Configuration dictionary to validate

        Returns:
            Validated configuration dictionary

        Raises:
            ValueError: If configuration is invalid
        """
        try:
            validated = AccessPolicyConfig(**config)
            return validated.model_dump()
        except Exception as e:
            raise ValueError(f"Invalid access policy config: {e}") from e

    def _check_access(self, user_email: str) -> tuple[bool, str]:
        """Check if a user has access.

        Args:
            user_email: Email of the user

        Returns:
            Tuple of (is_allowed, reason)
        """
        # Rule 1: Blacklist takes priority
        if matches_any_pattern(user_email, self.config.denied_users):
            return False, "User matches denied pattern"

        # Rule 2: If allowed_users is empty, everyone is allowed (except denied)
        if not self.config.allowed_users:
            return True, "Open access (no whitelist configured)"

        # Rule 3: Check if user matches whitelist pattern
        if matches_any_pattern(user_email, self.config.allowed_users):
            return True, "User matches allowed pattern"

        # Rule 4: User doesn't match whitelist
        return False, "User does not match any allowed pattern"
