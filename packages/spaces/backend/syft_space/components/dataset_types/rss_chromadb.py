"""RSS + ChromaDB dataset type binding.

Pairs the RSS/Atom source with an embedded ChromaDB vector store. The
user-facing configuration is flat; ``split_config`` peels off the
source-axis fields from the vector-store-axis fields at construction time.

Nothing is redacted: a feed URL is a public address, and private feeds carry
their token in the URL — which the source deliberately does not separate
into a credential field, so there is no secret here to hide.
"""

from __future__ import annotations

import re
import uuid
from typing import Any, ClassVar

from pydantic import BaseModel, Field, ValidationError, field_validator

from syft_space.components.dataset_types.interfaces import IngestableDatasetType
from syft_space.components.shared.utils import ConfigSchemaGenerator
from syft_space.components.sources.rss.rss_source import (
    DEFAULT_POLL_INTERVAL_SECONDS,
    POLL_INTERVAL_CHOICES,
    RssProvider,
)
from syft_space.components.vector_stores.chromadb_local.chromadb_vector_store import (
    ChromaDBLocalVectorStore,
)
from syft_space.components.vector_stores.chromadb_local.schemas import (
    default_http_port,
)


class RssChromaDBConfiguration(BaseModel):
    """Flat user-facing configuration for the RSS binding."""

    collection_name: str = Field(
        ...,
        alias="collectionName",
        description=(
            "Name of the ChromaDB collection (alphanumeric and underscores only)"
        ),
    )
    http_port: int = Field(
        default_factory=default_http_port,
        alias="httpPort",
        description="ChromaDB server HTTP port",
    )
    feed_urls: str = Field(
        ...,
        alias="feedUrls",
        description=(
            "Public RSS or Atom feed URLs, comma-separated "
            "(e.g. https://example.com/feed/). HTTPS only"
        ),
    )
    poll_interval_seconds: int = Field(
        default=DEFAULT_POLL_INTERVAL_SECONDS,
        alias="pollIntervalSeconds",
        description=(
            "How often to poll. Match the feed's publishing rate: a feed "
            "only shows its most recent items, so polling slower than it "
            "publishes loses the ones that fall off"
        ),
        json_schema_extra={"enum": POLL_INTERVAL_CHOICES},
    )
    model_config = {"populate_by_name": True}

    @field_validator("collection_name")
    @classmethod
    def validate_collection_name(cls, v: str) -> str:
        if not re.match(r"^[a-zA-Z0-9_]+$", v):
            raise ValueError(
                "collection_name can only contain letters, numbers, and underscores"
            )
        return v


class RssChromaDBDatasetType(IngestableDatasetType):
    """Items from public RSS or Atom feeds indexed in an embedded ChromaDB instance."""

    NAME: ClassVar[str] = "rss"
    SOURCE_PROVIDER_CLS: ClassVar[type[RssProvider]] = RssProvider
    VECTOR_STORE_CLS: ClassVar[type[ChromaDBLocalVectorStore]] = (
        ChromaDBLocalVectorStore
    )

    @classmethod
    def split_config(
        cls, configuration: dict[str, Any]
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Translate flat config into (source_cfg, vector_store_cfg)."""
        cfg = RssChromaDBConfiguration.model_validate(configuration)
        source_cfg = {
            "feed_urls": cfg.feed_urls,
            "poll_interval_seconds": cfg.poll_interval_seconds,
        }
        vector_store_cfg = {
            "collection_name": cfg.collection_name,
            "http_port": cfg.http_port,
        }
        return source_cfg, vector_store_cfg

    @classmethod
    def description(cls) -> str:
        return cls.__doc__ or ""

    @classmethod
    def icon(cls) -> str:
        return "📡"

    @classmethod
    def configuration_schema(cls) -> dict[str, Any]:
        return RssChromaDBConfiguration.model_json_schema(
            schema_generator=ConfigSchemaGenerator
        )

    @classmethod
    async def validate_configuration(cls, configuration: dict[str, Any]) -> None:
        """Validate flat config, then delegate to each collaborator.

        Generates a ``collectionName`` if missing (same UX as the other
        chromadb bindings) before running the per-axis validators.
        """
        if not configuration.get("collectionName") and not configuration.get(
            "collection_name"
        ):
            configuration["collectionName"] = uuid.uuid4().hex

        try:
            RssChromaDBConfiguration.model_validate(configuration)
        except ValidationError as e:
            raise ValueError(f"Invalid configuration: {e}") from e

        await super().validate_configuration(configuration)

    @property
    def collection_name(self) -> str:
        """The (prefixed) collection name from the vector store."""
        return self.vector_store.collection_name


__all__ = [
    "RssChromaDBConfiguration",
    "RssChromaDBDatasetType",
]
