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
    # Register dataset types lazily to keep startup fast.
    # Classes are imported on first use.
    registry.register_lazy_dataset_type(
        "remote_weaviate",
        "syft_space.components.dataset_types.remote_weaviate",
        "RemoteWeaviateDatasetType",
    )

    registry.register_lazy_dataset_type(
        "local_file",
        "syft_space.components.dataset_types.local_file_chromadb",
        "LocalFileChromaDBDatasetType",
    )

    registry.register_lazy_dataset_type(
        "wordpress",
        "syft_space.components.dataset_types.wordpress_chromadb",
        "WordPressChromaDBDatasetType",
    )


__all__ = ["register_builtin_types"]
