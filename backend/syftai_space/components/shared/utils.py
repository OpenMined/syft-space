"""Shared utilities for the application."""

from typing import Any

from pydantic.json_schema import GenerateJsonSchema


class ConfigSchemaGenerator(GenerateJsonSchema):
    """Generates clean configuration schemas without $defs and class metadata.

    Produces a simplified schema with just 'properties' and 'required',
    with all $ref references inlined. This is useful for frontend forms
    and API documentation where the full JSON Schema complexity isn't needed.

    Usage:
        from syftai_space.components.shared.utils import ConfigSchemaGenerator

        schema = MyConfig.model_json_schema(schema_generator=ConfigSchemaGenerator)
    """

    def generate(self, schema: Any, mode: str = "validation") -> dict[str, Any]:
        """Generate a simplified JSON schema.

        Args:
            schema: The Pydantic schema to process
            mode: Schema generation mode ('validation' or 'serialization')

        Returns:
            Simplified schema with just 'properties' and 'required'
        """
        json_schema = super().generate(schema, mode)

        # Inline $defs into properties (removes need for $ref)
        defs = json_schema.pop("$defs", {})
        for prop_schema in json_schema.get("properties", {}).values():
            if "$ref" in prop_schema:
                ref_name = prop_schema["$ref"].split("/")[-1]
                if ref_name in defs:
                    # Get the referenced schema
                    ref_schema = defs[ref_name].copy()
                    # Preserve description and default from the property
                    desc = prop_schema.get("description")
                    default = prop_schema.get("default")
                    # Replace property with inlined schema
                    prop_schema.clear()
                    prop_schema.update(ref_schema)
                    # Restore property-level overrides
                    if desc:
                        prop_schema["description"] = desc
                    if default is not None:
                        prop_schema["default"] = default

        # Return only properties and required fields
        return {
            "properties": json_schema.get("properties", {}),
            "required": json_schema.get("required", []),
        }
