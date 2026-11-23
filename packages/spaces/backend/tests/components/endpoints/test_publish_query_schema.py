"""The publish payload names the metadata keys a query may return and the
fields it may filter on, read from the dataset binding. A schema the store
cannot describe publishes ``filters: null`` rather than failing."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from syft_space.components.endpoints.publish_handler import PublishEndpointHandler
from syft_space.components.shared.filter_types import (
    MAX_CONDITIONS,
    MAX_DEPTH,
    MAX_LIST_VALUES,
    FieldFilterSpec,
    ops_for,
)
from syft_space.components.shared.metadata_types import (
    DatasetMetadata,
    MetadataField,
    MetadataFields,
    MetadataType,
)
from syft_space.components.shared.syfthub import SyftHubClient

TENANT_ID = uuid4()

TITLE = FieldFilterSpec(type=MetadataType.STRING, ops=ops_for(MetadataType.STRING))
YEAR = FieldFilterSpec(type=MetadataType.NUMBER, ops=ops_for(MetadataType.NUMBER))
SPECS = {"title": TITLE, "year": YEAR}


class _Fields(MetadataFields):
    fields = (
        MetadataField(name="title", type=MetadataType.STRING),
        MetadataField(name="year", type=MetadataType.NUMBER),
        MetadataField(name="secret", hidden=True),
    )


class _Binding:
    """A binding whose store answers with ``SPECS`` cut to the allowlist."""

    unreachable = False

    def __init__(self, configuration):
        self.metadata = DatasetMetadata(_Fields(configuration), MetadataFields())

    async def filter_spec(self, allowed=None):
        if self.unreachable:
            raise ConnectionError("store down")
        if allowed is None:
            return SPECS
        return {n: SPECS[n] for n in allowed if n in SPECS}


class _Unreachable(_Binding):
    unreachable = True


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


def _handler(
    binding=_Binding, registry_hit: bool = True, filterable_fields=None
) -> PublishEndpointHandler:
    dataset = SimpleNamespace(
        dtype="fake", configuration={"k": "v"}, filterable_fields=filterable_fields
    )
    dataset_repository = SimpleNamespace(get_by_id=AsyncMock(return_value=dataset))

    def get_dataset_type(name):
        if not registry_hit:
            raise KeyError(name)
        return binding

    return PublishEndpointHandler(
        endpoint_repository=SimpleNamespace(),
        marketplace_repository=SimpleNamespace(),
        dataset_repository=dataset_repository,
        model_repository=SimpleNamespace(),
        dataset_registry=SimpleNamespace(get_dataset_type=get_dataset_type),
        model_registry=SimpleNamespace(),
        client_factory=SyftHubClient,
    )


async def _query_schema(handler: PublishEndpointHandler, dataset_id=None):
    payload = await handler._build_publish_payload(_endpoint(dataset_id or uuid4()))
    return payload["query_schema"]


def _filters(fields: dict) -> dict:
    return {
        "fields": fields,
        "logic": ["and", "or"],
        "max_depth": MAX_DEPTH,
        "max_conditions": MAX_CONDITIONS,
        "max_list_values": MAX_LIST_VALUES,
    }


@pytest.mark.asyncio
async def test_payload_carries_every_filterable_field_by_default() -> None:
    schema = await _query_schema(_handler())
    assert schema["metadata_fields"] == ["title", "year"]
    assert schema["filters"] == _filters(
        {
            "title": {"type": "string", "ops": ["eq", "ne", "in", "nin"]},
            "year": {
                "type": "number",
                "ops": ["eq", "ne", "gt", "gte", "lt", "lte", "in", "nin"],
            },
        }
    )


@pytest.mark.asyncio
async def test_a_restricted_allowlist_publishes_only_those_fields() -> None:
    schema = await _query_schema(_handler(filterable_fields=["year", "gone"]))
    assert schema["metadata_fields"] == ["title", "year"]
    assert list(schema["filters"]["fields"]) == ["year"]


@pytest.mark.asyncio
async def test_filtering_disabled_publishes_no_fields() -> None:
    schema = await _query_schema(_handler(filterable_fields=[]))
    assert schema["filters"] == _filters({})


@pytest.mark.asyncio
async def test_model_only_endpoint_publishes_nothing_to_filter() -> None:
    payload = await _handler()._build_publish_payload(_endpoint(None))
    assert payload["query_schema"] == {"metadata_fields": [], "filters": None}


@pytest.mark.asyncio
async def test_an_unreachable_store_publishes_null_filters() -> None:
    schema = await _query_schema(_handler(binding=_Unreachable))
    assert schema == {"metadata_fields": ["title", "year"], "filters": None}


@pytest.mark.asyncio
async def test_unknown_dataset_type_does_not_block_publishing() -> None:
    payload = await _handler(registry_hit=False)._build_publish_payload(
        _endpoint(uuid4())
    )
    assert payload["query_schema"] == {"metadata_fields": [], "filters": None}
    assert payload["connect"][0]["config"]["path"] == "/api/v1/endpoints/ep/query"
