"""Policy types package with type system for policies."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .registry import PolicyTypeRegistry


def register_builtin_types(registry: "PolicyTypeRegistry") -> None:
    """Register all built-in policy types.

    This is called explicitly from main.py - no import side effects.

    Args:
        registry: The policy type registry to register types with
    """
    # Import and register built-in policy types here as they're implemented
    from .access.access_type import EndpointAccessPolicy
    from .mpp_per_request.mpp_per_request_type import MppPerRequestPolicy
    from .rate_limit.rate_limit_type import EndpointRateLimitPolicy
    from .xendit_per_request.xendit_per_request_type import XenditPerRequestPolicy

    registry.register_policy_type(EndpointRateLimitPolicy)
    registry.register_policy_type(EndpointAccessPolicy)
    registry.register_policy_type(MppPerRequestPolicy)
    registry.register_policy_type(XenditPerRequestPolicy)


__all__ = ["register_builtin_types"]
