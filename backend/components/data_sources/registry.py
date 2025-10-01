from __future__ import annotations
from typing import Type, Dict
from .interfaces import DataSource, DataSourceProvisioner

_data_sources: Dict[str, Type[DataSource]] = {}
_provisioners: Dict[str, Type[DataSourceProvisioner]] = {}


def register_data_source(cls: Type[DataSource]) -> None:
    key = getattr(cls, "SOURCE_NAME", None)
    if not key:
        raise ValueError(f"{cls.__name__} missing SOURCE_NAME")
    if key in _data_sources:
        raise ValueError(f"Data source already registered for source '{key}'")
    _data_sources[key] = cls


def register_data_provisioner(cls: Type[DataSourceProvisioner]) -> None:
    key = getattr(cls, "SOURCE_NAME", None)
    if not key:
        raise ValueError(f"{cls.__name__} missing SOURCE_NAME")
    if key in _provisioners:
        raise ValueError(
            f"Data source provisioner already registered for source '{key}'"
        )
    _provisioners[key] = cls


def get_data_source(source_name: str) -> Type[DataSource]:
    try:
        return _data_sources[source_name]
    except KeyError:
        raise KeyError(f"No data source for source '{source_name}'")


def get_data_provisioner(source_name: str) -> Type[DataSourceProvisioner]:
    try:
        return _provisioners[source_name]
    except KeyError:
        raise KeyError(f"No data source provisioner for source '{source_name}'")


def list_data_sources() -> list[str]:
    return sorted(_data_sources.keys())


def list_data_source_provisioners() -> list[str]:
    return sorted(_provisioners.keys())
