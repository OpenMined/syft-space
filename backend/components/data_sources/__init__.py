# Import all data source modules to ensure they register themselves
from .weaviate import weaviate  # noqa: F401

# Import the registry so it's available at package level
from .registry import DATA_SOURCE_REGISTRY

__all__ = ["DATA_SOURCE_REGISTRY"]
