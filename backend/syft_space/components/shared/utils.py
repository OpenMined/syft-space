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
    The $defs section is preserved so $ref pointers remain valid — the frontend
    resolver handles $ref lookup at render time.

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

        result: dict[str, Any] = {
            "properties": json_schema.get("properties", {}),
            "required": json_schema.get("required", []),
        }
        if "$defs" in json_schema:
            result["$defs"] = json_schema["$defs"]
        return result
