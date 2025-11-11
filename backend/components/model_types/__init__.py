"""Model types package with type system for models."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .registry import ModelTypeRegistry


def register_builtin_types(registry: "ModelTypeRegistry") -> None:
    """Register all built-in model types.

    This is called explicitly from main.py - no import side effects.

    Args:
        registry: The model type registry to register types with
    """
    # Import and register built-in model types here as they're implemented
    from .openai.openai_type import OpenAIModelType

    registry.register_model_type(OpenAIModelType)


__all__ = ["register_builtin_types"]
