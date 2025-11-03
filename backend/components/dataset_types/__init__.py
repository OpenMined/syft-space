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
    from .weaviate.weaviate_type import WeaviateDatasetType

    registry.register_dataset_type(WeaviateDatasetType)


__all__ = ["register_builtin_types"]
