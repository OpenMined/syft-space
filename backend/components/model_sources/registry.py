from __future__ import annotations
from typing import Type, Dict
from .interfaces import ModelSource, ModelSourceProvisioner

_model_sources: Dict[str, Type[ModelSource]] = {}
_model_source_provisioners: Dict[str, Type[ModelSourceProvisioner]] = {}


def register_model_source(cls: Type[ModelSource]) -> None:
    key = getattr(cls, "SOURCE_NAME", None)
    if not key:
        raise ValueError(f"{cls.__name__} missing SOURCE_NAME")
    if key in _model_sources:
        raise ValueError(f"Model source already registered for source '{key}'")
    _model_sources[key] = cls


def register_model_source_provisioner(cls: Type[ModelSourceProvisioner]) -> None:
    key = getattr(cls, "SOURCE_NAME", None)
    if not key:
        raise ValueError(f"{cls.__name__} missing SOURCE_NAME")
    if key in _model_source_provisioners:
        raise ValueError(
            f"Model source provisioner already registered for source '{key}'"
        )
    _model_source_provisioners[key] = cls


def get_model_source(source_name: str) -> Type[ModelSource]:
    try:
        return _model_sources[source_name]
    except KeyError:
        raise KeyError(f"No model source for source '{source_name}'")


def get_model_source_provisioner(source_name: str) -> Type[ModelSourceProvisioner]:
    try:
        return _model_source_provisioners[source_name]
    except KeyError:
        raise KeyError(f"No model source provisioner for source '{source_name}'")


def list_model_source_provisioners() -> list[str]:
    return sorted(_model_source_provisioners.keys())


def list_model_sources() -> list[str]:
    return sorted(_model_sources.keys())
