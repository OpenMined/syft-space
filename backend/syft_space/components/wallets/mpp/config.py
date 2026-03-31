"""MPP wallet configuration."""

import re

from pydantic import BaseModel, Field, field_validator


class MppWalletConfig(BaseModel):
    """MPP wallet credentials (Tempo blockchain)."""

    wallet_address: str = Field(..., description="Tempo wallet address (0x-prefixed)")
    wallet_private_key: str = Field(..., description="Wallet private key (hex)")
    mpp_secret_key: str = Field(
        ..., description="HMAC secret key for MPP challenge signing"
    )

    @field_validator("wallet_address")
    @classmethod
    def validate_ethereum_address(cls, v: str) -> str:
        if not re.match(r"^0x[0-9a-fA-F]{40}$", v):
            raise ValueError(
                "Invalid Ethereum address format. Expected 0x followed by 40 hex characters."
            )
        return v
