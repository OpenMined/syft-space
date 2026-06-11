"""Dataset type interfaces.

A ``BaseDatasetType`` binds a source (data origin) to a vector store.
Concrete bindings declare a source provider and a vector store class,
plus a ``split_config`` classmethod that splits the flat user
configuration into the two per-axis configs. The default ``__init__``
builds the source via the provider's ``for_ingest`` factory and the
vector store via direct construction, exposing both as
``self.source`` and ``self.vector_store``.

The lifecycle methods (``search``, ``healthcheck``, ``ingest``,
``delete``) delegate to the collaborators by default. Bindings
override them only when cross-axis policy is needed — for example, to
apply a source-defined allow-list at ingest time.
"""

from typing import Any, ClassVar

from syft_space.components.shared.domain_types import HealthcheckResponse
from syft_space.components.shared.ingest_types import IngestContext, IngestRequest
from syft_space.components.shared.search_types import (
    SearchContext,
    SearchParameters,
    SearchResult,
)
from syft_space.components.sources.interfaces import BaseSource, BaseSourceProvider
from syft_space.components.vector_stores.interfaces import (
    BaseVectorStore,
    IngestableVectorStore,
)


class BaseDatasetType:
    """Binding of a source with a vector store.

    Subclasses set ``SOURCE_PROVIDER_CLS`` and ``VECTOR_STORE_CLS``
    class attributes and implement ``split_config`` to produce the
    per-axis configs. The default ``__init__`` builds each collaborator
    and the lifecycle methods delegate to them.
    """

    NAME: ClassVar[str]
    SOURCE_PROVIDER_CLS: ClassVar[type[BaseSourceProvider]]
    VECTOR_STORE_CLS: ClassVar[type[BaseVectorStore]]

    source: BaseSource
    vector_store: BaseVectorStore

    def __init__(self, configuration: dict[str, Any]) -> None:
        """Construct the source + vector store from the flat user config.

        Args:
            configuration: User-facing configuration dictionary.
        """
        cls = type(self)
        source_cfg, vector_store_cfg = cls.split_config(configuration)
        self.source = cls.SOURCE_PROVIDER_CLS.for_ingest(source_cfg)
        self.vector_store = cls.VECTOR_STORE_CLS(vector_store_cfg)

    # ── Required per-binding ─────────────────────────────────────────

    @classmethod
    def split_config(
        cls, configuration: dict[str, Any]
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Translate flat user configuration into per-axis configs.

        Returns:
            ``(source_config, vector_store_config)`` — each in the shape
            its constructor expects.
        """
        raise NotImplementedError

    @classmethod
    def description(cls) -> str:
        """Human-readable description of the binding."""
        raise NotImplementedError

    @classmethod
    def icon(cls) -> str:
        """Icon for the binding (display only)."""
        raise NotImplementedError

    @classmethod
    def configuration_schema(cls) -> dict[str, Any]:
        """Return the combined source + vector store configuration schema.

        Bindings own the user-facing schema because the public API is
        flat — the schema describes what the user types in, before
        ``split_config`` translates it.
        """
        raise NotImplementedError

    # ── Default classmethods (overridable) ───────────────────────────

    @classmethod
    def name(cls) -> str:
        """Get the name of the binding."""
        return cls.NAME

    @classmethod
    def type(cls) -> str:
        """Get the type identifier of the binding."""
        return cls.NAME.lower()

    @classmethod
    def enabled(cls) -> bool:
        """A binding is enabled only if both collaborators are enabled."""
        return cls.SOURCE_PROVIDER_CLS.enabled() and cls.VECTOR_STORE_CLS.enabled()

    @classmethod
    def connection_fields(cls) -> list[str]:
        """Connection fields are shared across datasets of this type.

        Owned by the vector store — the provisioner records connection
        values once and overlays them onto every dataset created under
        this binding.
        """
        return cls.VECTOR_STORE_CLS.connection_fields()

    @classmethod
    async def validate_configuration(cls, configuration: dict[str, Any]) -> None:
        """Validate by splitting and delegating to each collaborator.

        Bindings override when they need cross-axis or pre-split logic
        (e.g. defaulting a generated identifier before validation).

        Raises:
            ValueError: If configuration is invalid.
        """
        source_cfg, vector_store_cfg = cls.split_config(configuration)
        await cls.SOURCE_PROVIDER_CLS.validate_configuration(source_cfg)
        await cls.VECTOR_STORE_CLS.validate_configuration(vector_store_cfg)

    # ── Default lifecycle (overridable) ──────────────────────────────

    async def search(
        self, ctx: SearchContext, query: str, params: SearchParameters | None = None
    ) -> SearchResult:
        """Delegate search to the vector store."""
        return await self.vector_store.search(ctx, query, params)

    async def healthcheck(self) -> HealthcheckResponse:
        """Delegate healthcheck to the vector store."""
        return await self.vector_store.healthcheck()


class IngestableDatasetType(BaseDatasetType):
    """Binding whose vector store accepts ingest from this process.

    Read-only bindings (e.g. a Weaviate cluster fed externally) extend
    ``BaseDatasetType`` directly; bindings that ingest from this process
    extend ``IngestableDatasetType`` so the write-path defaults are
    available.
    """

    VECTOR_STORE_CLS: ClassVar[type[IngestableVectorStore]]
    vector_store: IngestableVectorStore

    async def ingest(self, ctx: IngestContext, request: IngestRequest) -> None:
        """Delegate ingest to the vector store."""
        await self.vector_store.ingest(ctx, request)

    async def delete(self, ctx: IngestContext) -> None:
        """Delegate delete to the vector store."""
        await self.vector_store.delete(ctx)
