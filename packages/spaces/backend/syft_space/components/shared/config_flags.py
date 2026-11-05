"""Per-field flags on configuration models.

A source or vector store marks the fields of its own config model with
``cfg_flags`` in ``Field(json_schema_extra=...)``. The flags ride along in
the JSON schema, where the binding (``BaseDatasetType``) and the frontend
read them back. A field without flags is locked and public.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Final

__all__ = [
    "EDITABLE",
    "VISIBILITY",
    "Visibility",
    "cfg_flags",
    "editable_fields",
    "fields_with_visibility",
]

# Schema keys the flags are printed under.
EDITABLE: Final = "editable"
VISIBILITY: Final = "visibility"


class Visibility(StrEnum):
    """Who gets to see a field's value."""

    PUBLIC = "public"  # value returned and shown
    SECRET = "secret"  # nosec B105 - value never returned; the field is shown without it
    INTERNAL = "internal"  # value returned, never shown to the owner


def cfg_flags(
    *,
    editable: bool = False,
    visibility: Visibility = Visibility.PUBLIC,
    **extra: Any,
) -> dict[str, Any]:
    """``json_schema_extra`` for a config field.

    Defaults print nothing, so an unflagged field reads the same as one
    flagged with none. ``extra`` passes through untouched (``format``,
    ``enum``, ...). An internal field cannot be editable: nobody sees it.
    """
    if editable and visibility is Visibility.INTERNAL:
        raise ValueError("an internal field cannot be editable")
    flags: dict[str, Any] = dict(extra)
    if editable:
        flags[EDITABLE] = True
    if visibility is not Visibility.PUBLIC:
        flags[VISIBILITY] = visibility.value
    return flags


def editable_fields(schema: dict[str, Any]) -> list[str]:
    """Property keys flagged editable, as the schema prints them."""
    return _fields_where(schema, EDITABLE, True)


def fields_with_visibility(schema: dict[str, Any], visibility: Visibility) -> list[str]:
    """Property keys with the given visibility, as the schema prints them.

    ``public`` is the unprinted default, so it matches no property here;
    ask for ``secret`` or ``internal``.
    """
    return _fields_where(schema, VISIBILITY, visibility)


def _fields_where(schema: dict[str, Any], flag: str, value: Any) -> list[str]:
    properties = schema.get("properties") or {}
    return [key for key, prop in properties.items() if prop.get(flag) == value]
