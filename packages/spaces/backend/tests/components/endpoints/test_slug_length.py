"""``CreateEndpointRequest`` caps the slug at 63, the width of the Hub's column."""

from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError

from syft_space.components.endpoints.schemas import CreateEndpointRequest


def _request(slug: str) -> CreateEndpointRequest:
    return CreateEndpointRequest(
        name="ep", slug=slug, dataset_id=uuid4(), model_id=uuid4()
    )


@pytest.mark.parametrize("length", [3, 63])
def test_slug_length_within_cap(length: int) -> None:
    assert len(_request("a" * length).slug) == length


@pytest.mark.parametrize("length", [2, 64])
def test_slug_length_outside_cap(length: int) -> None:
    with pytest.raises(ValidationError, match="Slug must be at"):
        _request("a" * length)
