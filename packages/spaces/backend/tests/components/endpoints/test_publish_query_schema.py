"""The publish payload names the metadata keys a query may return, read from
the dataset binding's contract without building its collaborators."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from syft_space.components.endpoints.publish_handler import PublishEndpointHandler
from syft_space.components.shared.metadata_types import (
    DatasetMetadata,
    MetadataField,
    MetadataFields,
)

TENANT_ID = uuid4()


class _Fields(MetadataFields):
    fields = (MetadataField(name="title"), MetadataField(name="secret", hidden=True))


class _Binding:
    @classmethod
    def metadata_for(cls, configuration):
        return DatasetMetadata(_Fields(configuration), MetadataFields())


def _endpoint(dataset_id) -> SimpleNamespace:
    return SimpleNamespace(
        name="ep",
        slug="ep",
        summary="",
        description="",
        tenant_id=TENANT_ID,
        dataset_id=dataset_id,
        model_id=None,
        policies=[],
    )


def _handler(registry_hit: bool = True) -> PublishEndpointHandler:
    dataset_repository = SimpleNamespace(
        get_by_id=AsyncMock(
            return_value=SimpleNamespace(dtype="fake", configuration={"k": "v"})
        )
    )

    def get_dataset_type(name):
        if not registry_hit:
            raise KeyError(name)
        return _Binding

    return PublishEndpointHandler(
        endpoint_repository=SimpleNamespace(),
        marketplace_repository=SimpleNamespace(),
        dataset_repository=dataset_repository,
        model_repository=SimpleNamespace(),
        dataset_registry=SimpleNamespace(get_dataset_type=get_dataset_type),
        model_registry=SimpleNamespace(),
    )


@pytest.mark.asyncio
async def test_payload_carries_the_public_metadata_fields() -> None:
    payload = await _handler()._build_publish_payload(_endpoint(uuid4()))
    assert payload["query_schema"] == {"metadata_fields": ["title"]}


@pytest.mark.asyncio
async def test_model_only_endpoint_publishes_an_empty_list() -> None:
    payload = await _handler()._build_publish_payload(_endpoint(None))
    assert payload["query_schema"] == {"metadata_fields": []}


@pytest.mark.asyncio
async def test_unknown_dataset_type_does_not_block_publishing() -> None:
    payload = await _handler(registry_hit=False)._build_publish_payload(
        _endpoint(uuid4())
    )
    assert payload["query_schema"] == {"metadata_fields": []}
    assert payload["connect"][0]["config"]["path"] == "/api/v1/endpoints/ep/query"
