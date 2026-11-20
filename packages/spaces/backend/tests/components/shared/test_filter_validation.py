"""A query filter checked against a dataset's spec: every field, operator
and value is either accepted and coerced, or named in the error."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import TypeAdapter

from syft_space.components.shared.filter_types import (
    FieldFilterSpec,
    FilterCondition,
    FilterGroup,
    FilterNode,
    FilterOperator,
    FilterValidationError,
    FilterValueDtype,
    ops_for,
    validate_filters,
)
from syft_space.components.shared.metadata_types import MetadataType

NODE = TypeAdapter(FilterNode)

SPEC = {
    "title": FieldFilterSpec(
        type=MetadataType.STRING, ops=ops_for(MetadataType.STRING)
    ),
    "price": FieldFilterSpec(
        type=MetadataType.NUMBER, ops=ops_for(MetadataType.NUMBER)
    ),
    "published": FieldFilterSpec(
        type=MetadataType.DATETIME, ops=ops_for(MetadataType.DATETIME)
    ),
    "tags": FieldFilterSpec(
        type=MetadataType.STRING_LIST, ops=ops_for(MetadataType.STRING_LIST)
    ),
    "draft": FieldFilterSpec(type=MetadataType.BOOLEAN, ops=(FilterOperator.EQUAL,)),
}


def _cond(field: str, op: str, value) -> dict:
    return {"type": "condition", "field": field, "op": op, "value": value}


def _validate(node: dict) -> FilterCondition | FilterGroup:
    return validate_filters(NODE.validate_python(node), SPEC)


def _error(node: dict) -> FilterValidationError:
    with pytest.raises(FilterValidationError) as info:
        _validate(node)
    return info.value


def test_values_are_coerced_by_the_declared_type_and_tagged_with_its_dtype():
    out = _validate(_cond("price", "lte", "1000"))
    assert isinstance(out, FilterCondition)
    assert out.value == 1000
    assert out.value_dtype is FilterValueDtype.NUMERIC


def test_a_datetime_value_becomes_aware():
    out = _validate(_cond("published", "gte", "2024-01-01"))
    assert out.value == datetime(2024, 1, 1, tzinfo=timezone.utc)


def test_a_list_value_is_coerced_item_by_item():
    out = _validate(_cond("tags", "contains_any", ["a", 1]))
    assert out.value == ["a", "1"]


def test_groups_are_rebuilt_with_validated_operands():
    out = _validate(
        {
            "type": "group",
            "op": "and",
            "operands": [_cond("price", "gt", "5"), _cond("title", "eq", "x")],
        }
    )
    assert isinstance(out, FilterGroup)
    assert [o.value for o in out.operands] == [5, "x"]
    assert all(o.value_dtype is not None for o in out.operands)


def test_an_unknown_field_is_named():
    err = _error(_cond("secret", "eq", 1))
    assert (err.field, err.reason) == ("secret", "not a filterable field")


def test_an_operator_outside_the_field_ops_is_refused():
    err = _error(_cond("title", "gt", "a"))
    assert err.field == "title"
    assert "'gt' is not allowed for a string field" in err.reason


def test_a_list_operator_needs_a_list_and_a_scalar_one_a_scalar():
    assert "takes a list" in _error(_cond("tags", "contains_any", "a")).reason
    assert "takes a single value" in _error(_cond("price", "eq", [1])).reason


def test_an_uncoercible_value_is_reported_with_its_field():
    err = _error(_cond("price", "eq", "lots"))
    assert err.field == "price"
    assert "Cannot coerce" in err.reason


def test_a_bad_boolean_is_reported():
    assert _error(_cond("draft", "eq", "maybe")).field == "draft"


def test_not_is_not_a_query_operator():
    err = _error({"type": "group", "op": "not", "operands": [_cond("price", "eq", 1)]})
    assert "'not' is not allowed" in err.reason


def test_the_first_problem_in_a_tree_is_the_one_raised():
    err = _error(
        {
            "type": "group",
            "op": "or",
            "operands": [_cond("price", "eq", 1), _cond("nope", "eq", 1)],
        }
    )
    assert err.field == "nope"


def test_the_error_is_a_value_error_with_a_readable_message():
    err = _error(_cond("nope", "eq", 1))
    assert isinstance(err, ValueError)
    assert str(err) == "nope: not a filterable field"
