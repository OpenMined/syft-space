"""Metadata declarations: which keys a source or vector store writes, their
value types, and which of those may leave the space in a search response.

A source and a vector store each declare their own keys as a
``MetadataFields`` subclass, injected on the provider / store class as
``METADATA_FIELDS``. A dataset type wires the two into one
``DatasetMetadata``, which filters a document's metadata before it leaves
and names the fields a query may filter on.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from typing import Any, ClassVar

from pydantic import BaseModel

__all__ = ["DatasetMetadata", "MetadataField", "MetadataFields", "MetadataType"]


class MetadataType(StrEnum):
    """The value type a metadata key holds, as the writer produces it."""

    STRING = "string"
    NUMBER = "number"
    BOOLEAN = "boolean"
    DATETIME = "datetime"
    STRING_LIST = "string[]"
    NUMBER_LIST = "number[]"


class MetadataField(BaseModel, frozen=True):
    """One metadata key. ``hidden`` keys never leave the space.

    ``type`` is what the writer puts under the key. It is ``None`` until the
    writer states it, or when the store resolves it at runtime (a remote
    collection's own schema). An untyped field is never filterable.
    """

    name: str
    hidden: bool = False
    type: MetadataType | None = None


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
        self.declared: tuple[MetadataField, ...] = source.declared() + store.declared()
        self.derived: tuple[MetadataField, ...] = store.derived(source)
        self.fields: tuple[MetadataField, ...] = self.declared + self.derived

    def public(self, metadata: Mapping[str, Any]) -> dict[str, Any]:
        """Keep the keys some field declares public and none declares hidden."""
        public = set(self.public_names())
        return {k: v for k, v in metadata.items() if k in public}

    def public_names(self) -> list[str]:
        """Keys that may leave the space, in declaration order, once each."""
        hidden = {f.name for f in self.fields if f.hidden}
        return list(dict.fromkeys(f.name for f in self.fields if f.name not in hidden))

    def filter_candidates(self) -> tuple[MetadataField, ...]:
        """Public declared fields, once each: what a query may filter on
        before the store applies its own capability. Derived keys are
        storage twins, never a filter target."""
        hidden = {f.name for f in self.fields if f.hidden}
        derived = {f.name for f in self.derived}
        seen: dict[str, MetadataField] = {}
        for f in self.declared:
            if f.name in hidden or f.name in derived or f.name in seen:
                continue
            seen[f.name] = f
        return tuple(seen.values())
