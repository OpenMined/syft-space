"""Factory for building dataset_type instances from a dataset row.

Shared by the SourceScanner (which needs the ``source`` to watch) and the
JobProcessor (which needs the binding to ``ingest``). Extracted so the
construction rule lives in exactly one place.
"""

from loguru import logger

from syft_space.components.dataset_types.registry import DatasetTypeRegistry
from syft_space.components.datasets.entities import Dataset


class DatasetTypeFactory:
    """Builds dataset_type binding instances from persisted dataset rows."""

    def __init__(self, registry: DatasetTypeRegistry):
        self._registry = registry

    def build(self, dataset: Dataset):
        """Construct the dataset_type binding for a dataset row."""
        dataset_type_cls = self._registry.get_dataset_type(dataset.dtype)
        return dataset_type_cls(dataset.configuration)

    def provider_cls(self, dataset: Dataset):
        """The binding's source provider class — a class-level lookup.

        For provider classmethods (``selection_covers``, ...) that don't
        need a constructed source/vector-store pair.
        """
        return self._registry.get_dataset_type(dataset.dtype).SOURCE_PROVIDER_CLS

    def has_source(self, dataset: Dataset) -> bool:
        """Whether this dataset's binding exposes an active ``BaseSource``.

        ``NoOpSource`` instances (used by externally-fed bindings like
        remote Weaviate) are skipped — spawning a per-dataset task to
        iterate an empty change stream is wasted bookkeeping.
        """
        try:
            dataset_type = self.build(dataset)
        except Exception as e:
            logger.warning(f"Cannot build dataset_type for {dataset.id}: {e}")
            return False
        source = getattr(dataset_type, "source", None)
        if source is None:
            return False
        return not getattr(source, "IS_NOOP", False)
