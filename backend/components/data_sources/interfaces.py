from typing import Any, Dict, List, Optional, Protocol
from pydantic import BaseModel
from pydantic import EmailStr, Field
from components.data_sources.schemas import HealthcheckResponse, SearchParameters


class Context(BaseModel):
    """Context for the data source search."""

    sender: EmailStr = Field(..., description="Email of the sender")


class DataSource(Protocol):
    """Data source interface."""

    SOURCE_NAME: str

    def __init__(self, config: Dict[str, Any]):
        self.config = config

    @classmethod
    def name(cls):
        return cls.SOURCE_NAME

    @classmethod
    def type(cls):
        return cls.SOURCE_NAME.lower()

    @classmethod
    def configuration_schema() -> Dict[str, Any]:
        """Return a dictionary of config values required by this data source provider.
        This will be displayed in the frontend/sdk as configurable values
        when creating a service.
        """
        pass

    def search(
        self, ctx: Context, query: str, params: Optional[SearchParameters] = None
    ) -> List[Dict[str, Any]]:
        """Search the data source for the given query."""
        pass

    def ingest(self, ctx: Context, data: List[Dict[str, Any]]) -> None:
        """Ingest the data into the data source."""
        pass

    def healthcheck(self) -> HealthcheckResponse:
        """Healthcheck the data source.

        This will be called to check if the data source is healthy.
        """
        pass

    @classmethod
    def enabled(cls) -> bool:
        return True


class DataSourceProvisioner(Protocol):
    """Provisioner interface."""

    SOURCE_NAME: str

    def start(self, config: Dict[str, Any]) -> None:
        """Start the provisioner."""
        pass

    def stop(self) -> None:
        """Stop the provisioner."""
        pass

    def status(self) -> str:
        """Get the status of the provisioner."""
        pass
