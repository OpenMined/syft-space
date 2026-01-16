"""Dataset type interfaces and domain models."""

from io import BytesIO
from tempfile import SpooledTemporaryFile
from typing import Any, BinaryIO, Protocol

from pydantic import BaseModel, Field

from syft_space.components.shared.domain_types import Context, HealthcheckResponse


class SearchParameters(BaseModel):
    """Domain contract for search parameters."""

    similarity_threshold: float = Field(
        default=0.8, ge=0.0, le=1.0, description="Similarity threshold for matching"
    )
    limit: int = Field(
        default=5, ge=1, description="Maximum number of results to return"
    )
    include_metadata: bool = Field(
        default=True, description="Whether to include metadata in response"
    )
    extra_options: dict[str, Any] = Field(
        default_factory=dict, description="Extra options for the search"
    )


class SearchedDocument(BaseModel):
    """A single document from search results."""

    document_id: str = Field(..., description="Unique identifier for the document")
    content: str = Field(..., description="Content of the document")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Document metadata"
    )
    similarity_score: float = Field(
        ..., ge=0.0, le=1.0, description="Similarity score for the document"
    )


class SearchResult(BaseModel):
    """Domain contract for search results."""

    documents: list[SearchedDocument] = Field(
        default_factory=list, description="List of searched documents"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional search metadata"
    )


class IngestFile(BaseModel):
    """Framework-agnostic file wrapper for ingestion."""

    file_handle: BinaryIO | SpooledTemporaryFile | BytesIO = Field(
        ..., description="File-like object (SpooledTemporaryFile, BytesIO, etc.)"
    )
    filename: str = Field(..., description="Original filename")
    content_type: str | None = Field(default=None, description="MIME type")
    file_size: int | None = Field(default=None, description="Size in bytes")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Custom metadata"
    )

    class Config:
        """Pydantic config."""

        arbitrary_types_allowed = True


class IngestRequest(BaseModel):
    """Domain contract for data ingestion."""

    files: list[IngestFile] = Field(
        default_factory=list, description="List of files to ingest"
    )


class BaseDatasetType(Protocol):
    """Base dataset type interface.

    All concrete dataset types must implement this protocol.
    """

    NAME: str

    def __init__(self, config: dict[str, Any]) -> None:
        """Initialize the dataset type with configuration.

        Args:
            config: Configuration dictionary for this dataset type
        """
        ...

    @classmethod
    def name(cls) -> str:
        """Get the name of the dataset type."""
        ...

    @classmethod
    def type(cls) -> str:
        """Get the type identifier of the dataset type."""
        ...

    @classmethod
    def description(cls) -> str:
        """Get the description of the dataset type."""
        ...

    @classmethod
    def icon(cls) -> str:
        """Get the icon for the dataset type."""
        ...

    @classmethod
    def configuration_schema(cls) -> dict[str, Any]:
        """Return configuration schema required by this dataset type.

        This will be displayed in the frontend/SDK as configurable values
        when creating a dataset.

        Returns:
            Dictionary describing the configuration schema
        """
        ...

    @classmethod
    def validate_configuration(cls, configuration: dict[str, Any]) -> None:
        """Validate the configuration for the dataset type.

        Args:
            configuration: Configuration dictionary to validate

        Raises:
            ValidationError: If configuration is invalid
        """
        ...

    def search(
        self, ctx: Context, query: str, params: SearchParameters | None = None
    ) -> SearchResult:
        """Search the dataset for the given query.

        Args:
            ctx: Request context with sender information
            query: Search query string
            params: Optional search parameters

        Returns:
            SearchResult with matching documents
        """
        ...

    def healthcheck(self) -> HealthcheckResponse:
        """Check if the dataset type is healthy.

        Returns:
            HealthcheckResponse indicating health status
        """
        ...

    @classmethod
    def enabled(cls) -> bool:
        """Check if this dataset type is enabled.

        Returns:
            True if enabled, False otherwise
        """
        ...

    @classmethod
    def connection_fields(cls) -> list[str]:
        """Return list of configuration field names that are connection-related.

        Connection fields are shared across all datasets of this type when using
        a shared provisioner. When a new dataset is created and a provisioner
        is already running, these fields are overridden from the ProvisionerState.

        Non-connection fields (dataset-specific) remain unique per dataset.

        Returns:
            List of field names from configuration_schema() that are connection-related.

        Example for Weaviate:
            ["httpPort", "grpcPort"]
        """
        ...


class IngestableDatasetType(BaseDatasetType):
    """Dataset type interface with ingestion capabilities.

    Extends BaseDatasetType to add generic ingestion functionality.
    Dataset types that support any form of ingestion should implement this protocol.

    For file-based ingestion with watching, see FileIngestableDatasetType.
    """

    def ingest(self, ctx: Context, request: IngestRequest) -> None:
        """Ingest data into the dataset.

        Args:
            ctx: Request context with sender information
            request: Ingest request with files to add
        """
        ...


class FileIngestableDatasetType(IngestableDatasetType):
    """Dataset type interface for file-based ingestion with watching.

    Extends IngestableDatasetType with file-specific methods for:
    - Discovering paths to watch for new files
    - Filtering files by allowed extensions

    Use this interface for dataset types that:
    - Monitor local directories for new files
    - Need file extension filtering
    - Support the watch-based ingestion system
    """

    def watched_paths(self) -> list[str]:
        """Get the paths to watch for new files.

        Returns:
            List of absolute directory/file paths to monitor.
            Directories will be watched recursively.
        """
        ...

    def allowed_extensions(self) -> set[str]:
        """Get the allowed file extensions for ingestion.

        Returns:
            Set of extensions including the dot (e.g., {".pdf", ".txt", ".md"}).
            Only files with these extensions will be ingested.
        """
        ...


class BaseDatasetTypeProvisioner(Protocol):
    """Base dataset type provisioner interface.

    Provisioners handle lifecycle management of dataset infrastructure.
    All methods are classmethods - provisioners are stateless.
    State is passed as parameters and stored in Dataset entity.
    """

    NAME: str

    @classmethod
    def name(cls) -> str:
        """Get the name of the provisioner."""
        ...

    @classmethod
    def start(cls, config: dict[str, Any]) -> dict[str, Any]:
        """Start/provision the resource.

        Args:
            config: Configuration for the resource

        Returns:
            State dictionary with persistent identifiers needed to
            re-discover and manage the resource after restart.

            Examples:
            - Docker: {"container_name": "...", "container_id": "...", "port": 8080}
            - Subprocess: {"port": 8080, "pid_file": "/path/to.pid"}
            - Systemd: {"unit_name": "service-name.service"}
        """
        ...

    @classmethod
    def stop(cls, state: dict[str, Any]) -> None:
        """Stop the provisioned resource.

        Args:
            state: State dictionary returned from start()
        """
        ...

    @classmethod
    def is_running(cls, state: dict[str, Any]) -> bool:
        """Check if resource is currently running.

        Uses state to re-discover the resource (important after restart).

        Args:
            state: State dictionary returned from start()

        Returns:
            True if resource is running, False otherwise
        """
        ...

    @classmethod
    def status(cls, state: dict[str, Any]) -> str:
        """Get detailed status of the resource.

        Args:
            state: State dictionary returned from start()

        Returns:
            Status string: "running", "stopped", "starting", "error", etc.
        """
        ...
