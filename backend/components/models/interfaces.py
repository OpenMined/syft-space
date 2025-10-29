from typing import Any, Dict, List, Optional, Protocol

from components.integrations.schemas import HealthcheckResponse, SearchParameters
from pydantic import BaseModel, EmailStr, Field


class Context(BaseModel):
    """Context for the data source search."""

    sender: EmailStr = Field(..., description="Email of the sender")


class ModelSource(Protocol):
    """Model source interface."""

    SOURCE_NAME: str

    @staticmethod
    def setup() -> Dict[str, Any]:
        """Return a dictionary of config values required by this model source provider.
        This will be displayed in the frontend/sdk as configurable values
        when creating a service.
        """
        pass

    @staticmethod
    def chat(
        ctx: Context, prompt: str, params: Optional[ChatParameters] = None
    ) -> Dict[str, Any]:
        """Chat with the model source."""
        pass

    @staticmethod
    def healthcheck() -> HealthcheckResponse:
        """Healthcheck the model source.

        This will be called to check if the model source is healthy.
        """
        pass


class ModelSourceProvisioner(Protocol):
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
