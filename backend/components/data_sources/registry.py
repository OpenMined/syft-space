from __future__ import annotations
from typing import Type, Dict, List
from .interfaces import DataSource, DataSourceProvisioner


class DataSourceRegistry:
    """Registry class for data sources and provisioners."""

    _data_sources: Dict[str, Type[DataSource]] = {}
    _provisioners: Dict[str, Type[DataSourceProvisioner]] = {}

    def get_source(self, source_name: str) -> Type[DataSource]:
        """Get data source class by name."""
        try:
            return self._data_sources[source_name]
        except KeyError:
            raise KeyError(f"No data source for source '{source_name}'")

    def get_provisioner(self, source_name: str) -> Type[DataSourceProvisioner]:
        """Get data source provisioner class by name."""
        try:
            return self._provisioners[source_name]
        except KeyError:
            raise KeyError(f"No data source provisioner for source '{source_name}'")

    def list_sources(self) -> List[str]:
        """List all registered data source names."""
        return sorted(self._data_sources.keys())

    def list_provisioners(self) -> List[str]:
        """List all registered data source provisioner names."""
        return sorted(self._provisioners.keys())

    def is_source_registered(self, source_name: str) -> bool:
        """Check if a data source is registered."""
        return source_name in self._data_sources

    def is_provisioner_registered(self, source_name: str) -> bool:
        """Check if a provisioner is registered."""
        return source_name in self._provisioners

    def register_source(self, cls: Type[DataSource]) -> None:
        key = getattr(cls, "SOURCE_NAME", None)
        if not key:
            raise ValueError(f"{cls.__name__} missing SOURCE_NAME")
        if key in self._data_sources:
            raise ValueError(f"Data source already registered for source '{key}'")
        self._data_sources[key] = cls

    def register_provisioner(self, cls: Type[DataSourceProvisioner]) -> None:
        key = getattr(cls, "SOURCE_NAME", None)
        if not key:
            raise ValueError(f"{cls.__name__} missing SOURCE_NAME")
        if key in self._provisioners:
            raise ValueError(
                f"Data source provisioner already registered for source '{key}'"
            )
        self._provisioners[key] = cls


DATA_SOURCE_REGISTRY = DataSourceRegistry()
