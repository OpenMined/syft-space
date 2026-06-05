"""Registry for vector stores."""

from __future__ import annotations

from syft_space.components.vector_stores.interfaces import BaseVectorStore


class VectorStoreRegistry:
    """Registry class for vector stores.

    Stores are registered lazily by module path; classes are imported on
    first use to keep startup fast and avoid pulling optional dependencies
    (chromadb, weaviate, ...) until actually needed. Raises ``ValueError``
    on duplicate registration and ``KeyError`` on unknown lookup.

    Mirrors ``SourceRegistry``: a single ``register(name, module_path,
    class_name)`` method, no eager ``register(cls)`` overload.
    """

    _stores: dict[str, type[BaseVectorStore]] = {}
    _lazy_stores: dict[str, tuple[str, str]] = {}

    def get(self, name: str) -> type[BaseVectorStore]:
        """Get vector store class by name.

        Resolves a lazy entry by importing the target module on first
        call; the imported class is cached for subsequent lookups.

        Raises:
            KeyError: If no vector store found for name, or if lazy import fails.
        """
        if name in self._stores:
            return self._stores[name]

        if name in self._lazy_stores:
            module_path, class_name = self._lazy_stores[name]
            try:
                module = __import__(module_path, fromlist=[class_name])
                cls = getattr(module, class_name)
            except Exception as e:
                raise KeyError(
                    f"Failed to import vector store '{name}' from "
                    f"{module_path}.{class_name}: {e}"
                ) from e
            self._stores.setdefault(name, cls)
            return self._stores[name]

        raise KeyError(f"No vector store for name '{name}'")

    def list_stores(self) -> list[str]:
        """Sorted list of registered vector store names."""
        return sorted({*self._stores.keys(), *self._lazy_stores.keys()})

    def is_registered(self, name: str) -> bool:
        """Whether a vector store is registered under ``name``."""
        return name in self._stores or name in self._lazy_stores

    def register(self, name: str, module_path: str, class_name: str) -> None:
        """Register a vector store by import path.

        The target class is imported on first ``get()`` call, not at
        registration time.

        Raises:
            ValueError: If a vector store with this name is already registered.
        """
        if name in self._stores or name in self._lazy_stores:
            raise ValueError(f"Vector store already registered for name '{name}'")
        self._lazy_stores[name] = (module_path, class_name)


VECTOR_STORE_REGISTRY = VectorStoreRegistry()


def register_builtin_vector_stores() -> None:
    """Register all built-in vector stores.

    Called explicitly from ``main.py`` — no import side effects.
    """
    VECTOR_STORE_REGISTRY.register(
        "chromadb_local",
        "syft_space.components.vector_stores.chromadb_local.chromadb_vector_store",
        "ChromaDBLocalVectorStore",
    )
    VECTOR_STORE_REGISTRY.register(
        "weaviate_remote",
        "syft_space.components.vector_stores.weaviate_remote.weaviate_vector_store",
        "WeaviateVectorStore",
    )
