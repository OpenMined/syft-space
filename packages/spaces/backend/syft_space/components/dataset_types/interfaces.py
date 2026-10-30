"""Dataset type interfaces.

A ``BaseDatasetType`` binds a source (data origin) to a vector store.
Concrete bindings declare a source provider and a vector store class.
The user-facing configuration is flat: the binding composes it from the
two axis schemas, tagging each property with its ``axis``, and
``split_config`` partitions a flat config by key ownership. Each axis
declares its own editable / secret fields (``shared.config_flags``);
the binding only reads them back out of the composed schema. Flags:
``editable`` (may change after creation) and ``visibility`` (``public``,
``secret``: value never returned, ``internal``: never shown). The
default ``__init__`` builds the source via the provider's
``for_ingest`` factory and the vector store via direct construction,
exposing both as ``self.source`` and ``self.vector_store``.

The lifecycle methods (``search``, ``healthcheck``, ``ingest``,
``delete``) delegate to the collaborators by default. Bindings
override them only when cross-axis policy is needed — for example, to
apply a source-defined allow-list at ingest time.
"""

from typing import Any, ClassVar, NamedTuple

from syft_space.components.shared.config_flags import (
    Visibility,
    editable_fields,
    fields_with_visibility,
)
from syft_space.components.shared.domain_types import HealthcheckResponse
from syft_space.components.shared.ingest_types import IngestContext, IngestRequest
from syft_space.components.shared.metadata_types import DatasetMetadata
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
    class attributes. The default ``__init__`` builds each collaborator
    and the lifecycle methods delegate to them.
    """

    NAME: ClassVar[str]
    SOURCE_PROVIDER_CLS: ClassVar[type[BaseSourceProvider]]
    VECTOR_STORE_CLS: ClassVar[type[BaseVectorStore]]
    METADATA_CLS: ClassVar[type[DatasetMetadata]] = DatasetMetadata

    source: BaseSource
    vector_store: BaseVectorStore
    metadata: DatasetMetadata

    def __init__(self, configuration: dict[str, Any]) -> None:
        """Construct the source + vector store from the flat user config.

        Args:
            configuration: User-facing configuration dictionary.
        """
        cls = type(self)
        source_cfg, vector_store_cfg = cls.split_config(configuration)
        self.source = cls.SOURCE_PROVIDER_CLS.for_ingest(source_cfg)
        self.vector_store = cls.VECTOR_STORE_CLS(vector_store_cfg)
        self.metadata = cls.metadata_for(configuration)

    @classmethod
    def metadata_for(cls, configuration: dict[str, Any]) -> DatasetMetadata:
        """The binding's metadata contract from config alone, no collaborators built."""
        source_cfg, vector_store_cfg = cls.split_config(configuration)
        return cls.METADATA_CLS(
            cls.SOURCE_PROVIDER_CLS.METADATA_FIELDS(source_cfg),
            cls.VECTOR_STORE_CLS.METADATA_FIELDS(vector_store_cfg),
        )

    def public_metadata(self, metadata: dict[str, Any]) -> dict[str, Any]:
        """A document's metadata reduced to the keys that may leave the space."""
        return self.metadata.public(metadata)

    # ── Configuration shape ──────────────────────────────────────────

    @classmethod
    def configuration_schema(cls) -> dict[str, Any]:
        """The flat user-facing schema: source properties, then store properties.

        Every property is tagged ``axis`` (``source`` / ``vector_store``)
        and keeps the flags its axis declared. A key present on both axes
        is a programming error.
        """
        source = cls.SOURCE_PROVIDER_CLS.configuration_schema()
        store = cls.VECTOR_STORE_CLS.configuration_schema()
        return compose_schema(source, store)

    @classmethod
    def split_config(
        cls, configuration: dict[str, Any]
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Partition a flat config into ``(source_config, vector_store_config)``.

        Keys keep their spelling: a row may hold a key as the schema prints
        it (``collectionName``) or as its Python name (``collection_name``),
        and the axis models accept both. Keys no axis declares are dropped.
        """
        owner = _axes(cls).owner
        halves: dict[str, dict[str, Any]] = {"source": {}, "vector_store": {}}
        for key, value in configuration.items():
            axis = owner.get(key)
            if axis is not None:
                halves[axis][key] = value
        return halves["source"], halves["vector_store"]

    @classmethod
    def editable_fields(cls) -> list[str]:
        """Keys an owner may change after creation, as the schema prints them."""
        return editable_fields(cls.configuration_schema())

    @classmethod
    def secret_fields(cls) -> list[str]:
        """Keys holding credentials, as the schema prints them."""
        return fields_with_visibility(cls.configuration_schema(), Visibility.SECRET)

    # ── Required per-binding ─────────────────────────────────────────

    @classmethod
    def description(cls) -> str:
        """Human-readable description of the binding."""
        raise NotImplementedError

    @classmethod
    def icon(cls) -> str:
        """Icon for the binding (display only)."""
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
    def redact_configuration(cls, configuration: dict[str, Any]) -> dict[str, Any]:
        """Return a copy of the stored configuration safe to expose over the API.

        Secret scalars are dropped. A secret dict (``headers``) keeps its
        keys with ``None`` values, so a client can see which entries exist
        and edit them per key without learning the values.
        """
        spellings = _axes(cls).spellings
        secrets = {s for key in cls.secret_fields() for s in spellings[key]}
        redacted: dict[str, Any] = {}
        for key, value in configuration.items():
            if key not in secrets:
                redacted[key] = value
            elif isinstance(value, dict):
                redacted[key] = dict.fromkeys(value)
        return redacted

    @classmethod
    async def validate_configuration(cls, configuration: dict[str, Any]) -> None:
        """Validate by splitting and delegating to each collaborator.

        Bindings override when they need cross-axis or pre-split logic
        (e.g. defaulting a generated identifier before validation).

        Raises:
            ValueError: If configuration is invalid.
        """
        source_cfg, vector_store_cfg = cls.split_config(configuration)
        # Store first: its check is shape-only, a source's may reach the network.
        await cls.VECTOR_STORE_CLS.validate_configuration(vector_store_cfg)
        await cls.SOURCE_PROVIDER_CLS.validate_configuration(source_cfg)

    # ── Default lifecycle (overridable) ──────────────────────────────

    async def search(
        self, ctx: SearchContext, query: str, params: SearchParameters | None = None
    ) -> SearchResult:
        """Delegate search to the vector store."""
        return await self.vector_store.search(ctx, query, params)

    async def healthcheck(self) -> HealthcheckResponse:
        """Delegate healthcheck to the vector store."""
        return await self.vector_store.healthcheck()


def compose_schema(
    source: dict[str, Any], vector_store: dict[str, Any]
) -> dict[str, Any]:
    """Merge two axis schemas into one flat schema, tagging each property's axis."""
    properties: dict[str, Any] = {}
    required: list[str] = []
    defs: dict[str, Any] = {}
    for axis, schema in (("source", source), ("vector_store", vector_store)):
        for key, prop in (schema.get("properties") or {}).items():
            if key in properties:
                raise ValueError(f"configuration key {key!r} is declared by both axes")
            properties[key] = {**prop, "axis": axis}
        required.extend(schema.get("required") or [])
        defs.update(schema.get("$defs") or {})
    composed: dict[str, Any] = {"properties": properties, "required": required}
    if defs:
        composed["$defs"] = defs
    return composed


class _Axes(NamedTuple):
    """Key ownership of one binding, read from the two ``CONFIG_MODEL``s."""

    # Every accepted spelling of a key -> the axis that owns it.
    owner: dict[str, str]
    # Printed key -> all spellings the axis model accepts for it.
    spellings: dict[str, frozenset[str]]


_AXES_BY_CLASS: dict[type[BaseDatasetType], _Axes] = {}


def _axes(dataset_type_cls: type[BaseDatasetType]) -> _Axes:
    """Ownership of one binding class, computed once; a duplicate spelling raises."""
    if dataset_type_cls in _AXES_BY_CLASS:
        return _AXES_BY_CLASS[dataset_type_cls]
    owner: dict[str, str] = {}
    spellings: dict[str, frozenset[str]] = {}
    models = (
        ("source", dataset_type_cls.SOURCE_PROVIDER_CLS.CONFIG_MODEL),
        ("vector_store", dataset_type_cls.VECTOR_STORE_CLS.CONFIG_MODEL),
    )
    for axis, model in models:
        for name, field in model.model_fields.items():
            printed = field.alias or name
            for spelling in {printed, name}:
                if owner.get(spelling, axis) != axis:
                    raise ValueError(
                        f"configuration key {spelling!r} is declared by both axes"
                    )
                owner[spelling] = axis
            spellings[printed] = frozenset({printed, name})
    _AXES_BY_CLASS[dataset_type_cls] = _Axes(owner, spellings)
    return _AXES_BY_CLASS[dataset_type_cls]


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
