from __future__ import annotations

from typing import Dict, List, Type

from .interfaces import BaseDatasetType, BaseDatasetTypeProvisioner


class DatasetTypeRegistry:
    """Registry class for dataset types and provisioners."""

    _dataset_types: Dict[str, Type[BaseDatasetType]] = {}
    _provisioners: Dict[str, Type[BaseDatasetTypeProvisioner]] = {}

    def get_dataset_type(self, name: str) -> Type[BaseDatasetType]:
        """Get dataset type class by name."""
        try:
            return self._dataset_types[name]
        except KeyError:
            raise KeyError(f"No dataset type for name '{name}'")

    def get_provisioner(self, name: str) -> Type[BaseDatasetTypeProvisioner]:
        """Get dataset type provisioner class by name."""
        try:
            return self._provisioners[name]
        except KeyError:
            raise KeyError(f"No dataset type provisioner for name '{name}'")

    def list_dataset_types(self) -> List[str]:
        """List all registered dataset type names."""
        return sorted(self._dataset_types.keys())

    def list_provisioners(self) -> List[str]:
        """List all registered dataset type provisioner names."""
        return sorted(self._provisioners.keys())

    def is_dataset_type_registered(self, name: str) -> bool:
        """Check if a dataset type is registered."""
        return name in self._dataset_types

    def is_provisioner_registered(self, name: str) -> bool:
        """Check if a provisioner is registered."""
        return name in self._provisioners

    def register_dataset_type(self, cls: Type[BaseDatasetType]) -> None:
        """Register a dataset type."""
        key = getattr(cls, "NAME", None)
        if not key:
            raise ValueError(f"{cls.__name__} missing NAME")
        if key in self._dataset_types:
            raise ValueError(f"Dataset type already registered for name '{key}'")
        self._dataset_types[key] = cls

    def register_provisioner(self, cls: Type[BaseDatasetTypeProvisioner]) -> None:
        key = getattr(cls, "NAME", None)
        if not key:
            raise ValueError(f"{cls.__name__} missing NAME")
        if key in self._provisioners:
            raise ValueError(
                f"Dataset type provisioner already registered for name '{key}'"
            )
        self._provisioners[key] = cls


DATASET_TYPE_REGISTRY = DatasetTypeRegistry()
