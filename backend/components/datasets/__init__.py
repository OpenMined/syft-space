# Import all dataset type modules to ensure they register themselves
# Import the registry so it's available at package level
from .registry import DATASET_TYPE_REGISTRY
from .weaviate import weaviate  # noqa: F401

__all__ = ["DATASET_TYPE_REGISTRY"]
