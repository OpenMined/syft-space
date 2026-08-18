"""Endpoint access policy type implementation."""

from typing import Any

from pydantic import BaseModel, Field

from syft_space.components.policy_types.interfaces import (
    BasePolicyType,
    PolicyContext,
    PolicyMetadataEntry,
    PolicyRejection,
    PolicyViolationError,
    ReasonCode,
)
from syft_space.components.shared.utils import (
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

    Aggregation: OR logic - if ANY access policy allows, access is granted.
    Ordering: Policies are sorted by specificity (most specific patterns first).

    This policy is stateless.
    """

    NAME = "access"

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

    async def pre_hook(
        self, configs: list[dict[str, Any]], context: PolicyContext
    ) -> PolicyContext:
        """Pre-hook to enforce access control with OR logic.

        If ANY policy allows access, the user is granted access.
        Policies are sorted by specificity (most specific patterns checked first).

        Args:
            configs: List of configurations for all access policies
            context: Policy context with request information

        Returns:
            Modified context with access metadata

        Raises:
            PolicyViolationError: If ALL policies deny access
        """
        if not configs:
            return context

        user_email = str(context.sender_email)

        # Validate all configs upfront
        validated = [AccessPolicyConfig(**c) for c in configs]

        # Sort by specificity (most specific first)
        sorted_configs = sorted(validated, key=self._specificity_score, reverse=True)

        denial_reasons = []
        for config in sorted_configs:
            is_allowed, reason = self._check_access(user_email, config)
            if is_allowed:
                # First match wins in OR logic
                return context
            denial_reasons.append(reason)

        # All policies denied - abort
        message = f"Access denied: {'; '.join(denial_reasons)}"
        raise PolicyViolationError(
            message=message,
            policy_type=self.NAME,
            details={"user": user_email, "reasons": denial_reasons},
            outcome=PolicyRejection.ACCESS_DENIED,
            metadata_entry=PolicyMetadataEntry(
                policy_type=self.NAME,
                kind="access",
                status="rejected",
                reason_code=ReasonCode.ACCESS_DENIED,
                reason=message,
            ),
        )

    async def post_hook(
        self, configs: list[dict[str, Any]], context: PolicyContext
    ) -> PolicyContext:
        """Post-hook (no-op for access control).

        Args:
            configs: List of configurations for all access policies
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
    async def validate_config(cls, config: dict[str, Any]) -> dict[str, Any]:
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

    def _specificity_score(self, config: AccessPolicyConfig) -> int:
        """Calculate specificity score for ordering.

        Uses literal character count approach (similar to nginx longest prefix match).
        More literal characters = more specific. Fewer wildcards = more specific.

        Args:
            config: Validated access policy configuration

        Returns:
            Specificity score (higher = more specific)
        """
        return sum(
            self._pattern_specificity(p)
            for p in config.allowed_users + config.denied_users
        )

    def _pattern_specificity(self, pattern: str) -> int:
        """Calculate specificity for a single pattern.

        Scoring logic:
        - More literal characters = higher score
        - Fewer wildcards = higher score
        - Exact match (no wildcards) gets a bonus

        Examples:
            "*"                    → 0
            "*@company.com"        → 10  (12 literal - 2 penalty)
            "admin-*@company.com"  → 17  (19 literal - 2 penalty)
            "admin@company.com"    → 117 (17 literal + 100 exact match bonus)

        Args:
            pattern: Glob pattern string

        Returns:
            Specificity score (higher = more specific)
        """
        if pattern == "*":
            return 0

        wildcard_count = pattern.count("*")
        literal_count = len(pattern) - wildcard_count

        # Exact match gets a bonus
        if wildcard_count == 0:
            return literal_count + 100

        # Score: literal chars minus penalty for wildcards
        return literal_count - (wildcard_count * 2)

    def _best_matching_pattern(
        self, user_email: str, patterns: list[str]
    ) -> str | None:
        """Find the most specific pattern that matches the user.

        Args:
            user_email: Email of the user
            patterns: List of glob patterns to check

        Returns:
            The most specific matching pattern, or None if no match
        """
        matches = [p for p in patterns if matches_any_pattern(user_email, [p])]
        if not matches:
            return None
        # Return the most specific matching pattern
        return max(matches, key=self._pattern_specificity)

    def _check_access(
        self, user_email: str, config: AccessPolicyConfig
    ) -> tuple[bool, str]:
        """Check if a user has access based on specificity-based precedence.

        When a user matches both allowed and denied patterns, the more specific
        pattern wins. If equal specificity, deny wins (security tiebreaker).

        Args:
            user_email: Email of the user
            config: Access policy configuration

        Returns:
            Tuple of (is_allowed, reason)
        """
        # Find best matching patterns in each list
        denied_match = self._best_matching_pattern(user_email, config.denied_users)
        allowed_match = self._best_matching_pattern(user_email, config.allowed_users)

        # Case 1: No matches in either list
        if not denied_match and not allowed_match:
            # If allowed_users is empty, default allow; otherwise deny
            if not config.allowed_users:
                return True, "Open access (no whitelist configured)"
            return False, "User does not match any allowed pattern"

        # Case 2: Only denied match
        if denied_match and not allowed_match:
            return False, f"User matches denied pattern '{denied_match}'"

        # Case 3: Only allowed match
        if allowed_match and not denied_match:
            return True, f"User matches allowed pattern '{allowed_match}'"

        # Case 4: Both match - compare specificity
        denied_score = self._pattern_specificity(denied_match)
        allowed_score = self._pattern_specificity(allowed_match)

        if allowed_score > denied_score:
            return True, f"User matches allowed pattern '{allowed_match}'"
        else:
            # Deny wins on tie (security default)
            return False, f"User matches denied pattern '{denied_match}'"
