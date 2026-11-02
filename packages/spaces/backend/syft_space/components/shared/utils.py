"""Shared utilities for the application."""

import fnmatch
from typing import Any

from pydantic.json_schema import GenerateJsonSchema


def matches_any_pattern(value: str, patterns: list[str]) -> bool:
    """Check if value matches any of the glob patterns.

    Uses Unix shell-style wildcards:
    - `*` matches everything
    - `?` matches single character
    - `[seq]` matches any char in seq
    - `[!seq]` matches any char not in seq

    Examples:
        - `*` matches all
        - `*@company.com` matches all users from company.com
        - `admin-*@*` matches admin users from any domain
        - `user@test.com` matches exact email

    Args:
        value: The value to check (e.g., email address)
        patterns: List of glob patterns to match against

    Returns:
        True if value matches any pattern
    """
    if not patterns:
        return False
    value_lower = value.lower()
    return any(fnmatch.fnmatch(value_lower, p.lower()) for p in patterns)


class ConfigSchemaGenerator(GenerateJsonSchema):
    """Generates configuration schemas for frontend dynamic form rendering.

    Produces a simplified schema with 'properties', 'required', and '$defs'.
    A property typed as an Enum is printed inline (``type`` + ``enum`` on the
    property itself) rather than as a ``$ref``: the frontend reads a field's
    choices straight off the property. Other ``$defs`` are kept as they are.

    Usage:
        from syft_space.components.shared.utils import ConfigSchemaGenerator

        schema = MyConfig.model_json_schema(schema_generator=ConfigSchemaGenerator)
    """

    def generate(self, schema: Any, mode: str = "validation") -> dict[str, Any]:
        """Generate a simplified JSON schema.

        Args:
            schema: The Pydantic schema to process
            mode: Schema generation mode ('validation' or 'serialization')

        Returns:
            Schema with 'properties', 'required', and '$defs' (if present)
        """
        json_schema = super().generate(schema, mode)
        defs = json_schema.get("$defs", {})

        result: dict[str, Any] = {
            "properties": {
                name: _inline_enum(prop, defs)
                for name, prop in json_schema.get("properties", {}).items()
            },
            "required": json_schema.get("required", []),
        }
        if defs:
            result["$defs"] = defs
        return result


def _inline_enum(prop: dict[str, Any], defs: dict[str, Any]) -> dict[str, Any]:
    """``prop`` with a ``$ref`` to an enum definition replaced by that
    definition's ``type`` and ``enum``, at the top level or inside an
    ``anyOf`` branch (an optional enum); any other property unchanged."""
    ref = prop.get("$ref", "")
    target = defs.get(ref.removeprefix("#/$defs/")) if ref else None
    if target and "enum" in target:
        inlined = {k: v for k, v in prop.items() if k != "$ref"}
        inlined.setdefault("type", target.get("type"))
        inlined["enum"] = target["enum"]
        return inlined
    if isinstance(prop.get("anyOf"), list):
        return {**prop, "anyOf": [_inline_enum(b, defs) for b in prop["anyOf"]]}
    return prop
