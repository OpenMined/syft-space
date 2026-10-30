"""What the datasets component announces when a configuration changes.

``DatasetHandler.update_dataset`` publishes one ``DatasetConfigurationChanged``
per committed configuration edit to the listeners it was built with.
Listeners live in the components that own the reaction (ingestion restarts
the source's stream, the vector-store layer drops a cached client); this
module only defines the message, so datasets imports neither of them.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from syft_space.components.datasets.entities import Dataset
from syft_space.components.vector_stores.interfaces import BaseVectorStore

__all__ = ["AxisChange", "ConfigurationChangeListener", "DatasetConfigurationChanged"]


@dataclass(frozen=True)
class AxisChange:
    """One axis's configuration before and after the edit."""

    old: dict[str, Any]
    new: dict[str, Any]

    @property
    def changed(self) -> bool:
        return self.old != self.new


@dataclass(frozen=True)
class DatasetConfigurationChanged:
    """A dataset's stored configuration was replaced.

    Published after the row is committed, so a listener that re-reads the
    dataset sees the new configuration. ``vector_store_cls`` lets a listener
    rebuild the old store's connection without reaching for the registry.
    """

    dataset: Dataset
    source: AxisChange
    vector_store: AxisChange
    vector_store_cls: type[BaseVectorStore]


class ConfigurationChangeListener(Protocol):
    async def on_configuration_changed(
        self, event: DatasetConfigurationChanged
    ) -> None: ...
