"""PaymentService API schemas for request/response models."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, HttpUrl


class UpdatePaymentServiceRequest(BaseModel):
    """Request model for updating payment service config (partial update)."""

    url: HttpUrl | None = Field(None, description="Payment service URL")
    email: EmailStr | None = Field(None, description="Payment service login email")
    password: str | None = Field(None, description="Payment service login password")

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "url": "https://payment.example.com",
                "email": "user@example.com",
                "password": "secret123",
            }
        }


class PaymentServiceResponse(BaseModel):
    """Response model for payment service config."""

    id: UUID = Field(..., description="Unique identifier")
    url: str = Field(..., description="Payment service URL")
    email: str = Field(..., description="Payment service login email")
    # Note: password is NOT returned for security
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    class Config:
        """Pydantic config."""

        from_attributes = True
