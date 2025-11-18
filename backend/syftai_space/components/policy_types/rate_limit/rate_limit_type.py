"""Rate limit policy type implementation."""

import re
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator

from syftai_space.components.policy_types.interfaces import (
    BasePolicyType,
    PolicyContext,
)


class LimitScope(str, Enum):
    """Scope of the rate limit."""

    PER_USER = "per_user"


class RateLimitConfig(BaseModel):
    """Configuration schema for rate limit policy."""

    limit: str = Field(
        ...,
        description='Rate limit in format "N/unit" where unit is s(econds), m(inutes), or h(ours)',
        examples=["50/m", "1000/h", "100/s"],
    )
    scope: LimitScope = Field(
        default=LimitScope.PER_USER,
        description="Scope of the rate limit",
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


class RateLimitPolicyType(BasePolicyType):
    """Rate limit policy type.

    Limits the number of requests that can be made within a time window.
    Supports per-user scoping and selective application to specific users.
    """

    NAME = "rate_limit"

    # TODO: Think about how we can use a more persistent storage for this.
    # In-memory storage for rate limiting (key: (endpoint_slug, user_email), value: list of timestamps)
    _request_history: dict[tuple[str, str], list[datetime]] = defaultdict(list)

    def __init__(self, config: dict[str, Any]) -> None:
        """Initialize the rate limit policy.

        Args:
            config: Configuration dictionary matching RateLimitConfig schema
        """
        self.config = RateLimitConfig(**config)

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
            JSON schema for RateLimitConfig
        """
        return RateLimitConfig.model_json_schema()

    def pre_hook(self, context: PolicyContext) -> PolicyContext:
        """Pre-hook to enforce rate limiting.

        Args:
            context: Policy context with request information

        Returns:
            Modified context

        Raises:
            Exception: If rate limit is exceeded
        """
        # Check if this user should be rate limited
        user_email = str(context.sender_email)

        # Check if policy applies to this user
        if not self._applies_to_user(user_email):
            return context

        # Get rate limit parameters
        count, window_seconds = self.config.parse_limit()

        # Get the key for tracking this user's requests
        if self.config.scope == LimitScope.PER_USER:
            key = (context.endpoint_slug, user_email)
        else:
            # Future: support other scopes (e.g., global)
            key = (context.endpoint_slug, user_email)

        # Clean up old requests outside the time window
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(seconds=window_seconds)

        # Get request history for this key
        history = self._request_history[key]

        # Remove requests outside the window
        history[:] = [ts for ts in history if ts > window_start]

        # Check if rate limit is exceeded
        if len(history) >= count:
            # Rate limit exceeded
            friendly_limit = self.config.get_friendly_description()
            raise Exception(
                f"Rate limit exceeded: {friendly_limit}. "
                f"Current requests in window: {len(history)}"
            )

        # Add current request to history
        history.append(now)

        # Add metadata about rate limit status
        context.metadata["rate_limit"] = {
            "limit": self.config.limit,
            "requests_in_window": len(history),
            "max_requests": count,
            "window_seconds": window_seconds,
        }

        return context

    def post_hook(self, context: PolicyContext) -> PolicyContext:
        """Post-hook (no-op for rate limiting).

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

    def _applies_to_user(self, user_email: str) -> bool:
        """Check if the rate limit applies to a given user.

        Args:
            user_email: Email of the user

        Returns:
            True if the rate limit applies to this user
        """
        if "*" in self.config.applied_to:
            return True
        return user_email in self.config.applied_to
