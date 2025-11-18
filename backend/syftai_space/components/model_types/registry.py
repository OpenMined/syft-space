"""Registry for model types and provisioners."""

from __future__ import annotations

from syftai_space.components.model_types.interfaces import (
    BaseModelType,
    BaseModelTypeProvisioner,
)


class ModelTypeRegistry:
    """Registry class for model types and provisioners."""

    _model_types: dict[str, type[BaseModelType]] = {}
    _provisioners: dict[str, type[BaseModelTypeProvisioner]] = {}

    def get_model_type(self, name: str) -> type[BaseModelType]:
        """Get model type class by name.

        Args:
            name: Name of the model type

        Returns:
            Model type class

        Raises:
            KeyError: If no model type found for name
        """
        try:
            return self._model_types[name]
        except KeyError:
            raise KeyError(f"No model type for name '{name}'") from None

    def get_provisioner(self, name: str) -> type[BaseModelTypeProvisioner]:
        """Get model type provisioner class by name.

        Args:
            name: Name of the provisioner

        Returns:
            Provisioner class

        Raises:
            KeyError: If no provisioner found for name
        """
        try:
            return self._provisioners[name]
        except KeyError:
            raise KeyError(f"No model type provisioner for name '{name}'") from None

    def list_model_types(self) -> list[str]:
        """List all registered model type names.

        Returns:
            Sorted list of model type names
        """
        return sorted(self._model_types.keys())

    def list_provisioners(self) -> list[str]:
        """List all registered model type provisioner names.

        Returns:
            Sorted list of provisioner names
        """
        return sorted(self._provisioners.keys())

    def is_model_type_registered(self, name: str) -> bool:
        """Check if a model type is registered.

        Args:
            name: Name of the model type

        Returns:
            True if registered, False otherwise
        """
        return name in self._model_types

    def is_provisioner_registered(self, name: str) -> bool:
        """Check if a provisioner is registered.

        Args:
            name: Name of the provisioner

        Returns:
            True if registered, False otherwise
        """
        return name in self._provisioners

    def register_model_type(self, cls: type[BaseModelType]) -> None:
        """Register a model type.

        Args:
            cls: Model type class to register

        Raises:
            ValueError: If class missing NAME or already registered
        """
        key = getattr(cls, "NAME", None)
        if not key:
            raise ValueError(f"{cls.__name__} missing NAME")
        if key in self._model_types:
            raise ValueError(f"Model type already registered for name '{key}'")
        self._model_types[key] = cls

    def register_provisioner(self, cls: type[BaseModelTypeProvisioner]) -> None:
        """Register a model type provisioner.

        Args:
            cls: Provisioner class to register

        Raises:
            ValueError: If class missing NAME or already registered
        """
        key = getattr(cls, "NAME", None)
        if not key:
            raise ValueError(f"{cls.__name__} missing NAME")
        if key in self._provisioners:
            raise ValueError(
                f"Model type provisioner already registered for name '{key}'"
            )
        self._provisioners[key] = cls


# Global singleton registry instance
MODEL_TYPE_REGISTRY = ModelTypeRegistry()
