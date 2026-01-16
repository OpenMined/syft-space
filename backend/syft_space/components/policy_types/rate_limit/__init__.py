"""Rate limit policy type."""

from syft_space.components.policy_types.rate_limit.limiter import (
    InMemoryRateLimitStorage,
    RateLimitStorage,
    check_rate_limit,
    get_rate_limit_stats,
    get_storage,
    set_storage,
)
from syft_space.components.policy_types.rate_limit.rate_limit_type import (
    EndpointRateLimitPolicy,
    LimitScope,
    RateLimitConfig,
)

# Backward compatibility alias
RateLimitPolicyType = EndpointRateLimitPolicy

__all__ = [
    # Policy class
    "EndpointRateLimitPolicy",
    "RateLimitPolicyType",  # Deprecated alias
    "RateLimitConfig",
    "LimitScope",
    # Limiter functions
    "RateLimitStorage",
    "InMemoryRateLimitStorage",
    "set_storage",
    "get_storage",
    "check_rate_limit",
    "get_rate_limit_stats",
]
