"""Registry for dataset types and provisioners."""

from __future__ import annotations

from syft_space.components.dataset_types.interfaces import (
    BaseDatasetType,
    BaseDatasetTypeProvisioner,
)


class DatasetTypeRegistry:
    """Registry class for dataset types and provisioners."""

    _dataset_types: dict[str, type[BaseDatasetType]] = {}
    _provisioners: dict[str, type[BaseDatasetTypeProvisioner]] = {}

    def get_dataset_type(self, name: str) -> type[BaseDatasetType]:
        """Get dataset type class by name.

        Args:
            name: Name of the dataset type

        Returns:
            Dataset type class

        Raises:
            KeyError: If no dataset type found for name
        """
        try:
            return self._dataset_types[name]
        except KeyError:
            raise KeyError(f"No dataset type for name '{name}'") from None

    def get_provisioner(self, name: str) -> type[BaseDatasetTypeProvisioner] | None:
        """Get dataset type provisioner class by name.

        Args:
            name: Name of the provisioner

        Returns:
            Provisioner class

        Raises:
            KeyError: If no provisioner found for name
        """
        return self._provisioners.get(name)

    def list_dataset_types(self) -> list[str]:
        """List all registered dataset type names.

        Returns:
            Sorted list of dataset type names
        """
        return sorted(self._dataset_types.keys())

    def list_provisioners(self) -> list[str]:
        """List all registered dataset type provisioner names.

        Returns:
            Sorted list of provisioner names
        """
        return sorted(self._provisioners.keys())

    def is_dataset_type_registered(self, name: str) -> bool:
        """Check if a dataset type is registered.

        Args:
            name: Name of the dataset type

        Returns:
            True if registered, False otherwise
        """
        return name in self._dataset_types

    def is_provisioner_registered(self, name: str) -> bool:
        """Check if a provisioner is registered.

        Args:
            name: Name of the provisioner

        Returns:
            True if registered, False otherwise
        """
        return name in self._provisioners

    def register_dataset_type(self, cls: type[BaseDatasetType]) -> None:
        """Register a dataset type.

        Args:
            cls: Dataset type class to register

        Raises:
            ValueError: If class missing NAME or already registered
        """
        key = getattr(cls, "NAME", None)
        if not key:
            raise ValueError(f"{cls.__name__} missing NAME")
        if key in self._dataset_types:
            raise ValueError(f"Dataset type already registered for name '{key}'")
        self._dataset_types[key] = cls

    def register_provisioner(self, cls: type[BaseDatasetTypeProvisioner]) -> None:
        """Register a dataset type provisioner.

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
                f"Dataset type provisioner already registered for name '{key}'"
            )
        self._provisioners[key] = cls


# Global singleton registry instance
DATASET_TYPE_REGISTRY = DatasetTypeRegistry()
