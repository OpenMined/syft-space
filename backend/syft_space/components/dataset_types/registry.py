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
    _lazy_dataset_types: dict[str, tuple[str, str]] = {}
    _lazy_provisioners: dict[str, tuple[str, str]] = {}

    def get_dataset_type(self, name: str) -> type[BaseDatasetType]:
        """Get dataset type class by name.

        Args:
            name: Name of the dataset type

        Returns:
            Dataset type class

        Raises:
            KeyError: If no dataset type found for name
        """
        if name in self._dataset_types:
            return self._dataset_types[name]

        if name in self._lazy_dataset_types:
            module_path, class_name = self._lazy_dataset_types[name]
            try:
                module = __import__(module_path, fromlist=[class_name])
                cls = getattr(module, class_name)
            except Exception as e:
                raise KeyError(
                    f"Failed to import dataset type '{name}' from {module_path}.{class_name}: {e}"
                ) from e
            # Guard against concurrent registration (e.g. warm-up task)
            if name not in self._dataset_types:
                self.register_dataset_type(cls)
            return self._dataset_types[name]

        raise KeyError(f"No dataset type for name '{name}'")

    def get_provisioner(self, name: str) -> type[BaseDatasetTypeProvisioner] | None:
        """Get dataset type provisioner class by name.

        Args:
            name: Name of the provisioner

        Returns:
            Provisioner class

        Raises:
            KeyError: If no provisioner found for name
        """
        if name in self._provisioners:
            return self._provisioners.get(name)

        if name in self._lazy_provisioners:
            module_path, class_name = self._lazy_provisioners[name]
            try:
                module = __import__(module_path, fromlist=[class_name])
                cls = getattr(module, class_name)
            except Exception as e:
                raise KeyError(
                    f"Failed to import provisioner '{name}' from {module_path}.{class_name}: {e}"
                ) from e
            # Guard against concurrent registration (e.g. warm-up task)
            if name not in self._provisioners:
                self.register_provisioner(cls)
            return self._provisioners[name]

        return None

    def list_dataset_types(self) -> list[str]:
        """List all registered dataset type names.

        Returns:
            Sorted list of dataset type names
        """
        return sorted({*self._dataset_types.keys(), *self._lazy_dataset_types.keys()})

    def list_provisioners(self) -> list[str]:
        """List all registered dataset type provisioner names.

        Returns:
            Sorted list of provisioner names
        """
        return sorted({*self._provisioners.keys(), *self._lazy_provisioners.keys()})

    def is_dataset_type_registered(self, name: str) -> bool:
        """Check if a dataset type is registered.

        Args:
            name: Name of the dataset type

        Returns:
            True if registered, False otherwise
        """
        return name in self._dataset_types or name in self._lazy_dataset_types

    def is_provisioner_registered(self, name: str) -> bool:
        """Check if a provisioner is registered.

        Args:
            name: Name of the provisioner

        Returns:
            True if registered, False otherwise
        """
        return name in self._provisioners or name in self._lazy_provisioners

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
        self._lazy_dataset_types.pop(key, None)

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
        self._lazy_provisioners.pop(key, None)

    def register_lazy_dataset_type(
        self, name: str, module_path: str, class_name: str
    ) -> None:
        """Register a dataset type by import path for lazy loading."""
        if name in self._dataset_types or name in self._lazy_dataset_types:
            raise ValueError(f"Dataset type already registered for name '{name}'")
        self._lazy_dataset_types[name] = (module_path, class_name)

    def register_lazy_provisioner(
        self, name: str, module_path: str, class_name: str
    ) -> None:
        """Register a provisioner by import path for lazy loading."""
        if name in self._provisioners or name in self._lazy_provisioners:
            raise ValueError(
                f"Dataset type provisioner already registered for name '{name}'"
            )
        self._lazy_provisioners[name] = (module_path, class_name)


# Global singleton registry instance
DATASET_TYPE_REGISTRY = DatasetTypeRegistry()
