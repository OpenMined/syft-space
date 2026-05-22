"""Configs for MPP payment policies.

`MppPaymentConfig` is the shared base — price + applied_to. Subclasses fix
`unit_type` to a Literal const so the field is part of the schema (not
runtime-injected) and surfaces naturally through `model_dump()` to be
published to SyftHub.

Older policy rows used `price_per_request` or `price_per_document` as the
field name — both still validate via AliasChoices for graceful migration.
"""

from typing import Literal

from pydantic import AliasChoices, BaseModel, Field


class MppPaymentConfig(BaseModel):
    """Shared base for all MPP payment configs."""

    price: float = Field(
        ge=0,
        description="Price per unit in USD",
        validation_alias=AliasChoices(
            "price", "price_per_request", "price_per_document"
        ),
    )
    applied_to: list[str] = Field(
        default_factory=lambda: ["*"],
        description="List of user email patterns. Use '*' for all users.",
    )


class MppPerRequestConfig(MppPaymentConfig):
    """Config for MppPerRequestPolicy — charges price per query."""

    unit_type: Literal["request"] = "request"


class MppPerDocumentConfig(MppPaymentConfig):
    """Config for MppPerDocumentPolicy — charges price per retrieved document."""

    unit_type: Literal["document"] = "document"
