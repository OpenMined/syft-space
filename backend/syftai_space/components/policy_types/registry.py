"""Registry for policy types."""

from __future__ import annotations

from syftai_space.components.policy_types.interfaces import BasePolicyType


class PolicyTypeRegistry:
    """Registry class for policy types."""

    _policy_types: dict[str, type[BasePolicyType]] = {}

    def get_policy_type(self, name: str) -> type[BasePolicyType]:
        """Get policy type class by name.

        Args:
            name: Name of the policy type

        Returns:
            Policy type class

        Raises:
            KeyError: If no policy type found for name
        """
        try:
            return self._policy_types[name]
        except KeyError:
            raise KeyError(f"No policy type for name '{name}'") from None

    def list_policy_types(self) -> list[str]:
        """List all registered policy type names.

        Returns:
            Sorted list of policy type names
        """
        return sorted(self._policy_types.keys())

    def is_policy_type_registered(self, name: str) -> bool:
        """Check if a policy type is registered.

        Args:
            name: Name of the policy type

        Returns:
            True if registered, False otherwise
        """
        return name in self._policy_types

    def register_policy_type(self, cls: type[BasePolicyType]) -> None:
        """Register a policy type.

        Args:
            cls: Policy type class to register

        Raises:
            ValueError: If class missing NAME or already registered
        """
        key = getattr(cls, "NAME", None)
        if not key:
            raise ValueError(f"{cls.__name__} missing NAME")
        if key in self._policy_types:
            raise ValueError(f"Policy type already registered for name '{key}'")
        self._policy_types[key] = cls


# Global singleton registry instance
POLICY_TYPE_REGISTRY = PolicyTypeRegistry()
