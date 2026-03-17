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
    from .accounting.accounting_type import AccountingPolicy
    from .rate_limit.rate_limit_type import EndpointRateLimitPolicy
    from .xendit.xendit_type import XenditPolicy

    registry.register_policy_type(EndpointRateLimitPolicy)
    registry.register_policy_type(EndpointAccessPolicy)
    registry.register_policy_type(AccountingPolicy)
    registry.register_policy_type(XenditPolicy)


__all__ = ["register_builtin_types"]
