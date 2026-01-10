"""Endpoint rate limit policy type implementation."""

import re
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator

from syftai_space.components.policy_types.interfaces import (
    BasePolicyType,
    PolicyContext,
    PolicyViolationError,
)
from syftai_space.components.policy_types.rate_limit.limiter import (
    check_rate_limit,
    get_rate_limit_stats,
)
from syftai_space.components.shared.utils import (
    ConfigSchemaGenerator,
    matches_any_pattern,
)


class LimitScope(str, Enum):
    """Scope of the rate limit.

    PER_USER: Each user has their own rate limit counter
    GLOBAL: All users share the same rate limit counter for the endpoint
    """

    PER_USER = "per_user"
    GLOBAL = "global"


class RateLimitConfig(BaseModel):
    """Configuration schema for rate limit policy."""

    limit: str = Field(
        ...,
        description='Rate limit in format "N/unit" where unit is s(econds), m(inutes), or h(ours)',
        examples=["50/m", "1000/h", "100/s"],
    )
    scope: LimitScope = Field(
        default=LimitScope.PER_USER,
        description="Scope: per_user (each user has own limit) or global (shared across all users)",
    )
    applied_to: list[str] = Field(
        default_factory=lambda: ["*"],
        description="List of user emails or '*' for all users",
    )

    @field_validator("limit")
    @classmethod
    def validate_limit_format(cls, v: str) -> str:
        """Validate the limit format.

        Args:
            v: The limit string to validate

        Returns:
            The validated limit string

        Raises:
            ValueError: If the limit format is invalid
        """
        pattern = r"^(\d+)/(s|m|h)$"
        match = re.match(pattern, v)
        if not match:
            raise ValueError(
                'Invalid limit format. Must be "N/unit" where N is a number '
                "and unit is s (seconds), m (minutes), or h (hours). "
                'Examples: "50/m", "1000/h", "100/s"'
            )
        count = int(match.group(1))
        if count <= 0:
            raise ValueError("Rate limit count must be positive")
        return v

    def parse_limit(self) -> tuple[int, int]:
        """Parse the limit string into count and seconds.

        Returns:
            Tuple of (count, window_seconds)
        """
        match = re.match(r"^(\d+)/(s|m|h)$", self.limit)
        if not match:
            raise ValueError(f"Invalid limit format: {self.limit}")

        count = int(match.group(1))
        unit = match.group(2)

        # Convert to seconds
        unit_seconds = {"s": 1, "m": 60, "h": 3600}
        window_seconds = unit_seconds[unit]

        return count, window_seconds

    def get_friendly_description(self) -> str:
        """Get a user-friendly description of the rate limit.

        Returns:
            Human-readable description
        """
        count, window_seconds = self.parse_limit()

        if window_seconds == 1:
            time_unit = "second"
        elif window_seconds == 60:
            time_unit = "minute"
        elif window_seconds == 3600:
            time_unit = "hour"
        else:
            time_unit = f"{window_seconds} second"

        time_str = f"{window_seconds // (60 if time_unit == 'minute' else (3600 if time_unit == 'hour' else 1))} {time_unit}(s)"

        return f"{count} requests per {time_str}"


class EndpointRateLimitPolicy(BasePolicyType):
    """Endpoint rate limit policy type.

    Limits the number of requests that can be made within a time window.
    Supports per-user and global scoping with selective application to specific users.

    Aggregation: AND logic - ALL rate limits must pass.
    Ordering: Policies are sorted by most restrictive first (fail fast).

    This policy is stateless - rate limit history is managed by the limiter module.
    """

    NAME = "rate_limit"

    @classmethod
    def name(cls) -> str:
        """Get the name of the policy type."""
        return cls.NAME

    @classmethod
    def description(cls) -> str:
        """Get the description of the policy type."""
        return (
            "Limit the number of requests that can be made within a time window. "
            "Supports per-user rate limiting and selective application to specific users."
        )

    @classmethod
    def icon(cls) -> str:
        """Get the icon for the policy type."""
        return "⏱️"

    @classmethod
    def configuration_schema(cls) -> dict[str, Any]:
        """Return configuration schema required by this policy type.

        Returns:
            Clean JSON schema with properties and required fields only
        """
        return RateLimitConfig.model_json_schema(schema_generator=ConfigSchemaGenerator)

    def pre_hook(
        self, configs: list[dict[str, Any]], context: PolicyContext
    ) -> PolicyContext:
        """Pre-hook to enforce rate limiting with AND logic.

        ALL rate limits must pass. Policies are sorted by most restrictive first
        (fail fast on strictest limit).

        Args:
            configs: List of configurations for all rate limit policies
            context: Policy context with request information

        Returns:
            Modified context

        Raises:
            PolicyViolationError: If ANY rate limit is exceeded
        """
        if not configs:
            return context

        user_email = str(context.sender_email)

        # Validate all configs upfront
        validated = [RateLimitConfig(**c) for c in configs]

        # Sort by limit count (most restrictive first for early failure)
        sorted_configs = sorted(validated, key=self._parse_limit_count)

        for config in sorted_configs:
            # Check if policy applies to this user
            if not self._applies_to_user(user_email, config):
                continue

            # Get rate limit parameters
            count, window_seconds = config.parse_limit()

            # Build key based on scope
            if config.scope == LimitScope.PER_USER:
                key = f"{context.endpoint_slug}:{user_email}"
            else:  # GLOBAL
                key = context.endpoint_slug

            # Check and record using module-level limiter
            is_allowed, current_count = check_rate_limit(key, count, window_seconds)

            if not is_allowed:
                friendly_limit = config.get_friendly_description()
                _, reset_seconds = get_rate_limit_stats(key, count, window_seconds)
                raise PolicyViolationError(
                    message=(
                        f"Rate limit exceeded: {friendly_limit}. "
                        f"Requests in window: {current_count}. "
                        f"Try again in {reset_seconds}s."
                    ),
                    policy_type=self.NAME,
                    details={
                        "limit": config.limit,
                        "current_count": current_count,
                        "reset_seconds": reset_seconds,
                        "scope": config.scope.value,
                    },
                )

        return context

    def post_hook(
        self, configs: list[dict[str, Any]], context: PolicyContext
    ) -> PolicyContext:
        """Post-hook (no-op for rate limiting).

        Args:
            configs: List of configurations for all rate limit policies
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
        """Validate configuration against RateLimitConfig schema.

        Args:
            config: Configuration dictionary to validate

        Returns:
            Validated configuration dictionary

        Raises:
            ValueError: If configuration is invalid
        """
        try:
            validated = RateLimitConfig(**config)
            return validated.model_dump()
        except Exception as e:
            raise ValueError(f"Invalid rate limit config: {e}") from e

    def _parse_limit_count(self, config: RateLimitConfig) -> int:
        """Parse limit count for sorting (lower = more restrictive).

        Args:
            config: Validated rate limit configuration

        Returns:
            The limit count for sorting purposes
        """
        match = re.match(r"^(\d+)/", config.limit)
        if match:
            return int(match.group(1))
        return 999999

    def _applies_to_user(self, user_email: str, config: RateLimitConfig) -> bool:
        """Check if the rate limit applies to a given user.

        Args:
            user_email: Email of the user
            config: Rate limit configuration

        Returns:
            True if the rate limit applies to this user
        """
        return matches_any_pattern(user_email, config.applied_to)
