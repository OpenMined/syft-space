from typing import Any, Dict, List, Optional, Protocol

from pydantic import BaseModel, EmailStr, Field

from components.datasets.schemas import HealthcheckResponse, SearchParameters


class Context(BaseModel):
    """Context for the dataset search."""

    sender: EmailStr = Field(..., description="Email of the sender")


class BaseDatasetType(Protocol):
    """Base dataset type interface."""

    NAME: str

    def __init__(self, config: Dict[str, Any]):
        self.config = config

    @classmethod
    def name(cls):
        """Get the name of the dataset type."""
        return cls.NAME

    @classmethod
    def type(cls):
        """Get the type of the dataset type."""
        return cls.NAME.lower()

    @classmethod
    def description(cls):
        return cls.__doc__

    @classmethod
    def icon(cls) -> str:
        return "🕸️"

    @classmethod
    def configuration_schema() -> Dict[str, Any]:
        """Return a dictionary of config values required by this dataset type.
        This will be displayed in the frontend/sdk as configurable values
        when creating a service.
        """
        pass

    def search(
        self, ctx: Context, query: str, params: Optional[SearchParameters] = None
    ) -> List[Dict[str, Any]]:
        """Search the dataset for the given query."""
        pass

    def ingest(self, ctx: Context, data: List[Dict[str, Any]]) -> None:
        """Ingest the data into the dataset."""
        pass

    def healthcheck(self) -> HealthcheckResponse:
        """Healthcheck the dataset.

        This will be called to check if the dataset is healthy.
        """
        pass

    @classmethod
    def enabled(cls) -> bool:
        return True


class BaseDatasetTypeProvisioner(Protocol):
    """Base dataset type provisioner interface."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config

    NAME: str

    @classmethod
    def name(cls):
        return cls.NAME

    def start(self, config: Dict[str, Any]) -> None:
        """Start the dataset type provisioner."""
        pass

    def stop(self) -> None:
        """Stop the dataset type provisioner."""
        pass

    def status(self) -> str:
        """Get the status of the provisioner."""
        pass
