from typing import Any, Dict, List

from components.datasets.interfaces import BaseDatasetType
from components.datasets.registry import DatasetTypeRegistry
from components.datasets.schemas import DatasetType


class DatasetHandler:
    """Handler for dataset operations."""

    def __init__(self, registry: DatasetTypeRegistry):
        """
        Initialize the DatasetHandler.

        Args:
            registry: DatasetTypeRegistry
        """
        self.registry = registry

    def list_dataset_types(self) -> List[str]:
        """
        List all available dataset type names.

        Returns:
            List of dataset type names
        """
        return self.registry.list_dataset_types()

    def get_dataset_type_schema(self, name: str) -> Dict[str, Any]:
        """
        Get configuration schema for a specific dataset type.

        Args:
            name: Name of the dataset type

        Returns:
            Configuration schema dictionary

        Raises:
            KeyError: If dataset type not found
            ValueError: If data source is not enabled
        """
        try:
            dataset_type_class = self.registry.get_dataset_type(name)
        except KeyError as e:
            raise KeyError(f"Dataset type '{name}' not found") from e

        if not dataset_type_class.enabled():
            raise ValueError(f"Dataset type '{name}' is not enabled")

        return dataset_type_class.configuration_schema()

    def is_dataset_type_available(self, name: str) -> bool:
        """
        Check if a dataset type is available and enabled.

        Args:
            name: Name of the dataset type

        Returns:
            True if available and enabled, False otherwise
        """
        try:
            dataset_type_class = self.registry.get_dataset_type(name)
            return dataset_type_class is not None and dataset_type_class.enabled()
        except KeyError:
            return False

    def get_dataset_type(self, name: str) -> DatasetType:
        """
        Get comprehensive information about a dataset type.

        Args:
            name: Name of the dataset type

        Returns:
            DatasetType containing dataset type information

        Raises:
            KeyError: If dataset type not found
        """
        try:
            dataset_type_class = self.registry.get_dataset_type(name)
        except KeyError as e:
            raise KeyError(f"Dataset type '{name}' not found") from e

        return DatasetType(
            name=dataset_type_class.name(),
            config_schema=dataset_type_class.configuration_schema(),
            description=dataset_type_class.description(),
            icon=dataset_type_class.icon(),
            enabled=dataset_type_class.enabled(),
        )

    def list_dataset_types(self) -> List[DatasetType]:
        """
        Get comprehensive information about all available dataset types.

        Returns:
            List of DatasetType containing dataset type information
        """
        return [
            self.get_dataset_type(name) for name in self.registry.list_dataset_types()
        ]
