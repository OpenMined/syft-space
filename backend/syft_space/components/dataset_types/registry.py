"""Registry for dataset type bindings."""

from __future__ import annotations

from syft_space.components.dataset_types.interfaces import BaseDatasetType


class DatasetTypeRegistry:
    """Registry of dataset-type bindings keyed by their ``NAME`` (``dtype``).

    A binding is the pairing of a ``BaseSource`` with a ``BaseVectorStore``;
    the registry only tracks the bindings themselves. Provisioner classes
    are owned by their vector store via ``BaseVectorStore.PROVISIONER_CLS``
    and are reachable through ``cls.VECTOR_STORE_CLS.PROVISIONER_CLS``.
    """

    _dataset_types: dict[str, type[BaseDatasetType]] = {}
    _lazy_dataset_types: dict[str, tuple[str, str]] = {}

    def get_dataset_type(self, name: str) -> type[BaseDatasetType]:
        """Get dataset type class by name.

        Args:
            name: Name of the dataset type.

        Returns:
            Dataset type class.

        Raises:
            KeyError: If no dataset type is registered under ``name``.
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
                    f"Failed to import dataset type '{name}' from "
                    f"{module_path}.{class_name}: {e}"
                ) from e
            # Guard against concurrent registration (e.g. warm-up task)
            if name not in self._dataset_types:
                self.register_dataset_type(cls)
            return self._dataset_types[name]

        raise KeyError(f"No dataset type for name '{name}'")

    def list_dataset_types(self) -> list[str]:
        """List all registered dataset type names."""
        return sorted({*self._dataset_types.keys(), *self._lazy_dataset_types.keys()})

    def is_dataset_type_registered(self, name: str) -> bool:
        """Check if a dataset type is registered."""
        return name in self._dataset_types or name in self._lazy_dataset_types

    def register_dataset_type(self, cls: type[BaseDatasetType]) -> None:
        """Register a dataset type.

        Args:
            cls: Dataset type class to register.

        Raises:
            ValueError: If class missing NAME or already registered.
        """
        key = getattr(cls, "NAME", None)
        if not key:
            raise ValueError(f"{cls.__name__} missing NAME")
        if key in self._dataset_types:
            raise ValueError(f"Dataset type already registered for name '{key}'")
        self._dataset_types[key] = cls
        self._lazy_dataset_types.pop(key, None)

    def register_lazy_dataset_type(
        self, name: str, module_path: str, class_name: str
    ) -> None:
        """Register a dataset type by import path for lazy loading."""
        if name in self._dataset_types or name in self._lazy_dataset_types:
            raise ValueError(f"Dataset type already registered for name '{name}'")
        self._lazy_dataset_types[name] = (module_path, class_name)


# Global singleton registry instance
DATASET_TYPE_REGISTRY = DatasetTypeRegistry()
