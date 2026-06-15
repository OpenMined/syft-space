"""Redaction of model configurations before they leave the API.

Stored configurations can hold credentials (e.g. an OpenAI API key). The
model type declares how to strip them via
``BaseModelType.redact_configuration``; this helper resolves a ``dtype``
to its model type and delegates, so response builders can redact without
importing the registry themselves.
"""

from __future__ import annotations

from typing import Any

from syft_space.components.model_types.registry import MODEL_TYPE_REGISTRY


def redact_config(configuration: dict[str, Any], dtype: str) -> dict[str, Any]:
    """Return a copy of ``configuration`` safe to expose over the API.

    Delegates to the model type's ``redact_configuration``. Unknown dtypes
    fall back to the configuration unchanged.
    """
    try:
        model_type_cls = MODEL_TYPE_REGISTRY.get_model_type(dtype)
    except KeyError:
        return dict(configuration)
    return model_type_cls.redact_configuration(configuration)
