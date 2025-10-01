from ast import Dict
from ast import List
from enum import Enum
from pydantic import BaseModel
from pydantic import Field
from pydantic import Optional
from pydantic import Any


class HealthcheckStatus(str, Enum):
    """Status for the data source healthcheck."""

    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"


class HealthcheckResponse(BaseModel):
    """Response for the data source healthcheck."""

    status: HealthcheckStatus


class ChatParameters(BaseModel):
    """Parameters for the model source chat."""

    query: str = Field(..., description="Query to use")
    temperature: float = Field(..., description="Temperature to use")
    max_tokens: int = Field(..., description="Maximum number of tokens to generate")
    include_metadata: bool = Field(
        default=True, description="Whether to include metadata in response"
    )
    extra_options: Dict[str, Any] = Field(
        default_factory=dict, description="Extra options for the chat"
    )


class ChatMessage(BaseModel):
    """Message in the chat"""

    role: str = Field(..., description="Role of the message sender")
    content: str = Field(..., description="Content of the message")
    tokens: int = Field(..., description="Number of tokens in the message")


class ChatResult(BaseModel):
    id: str = Field(..., description="Unique identifier for the response")
    model: str = Field(..., description="Model used for generation")
    messages: List[ChatMessage] = Field(..., description="Generated messages")
    finish_reason: str = Field(..., description="Reason for completion")
    cost: float = Field(..., description="Cost of the generation")
    response_time_ms: int = Field(..., description="Response time in milliseconds")
    api_version: str = Field(..., description="API version used")
