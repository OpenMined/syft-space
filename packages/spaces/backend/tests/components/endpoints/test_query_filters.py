"""A query's ``filters`` on the way to the store: the binding validates
against the endpoint's allowlist, the handler turns a refusal into a
structured 400, and ``filterable_fields`` is stored as sent."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from pydantic import TypeAdapter, ValidationError

from syft_space.components.dataset_types.interfaces import BaseDatasetType
from syft_space.components.endpoints.entities import Endpoint
from syft_space.components.endpoints.handlers import EndpointHandler
from syft_space.components.endpoints.query_handler import QueryEndpointHandler
from syft_space.components.endpoints.repository import UNSET
from syft_space.components.endpoints.schemas import (
    AuthenticatedQueryRequest,
    QueryEndpointRequest,
    UpdateEndpointRequest,
)
from syft_space.components.shared.filter_types import (
    FieldFilterSpec,
    FilterCondition,
    FilterNode,
    FilterValidationError,
    ops_for,
)
from syft_space.components.shared.metadata_types import MetadataType
from syft_space.components.shared.search_types import SearchResult

NODE = TypeAdapter(FilterNode)
SPEC = {
    "title": FieldFilterSpec(
        type=MetadataType.STRING, ops=ops_for(MetadataType.STRING)
    ),
    "price": FieldFilterSpec(
        type=MetadataType.NUMBER, ops=ops_for(MetadataType.NUMBER)
    ),
}


def _cond(field: str, op: str, value) -> dict:
    return {"type": "condition", "field": field, "op": op, "value": value}


# ============== the binding ==============


def _binding() -> BaseDatasetType:
    binding = BaseDatasetType.__new__(BaseDatasetType)
    binding.vector_store = MagicMock()
    binding.vector_store.filter_schema = AsyncMock(return_value=dict(SPEC))
    binding.metadata = MagicMock()
    return binding


async def test_the_spec_is_the_stores_unless_the_endpoint_names_fields():
    binding = _binding()
    assert await binding.filter_spec(None) == SPEC
    assert await binding.filter_spec(["price", "stale"]) == {"price": SPEC["price"]}
    assert await binding.filter_spec([]) == {}


async def test_validation_runs_against_the_allowlisted_spec():
    binding = _binding()
    node = NODE.validate_python(_cond("price", "lte", "10"))
    out = await binding.validate_filters(node, ["price"])
    assert isinstance(out, FilterCondition) and out.value == 10
    with pytest.raises(FilterValidationError) as info:
        await binding.validate_filters(node, ["title"])
    assert info.value.field == "price"


# ============== the handler ==============

TENANT_ID = uuid4()
DATASET_ID = uuid4()


def _handler(dataset_instance: MagicMock) -> QueryEndpointHandler:
    dataset_repository = MagicMock()
    dataset_repository.get_by_id = AsyncMock(
        return_value=SimpleNamespace(
            id=DATASET_ID, tenant_id=TENANT_ID, dtype="chroma", configuration={}
        )
    )
    registry = MagicMock()
    registry.get_dataset_type = MagicMock(
        return_value=MagicMock(return_value=dataset_instance)
    )
    return QueryEndpointHandler(
        endpoint_repository=MagicMock(),
        dataset_repository=dataset_repository,
        model_repository=MagicMock(),
        policy_repository=MagicMock(),
        dataset_registry=registry,
        model_registry=MagicMock(),
        policy_registry=MagicMock(),
    )


def _endpoint(filterable_fields=None) -> Endpoint:
    return Endpoint(
        name="ep",
        slug="ep",
        tenant_id=TENANT_ID,
        dataset_id=DATASET_ID,
        response_type="raw",
        published=True,
        filterable_fields=filterable_fields,
    )


def _request(filters: dict | None) -> AuthenticatedQueryRequest:
    return AuthenticatedQueryRequest.from_request(
        QueryEndpointRequest(messages="q", filters=filters), "u@example.org"
    )


async def test_a_refused_filter_is_a_400_naming_field_and_reason():
    instance = MagicMock()
    instance.validate_filters = AsyncMock(
        side_effect=FilterValidationError("secret", "not a filterable field")
    )
    instance.search = AsyncMock()
    with pytest.raises(HTTPException) as info:
        await _handler(instance)._search_dataset(
            _endpoint(), _request(_cond("secret", "eq", 1)), "q"
        )
    assert info.value.status_code == 400
    assert info.value.detail == {"field": "secret", "reason": "not a filterable field"}
    instance.search.assert_not_awaited()


async def test_a_valid_filter_is_validated_with_the_allowlist_and_passed_to_search():
    instance = MagicMock()
    coerced = NODE.validate_python(_cond("price", "lte", 10))
    instance.validate_filters = AsyncMock(return_value=coerced)
    instance.search = AsyncMock(return_value=SearchResult())
    instance.public_metadata = dict
    instance.metadata.public_names = lambda: []
    await _handler(instance)._search_dataset(
        _endpoint(["price"]), _request(_cond("price", "lte", "10")), "q"
    )
    node, allowed = instance.validate_filters.await_args.args
    assert node.field == "price" and allowed == ["price"]
    assert instance.search.await_args.args[2].filters is coerced


async def test_no_filter_means_no_validation_and_none_to_the_store():
    instance = MagicMock()
    instance.validate_filters = AsyncMock()
    instance.search = AsyncMock(return_value=SearchResult())
    instance.public_metadata = dict
    instance.metadata.public_names = lambda: []
    await _handler(instance)._search_dataset(_endpoint(), _request(None), "q")
    instance.validate_filters.assert_not_awaited()
    assert instance.search.await_args.args[2].filters is None


def test_the_request_rejects_a_malformed_filter_before_the_handler():
    with pytest.raises(ValidationError):
        QueryEndpointRequest(messages="q", filters={"type": "condition", "field": "x"})


# ============== filterable_fields on the endpoint ==============


def test_update_may_carry_filterable_fields_alone_and_null_counts_as_sent():
    assert UpdateEndpointRequest(filterable_fields=["a"]).filterable_fields == ["a"]
    req = UpdateEndpointRequest(filterable_fields=None)
    assert "filterable_fields" in req.model_fields_set
    with pytest.raises(ValidationError):
        UpdateEndpointRequest()


async def test_update_handler_passes_unset_when_omitted_and_the_value_when_sent():
    repository = MagicMock()
    repository.update_by_slug = AsyncMock(return_value=None)
    handler = EndpointHandler.__new__(EndpointHandler)
    handler.endpoint_repository = repository
    for request, expected in [
        (UpdateEndpointRequest(name="n"), UNSET),
        (UpdateEndpointRequest(filterable_fields=None), None),
        (UpdateEndpointRequest(filterable_fields=["a"]), ["a"]),
    ]:
        with pytest.raises(HTTPException):  # the mock finds no endpoint
            await handler.update_endpoint("ep", request, SimpleNamespace(id=TENANT_ID))
        assert (
            repository.update_by_slug.await_args.kwargs["filterable_fields"] == expected
        )
