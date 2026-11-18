"""``filterable_fields`` on a dataset: stored as sent on create, and on
update ``null`` resets to every field while an omitted key leaves it alone."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from syft_space.components.datasets.handlers import DatasetHandler
from syft_space.components.datasets.repository import UNSET
from syft_space.components.datasets.schemas import (
    CreateDatasetRequest,
    UpdateDatasetRequest,
)

TENANT = SimpleNamespace(id=uuid4())


def test_create_defaults_to_every_filterable_field():
    req = CreateDatasetRequest(name="d", dtype="rss", configuration={})
    assert req.filterable_fields is None
    req = CreateDatasetRequest(
        name="d", dtype="rss", configuration={}, filterable_fields=[]
    )
    assert req.filterable_fields == []


def test_update_may_carry_filterable_fields_alone_and_null_counts_as_sent():
    assert UpdateDatasetRequest(filterable_fields=["a"]).filterable_fields == ["a"]
    req = UpdateDatasetRequest(filterable_fields=None)
    assert "filterable_fields" in req.model_fields_set
    with pytest.raises(ValidationError):
        UpdateDatasetRequest()


async def test_update_handler_passes_unset_when_omitted_and_the_value_when_sent():
    repository = MagicMock()
    repository.get_by_name = AsyncMock(return_value=SimpleNamespace(configuration={}))
    repository.update_by_name = AsyncMock(return_value=None)
    handler = DatasetHandler.__new__(DatasetHandler)
    handler.repository = repository
    for request, expected in [
        (UpdateDatasetRequest(summary="s"), UNSET),
        (UpdateDatasetRequest(filterable_fields=None), None),
        (UpdateDatasetRequest(filterable_fields=["a"]), ["a"]),
    ]:
        with pytest.raises(HTTPException):  # the mock finds nothing to update
            await handler.update_dataset("d", request, TENANT)
        assert (
            repository.update_by_name.await_args.kwargs["filterable_fields"] == expected
        )
