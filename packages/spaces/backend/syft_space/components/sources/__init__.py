"""Data source abstractions.

A source type contributes three classes: ``BaseBrowser`` for the
picker, ``BaseSource`` for ingestion, and ``BaseSourceProvider`` to
describe the source for the registry and build the other two. Sources
are orthogonal to the vector store used to index their content;
bindings between sources and vector stores live in ``dataset_types/``.
"""

from syft_space.components.sources.interfaces import (
    BaseBrowser,
    BaseSource,
    BaseSourceProvider,
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
    "BaseBrowser",
    "BaseSource",
    "BaseSourceProvider",
    "SourceChangeEvent",
    "SourceItem",
    "SourceRegistry",
    "register_builtin_sources",
]
