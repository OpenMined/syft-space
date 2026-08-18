"""Registry for data source providers."""

from __future__ import annotations

from syft_space.components.sources.interfaces import BaseSourceProvider


class SourceRegistry:
    """Lookup table mapping ``dtype`` names to source providers.

    Providers are registered lazily by module path and imported on
    first use, so optional dependencies aren't pulled in at startup.
    Raises ``ValueError`` on duplicate registration and ``KeyError``
    on unknown lookup.
    """

    _sources: dict[str, type[BaseSourceProvider]] = {}
    _lazy_sources: dict[str, tuple[str, str]] = {}

    def get(self, name: str) -> type[BaseSourceProvider]:
        """Return the provider class for ``name``, importing it on first use.

        The resolved class is cached, so subsequent lookups are direct.

        Raises:
            KeyError: If no source is registered under ``name`` or the
                lazy import fails.
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
        """Register a provider by import path; imported on first ``get()``.

        Args:
            name: Source name, matching the provider's ``NAME`` attribute.
            module_path: Dotted module path containing the provider class.
            class_name: Provider class name within the module.

        Raises:
            ValueError: If a source is already registered under ``name``.
        """
        if name in self._sources or name in self._lazy_sources:
            raise ValueError(f"Source already registered for name '{name}'")
        self._lazy_sources[name] = (module_path, class_name)


SOURCE_REGISTRY = SourceRegistry()


def register_builtin_sources() -> None:
    """Register the source providers shipped with the application.

    Called explicitly from ``main.py``; importing this module does not
    register anything by itself.
    """
    SOURCE_REGISTRY.register(
        "local_file",
        "syft_space.components.sources.local_file.local_file_source",
        "LocalFileProvider",
    )
    SOURCE_REGISTRY.register(
        "wordpress",
        "syft_space.components.sources.wordpress.wordpress_source",
        "WordPressProvider",
    )
    SOURCE_REGISTRY.register(
        "noop",
        "syft_space.components.sources.noop_source",
        "NoOpProvider",
    )
