"""Metadata declarations: which keys a source or vector store writes, and
which of those may leave the space in a search response.

A source and a vector store each declare their own keys as a
``MetadataFields`` subclass, injected on the provider / store class as
``METADATA_FIELDS``. A dataset type wires the two into one
``DatasetMetadata``, which filters a document's metadata before it leaves.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, ClassVar

from pydantic import BaseModel

__all__ = ["DatasetMetadata", "MetadataField", "MetadataFields"]


class MetadataField(BaseModel, frozen=True):
    """One metadata key. ``hidden`` keys never leave the space."""

    name: str
    hidden: bool = False


class MetadataFields:
    """What one contributor (a source or a store) says about its own keys.

    ``fields`` is the static declaration. ``declared`` may compute it from
    ``config`` when the keys are only known per dataset. ``derived`` lists
    keys this contributor manufactures from another's declaration.
    """

    fields: ClassVar[tuple[MetadataField, ...]] = ()

    def __init__(self, config: Mapping[str, Any] | None = None) -> None:
        self.config: Mapping[str, Any] = config or {}

    def declared(self) -> tuple[MetadataField, ...]:
        return self.fields

    def derived(self, source: MetadataFields) -> tuple[MetadataField, ...]:
        return ()


class DatasetMetadata:
    """The composed declarations of one binding's source and store."""

    def __init__(self, source: MetadataFields, store: MetadataFields) -> None:
        self.fields: tuple[MetadataField, ...] = (
            source.declared() + store.declared() + store.derived(source)
        )

    def public(self, metadata: Mapping[str, Any]) -> dict[str, Any]:
        """Keep the keys some field declares public and none declares hidden."""
        hidden = {f.name for f in self.fields if f.hidden}
        public = {f.name for f in self.fields if not f.hidden} - hidden
        return {k: v for k, v in metadata.items() if k in public}
