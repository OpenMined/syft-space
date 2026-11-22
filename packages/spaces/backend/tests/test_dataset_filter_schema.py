"""``GET /datasets/{name}/filter-schema``: the unrestricted spec the owner
picks from; 404 for an unknown dataset, 503 when the store cannot answer."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from syft_space.components.datasets.handlers import DatasetHandler
from syft_space.components.shared.filter_types import (
    FieldFilterSpec,
    FilterSchema,
    ops_for,
)
from syft_space.components.shared.metadata_types import MetadataType

TENANT = SimpleNamespace(id=uuid4())
SPECS = {
    "year": FieldFilterSpec(type=MetadataType.NUMBER, ops=ops_for(MetadataType.NUMBER))
}


class _Binding:
    def __init__(self, configuration):
        self.configuration = configuration

    async def filter_spec(self, allowed=None):
        assert allowed is None, "the route reports the spec before the allowlist"
        return SPECS


class _Unreachable(_Binding):
    async def filter_spec(self, allowed=None):
        raise ConnectionError("store down")


def _handler(binding=_Binding, found: bool = True) -> DatasetHandler:
    handler = DatasetHandler.__new__(DatasetHandler)
    handler.repository = MagicMock()
    dataset = SimpleNamespace(dtype="fake", configuration={}, filterable_fields=["x"])
    handler.repository.get_by_name = AsyncMock(return_value=dataset if found else None)
    handler.registry = SimpleNamespace(get_dataset_type=lambda name: binding)
    return handler


async def test_the_schema_is_the_stores_spec_before_the_allowlist():
    assert await _handler().get_filter_schema("d", TENANT) == FilterSchema(fields=SPECS)


async def test_an_unknown_dataset_is_404():
    with pytest.raises(HTTPException) as e:
        await _handler(found=False).get_filter_schema("d", TENANT)
    assert e.value.status_code == 404


async def test_a_store_that_cannot_answer_is_503_with_the_reason():
    with pytest.raises(HTTPException) as e:
        await _handler(binding=_Unreachable).get_filter_schema("d", TENANT)
    assert e.value.status_code == 503
    assert "store down" in e.value.detail
