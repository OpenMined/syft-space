"""Dataset types package with type system for datasets."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .registry import DatasetTypeRegistry


def register_builtin_types(registry: "DatasetTypeRegistry") -> None:
    """Register all built-in dataset types.

    This is called explicitly from main.py - no import side effects.

    Args:
        registry: The dataset type registry to register types with
    """
    from .weaviate_local.weaviate_provisioner import LocalFileBasedProvisioner
    from .weaviate_local.weaviate_type import LocalFileDatasetType

    registry.register_dataset_type(LocalFileDatasetType)
    registry.register_provisioner(LocalFileBasedProvisioner)


__all__ = ["register_builtin_types"]
