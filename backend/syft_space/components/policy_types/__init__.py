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
    from .cluster.cluster_per_document import ClusterPerDocumentPolicy
    from .cluster.cluster_per_request import ClusterPerRequestPolicy
    from .mpp.mpp_per_document import MppPerDocumentPolicy
    from .mpp.mpp_per_request import MppPerRequestPolicy
    from .pii_filter.pii_filter_type import PiiFilterType
    from .rate_limit.rate_limit_type import EndpointRateLimitPolicy
    from .stripe.stripe_per_document import StripePerDocumentPolicy
    from .stripe.stripe_per_request import StripePerRequestPolicy
    from .xendit.xendit_per_document import XenditPerDocumentPolicy
    from .xendit.xendit_per_request import XenditPerRequestPolicy

    registry.register_policy_type(EndpointRateLimitPolicy)
    registry.register_policy_type(EndpointAccessPolicy)
    registry.register_policy_type(MppPerRequestPolicy)
    registry.register_policy_type(MppPerDocumentPolicy)
    registry.register_policy_type(PiiFilterType)
    registry.register_policy_type(XenditPerRequestPolicy)
    registry.register_policy_type(XenditPerDocumentPolicy)
    registry.register_policy_type(StripePerRequestPolicy)
    registry.register_policy_type(ClusterPerRequestPolicy)
    registry.register_policy_type(ClusterPerDocumentPolicy)
    registry.register_policy_type(StripePerDocumentPolicy)


__all__ = ["register_builtin_types"]
