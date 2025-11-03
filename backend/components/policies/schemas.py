"""Policy API schemas for request/response models."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class PolicyTypeInfoResponse(BaseModel):
    """Response model for policy type information."""

    name: str = Field(..., description="Name of the policy type")
    description: str = Field(..., description="Description of the policy type")
    config_schema: dict[str, Any] = Field(
        ..., description="Configuration schema for the policy type"
    )
    icon: str = Field(..., description="Icon for the policy type")
    enabled: bool = Field(..., description="Whether the policy type is enabled")


class CreatePolicyRequest(BaseModel):
    """Request model for creating a policy."""

    name: str = Field(..., description="Name for the policy")
    policy_type: str = Field(..., description="Policy type name")
    configuration: dict[str, Any] = Field(
        ..., description="Filled configuration schema"
    )
    endpoint_id: UUID = Field(..., description="ID of the endpoint to attach to")

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "name": "Rate limit 100/min",
                "policy_type": "rate_limit",
                "configuration": {
                    "rate": "100/m",
                },
                "endpoint_id": "123e4567-e89b-12d3-a456-426614174000",
            }
        }


class PolicyResponse(BaseModel):
    """Response model for policy details."""

    id: UUID = Field(..., description="Unique identifier")
    name: str = Field(..., description="Policy name")
    policy_type: str = Field(..., description="Policy type name")
    configuration: dict[str, Any] = Field(..., description="Configuration")
    endpoint_id: UUID = Field(..., description="Endpoint ID")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    class Config:
        """Pydantic config."""

        from_attributes = True


class PolicyListItem(BaseModel):
    """Response model for policy in list view."""

    id: UUID = Field(..., description="Unique identifier")
    name: str = Field(..., description="Policy name")
    policy_type: str = Field(..., description="Policy type name")
    endpoint_id: UUID = Field(..., description="Endpoint ID")
    created_at: datetime = Field(..., description="Creation timestamp")

    class Config:
        """Pydantic config."""

        from_attributes = True
