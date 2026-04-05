"""Xendit wallet configuration."""

from pydantic import BaseModel, Field


class XenditWalletConfig(BaseModel):
    """Xendit wallet credentials."""

    api_key: str = Field(..., description="Xendit API key")
    callback_token: str = Field(
        ..., description="Xendit webhook callback verification token"
    )
