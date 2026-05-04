"""MPP wallet schemas — credential management only."""

import re

from pydantic import BaseModel, Field, field_validator


class CreateMppWalletRequest(BaseModel):
    """Request to generate a new MPP wallet keypair."""

    name: str | None = Field(None, description="Optional wallet label")


class ImportMppWalletRequest(BaseModel):
    """Request to import an MPP wallet from private key."""

    private_key: str = Field(..., description="Wallet private key (hex string)")
    name: str | None = Field(None, description="Optional wallet label")


class UpdateMppWalletAddressRequest(BaseModel):
    """Request to manually update MPP wallet address."""

    wallet_address: str = Field(..., description="Ethereum-format wallet address")

    @field_validator("wallet_address")
    @classmethod
    def validate_ethereum_address(cls, v: str) -> str:
        if not re.match(r"^0x[0-9a-fA-F]{40}$", v):
            raise ValueError(
                "Invalid Ethereum address format. Must be 0x followed by 40 hex characters."
            )
        return v
