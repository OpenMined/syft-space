"""Registry for data sources."""

from __future__ import annotations

from syft_space.components.sources.interfaces import BaseSource


class SourceRegistry:
    """Registry class for data sources.

    Sources are registered lazily by module path; classes are imported on
    first use to keep startup fast and avoid pulling optional dependencies
    until actually needed. Raises ``ValueError`` on duplicate registration
    and ``KeyError`` on unknown lookup.
    """

    _sources: dict[str, type[BaseSource]] = {}
    _lazy_sources: dict[str, tuple[str, str]] = {}

    def get(self, name: str) -> type[BaseSource]:
        """Get source class by name.

        Resolves a lazy entry by importing the target module on first call;
        the imported class is cached for subsequent lookups.

        Args:
            name: Name of the source.

        Returns:
            Source class.

        Raises:
            KeyError: If no source found for name, or if lazy import fails.
        """
        if name in self._sources:
            return self._sources[name]

        if name in self._lazy_sources:
            module_path, class_name = self._lazy_sources[name]
            try:
                module = __import__(module_path, fromlist=[class_name])
                cls = getattr(module, class_name)
            except Exception as e:
                raise KeyError(
                    f"Failed to import source '{name}' from "
                    f"{module_path}.{class_name}: {e}"
                ) from e
            # Cache resolved class; guard against concurrent resolution.
            self._sources.setdefault(name, cls)
            return self._sources[name]

        raise KeyError(f"No source for name '{name}'")

    def list_sources(self) -> list[str]:
        """List all registered source names.

        Returns:
            Sorted list of source names.
        """
        return sorted({*self._sources.keys(), *self._lazy_sources.keys()})

    def is_registered(self, name: str) -> bool:
        """Check if a source is registered.

        Args:
            name: Name of the source.

        Returns:
            True if registered, False otherwise.
        """
        return name in self._sources or name in self._lazy_sources

    def register(self, name: str, module_path: str, class_name: str) -> None:
        """Register a source by import path.

        The target class is imported on first ``get()`` call, not at
        registration time.

        Args:
            name: Name of the source (matches ``BaseSource.NAME`` of the
                target class).
            module_path: Dotted module path containing the source class.
            class_name: Name of the source class within the module.

        Raises:
            ValueError: If a source with this name is already registered.
        """
        if name in self._sources or name in self._lazy_sources:
            raise ValueError(f"Source already registered for name '{name}'")
        self._lazy_sources[name] = (module_path, class_name)


SOURCE_REGISTRY = SourceRegistry()


def register_builtin_sources() -> None:
    """Register all built-in sources.

    Called explicitly from ``main.py`` — no import side effects.
    """
    SOURCE_REGISTRY.register(
        "local_file",
        "syft_space.components.sources.local_file.local_file_source",
        "LocalFileSource",
    )
    SOURCE_REGISTRY.register(
        "noop",
        "syft_space.components.sources.noop_source",
        "NoOpSource",
    )
