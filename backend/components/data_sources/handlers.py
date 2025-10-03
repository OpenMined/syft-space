from typing import Dict, Any, List

from components.data_sources.schemas import DataSourceInfo

from components.data_sources.interfaces import DataSourceProvisioner
from components.data_sources.registry import DataSourceRegistry


class DataSourceHandler:
    """Handler for data source operations with dependency injection support."""

    def __init__(self, registry: DataSourceRegistry):
        """
        Initialize the DataSourceHandler.

        Args:
            registry: DataSourceRegistry
        """
        self.registry = registry

    def list_data_sources(self) -> List[str]:
        """
        List all available data source names.

        Returns:
            List of data source names
        """
        return self.registry.list_sources()

    def get_configuration_schema(self, source_name: str) -> Dict[str, Any]:
        """
        Get configuration schema for a specific data source.

        Args:
            source_name: Name of the data source

        Returns:
            Configuration schema dictionary

        Raises:
            KeyError: If data source not found
            ValueError: If data source is not enabled
        """
        try:
            data_source_class = self.registry.get_source(source_name)
        except KeyError as e:
            raise KeyError(f"Data source '{source_name}' not found") from e

        if not data_source_class.enabled():
            raise ValueError(f"Data source '{source_name}' is not enabled")

        return data_source_class.configuration_schema()

    def is_source_available(self, source_name: str) -> bool:
        """
        Check if a data source is available and enabled.

        Args:
            source_name: Name of the data source

        Returns:
            True if available and enabled, False otherwise
        """
        try:
            data_source_class = self.registry.get_source(source_name)
            return data_source_class is not None and data_source_class.enabled()
        except KeyError:
            return False

    def get_data_source_info(self, source_name: str) -> DataSourceInfo:
        """
        Get comprehensive information about a data source.

        Args:
            source_name: Name of the data source

        Returns:
            DataSourceInfo containing data source information

        Raises:
            KeyError: If data source not found
        """
        try:
            data_source_class = self.registry.get_source(source_name)
        except KeyError as e:
            raise KeyError(f"Data source '{source_name}' not found") from e

        return DataSourceInfo(
            name=data_source_class.name(),
            config_schema=data_source_class.configuration_schema(),
            description=data_source_class.description(),
            icon=data_source_class.icon(),
            enabled=data_source_class.enabled(),
        )

    def list_data_source_info(self) -> List[DataSourceInfo]:
        """
        Get comprehensive information about all available data sources.

        Returns:
            List of DataSourceInfo containing data source information
        """
        return [
            self.get_data_source_info(source_name)
            for source_name in self.registry.list_sources()
        ]
