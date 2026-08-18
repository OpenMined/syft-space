"""Tests for response_type/attachment validation on ``CreateEndpointRequest``.

Creation is the only gate: ``raw`` needs a dataset, ``summary`` needs a
model, ``both`` needs both. Endpoints created before this validation keep
their legacy query behavior — the query path does not re-check.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError

from syft_space.components.endpoints.entities import (
    ResponseType,
    validate_response_type_attachments,
)
from syft_space.components.endpoints.schemas import CreateEndpointRequest


@pytest.mark.parametrize(
    ("response_type", "has_dataset", "has_model", "ok"),
    [
        (ResponseType.RAW, True, False, True),
        (ResponseType.RAW, True, True, True),
        (ResponseType.RAW, False, True, False),
        (ResponseType.SUMMARY, False, True, True),
        (ResponseType.SUMMARY, True, True, True),
        (ResponseType.SUMMARY, True, False, False),
        (ResponseType.BOTH, True, True, True),
        (ResponseType.BOTH, True, False, False),
        (ResponseType.BOTH, False, True, False),
        (ResponseType.BOTH, False, False, False),
    ],
)
def test_validate_response_type_attachments(
    response_type: ResponseType, has_dataset: bool, has_model: bool, ok: bool
) -> None:
    error = validate_response_type_attachments(
        response_type, has_dataset=has_dataset, has_model=has_model
    )
    assert (error is None) is ok


def _create_request(**kwargs) -> CreateEndpointRequest:
    return CreateEndpointRequest(name="test-ep", slug="test-ep", **kwargs)


@pytest.mark.parametrize(
    ("response_type", "attachments"),
    [
        ("raw", {"dataset_id": uuid4()}),
        ("summary", {"model_id": uuid4()}),
        ("summary", {"dataset_id": uuid4(), "model_id": uuid4()}),
        ("both", {"dataset_id": uuid4(), "model_id": uuid4()}),
    ],
)
def test_create_request_accepts_valid_attachments(
    response_type: str, attachments: dict
) -> None:
    request = _create_request(response_type=response_type, **attachments)
    assert request.response_type == response_type


@pytest.mark.parametrize(
    ("response_type", "attachments"),
    [
        ("raw", {"model_id": uuid4()}),
        ("summary", {"dataset_id": uuid4()}),
        ("both", {"dataset_id": uuid4()}),
        ("both", {"model_id": uuid4()}),
        ("both", {}),
    ],
)
def test_create_request_rejects_attachments_that_cant_serve_response_type(
    response_type: str, attachments: dict
) -> None:
    with pytest.raises(ValidationError, match=f"'{response_type}'"):
        _create_request(response_type=response_type, **attachments)


def test_create_request_rejects_unknown_response_type() -> None:
    with pytest.raises(ValidationError, match="Invalid response_type"):
        _create_request(response_type="summry", model_id=uuid4())
