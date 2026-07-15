"""WordPress + ChromaDB dataset type binding.

Pairs the WordPress REST API source with an embedded ChromaDB vector
store. The user-facing configuration is flat; ``split_config`` peels
off the source-axis fields from the vector-store-axis fields at
construction time.
"""

from __future__ import annotations

import re
import uuid
from typing import Any, ClassVar

from pydantic import BaseModel, Field, ValidationError, field_validator

from syft_space.components.dataset_types.interfaces import IngestableDatasetType
from syft_space.components.shared.utils import ConfigSchemaGenerator
from syft_space.components.sources.wordpress.wordpress_source import (
    DEFAULT_POLL_INTERVAL_SECONDS,
    DEFAULT_USER_AGENT,
    WordPressProvider,
)
from syft_space.components.vector_stores.chromadb_local.chromadb_vector_store import (
    ChromaDBLocalVectorStore,
)
from syft_space.components.vector_stores.chromadb_local.schemas import (
    default_http_port,
)


class WordPressChromaDBConfiguration(BaseModel):
    """Flat user-facing configuration for the WordPress binding.

    ``split_config`` translates this into per-axis configs at
    construction time.
    """

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
    site_url: str = Field(
        ...,
        alias="siteUrl",
        description="Base URL of the WordPress site (e.g. https://example.com)",
    )
    username: str = Field(
        ...,
        description="WordPress user_login or display name (used for Basic Auth)",
    )
    application_password: str = Field(
        ...,
        alias="applicationPassword",
        description=(
            "WordPress Application Password (generate under "
            "Users → Profile → Application Passwords in wp-admin)"
        ),
        json_schema_extra={"format": "password"},
    )
    poll_interval_seconds: int = Field(
        default=DEFAULT_POLL_INTERVAL_SECONDS,
        alias="pollIntervalSeconds",
        description="Seconds between change-stream polls",
        gt=0,
    )
    user_agent: str = Field(
        default=DEFAULT_USER_AGENT,
        alias="userAgent",
        description=(
            "HTTP User-Agent header — override when the site WAF expects "
            "an allowlisted value"
        ),
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


class WordPressChromaDBDatasetType(IngestableDatasetType):
    """WordPress posts and pages indexed in an embedded ChromaDB instance."""

    NAME: ClassVar[str] = "wordpress"
    SOURCE_PROVIDER_CLS: ClassVar[type[WordPressProvider]] = WordPressProvider
    VECTOR_STORE_CLS: ClassVar[type[ChromaDBLocalVectorStore]] = (
        ChromaDBLocalVectorStore
    )

    @classmethod
    def split_config(
        cls, configuration: dict[str, Any]
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Translate flat config into (source_cfg, vector_store_cfg)."""
        cfg = WordPressChromaDBConfiguration.model_validate(configuration)
        source_cfg = {
            "site_url": cfg.site_url,
            "username": cfg.username,
            "application_password": cfg.application_password,
            "poll_interval_seconds": cfg.poll_interval_seconds,
            "user_agent": cfg.user_agent,
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
        return "📰"

    @classmethod
    def configuration_schema(cls) -> dict[str, Any]:
        return WordPressChromaDBConfiguration.model_json_schema(
            schema_generator=ConfigSchemaGenerator
        )

    @classmethod
    async def validate_configuration(cls, configuration: dict[str, Any]) -> None:
        """Validate flat config, then delegate to each collaborator.

        Generates a ``collectionName`` if missing (same UX as the
        local_file binding) before running the per-axis validators.
        """
        if not configuration.get("collectionName") and not configuration.get(
            "collection_name"
        ):
            configuration["collectionName"] = uuid.uuid4().hex

        try:
            WordPressChromaDBConfiguration.model_validate(configuration)
        except ValidationError as e:
            raise ValueError(f"Invalid configuration: {e}") from e

        await super().validate_configuration(configuration)

    @property
    def collection_name(self) -> str:
        """The (prefixed) collection name from the vector store."""
        return self.vector_store.collection_name

    @classmethod
    def redact_configuration(cls, configuration: dict[str, Any]) -> dict[str, Any]:
        """Drop the WordPress Application Password from the exposed config."""
        return {
            k: v
            for k, v in configuration.items()
            if k not in ("applicationPassword", "application_password")
        }


__all__ = [
    "WordPressChromaDBConfiguration",
    "WordPressChromaDBDatasetType",
]
