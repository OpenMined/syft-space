"""Redaction of dataset configurations before they leave the API.

Stored configurations can hold credentials (e.g. a WordPress Application
Password). The binding declares how to strip them via
``BaseDatasetType.redact_configuration``; this helper resolves a ``dtype``
to its binding and delegates, so response builders can redact without
importing the registry themselves.
"""

from __future__ import annotations

from typing import Any

from syft_space.components.dataset_types.registry import DATASET_TYPE_REGISTRY


def redact_config(configuration: dict[str, Any], dtype: str) -> dict[str, Any]:
    """Return a copy of ``configuration`` safe to expose over the API.

    Delegates to the binding's ``redact_configuration``. Unknown dtypes
    fall back to the configuration unchanged.
    """
    try:
        dataset_type_cls = DATASET_TYPE_REGISTRY.get_dataset_type(dtype)
    except KeyError:
        return dict(configuration)
    return dataset_type_cls.redact_configuration(configuration)
