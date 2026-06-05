"""Data source abstractions.

A ``BaseSource`` represents a data origin (local files, WordPress, RSS, S3, ...)
and is orthogonal to the vector store used to index its content. Bindings
between sources and vector stores live in ``dataset_types/``.
"""

from syft_space.components.sources.interfaces import (
    BaseSource,
    SourceChangeEvent,
    SourceItem,
)
from syft_space.components.sources.registry import (
    SOURCE_REGISTRY,
    SourceRegistry,
    register_builtin_sources,
)

__all__ = [
    "SOURCE_REGISTRY",
    "BaseSource",
    "SourceChangeEvent",
    "SourceItem",
    "SourceRegistry",
    "register_builtin_sources",
]
