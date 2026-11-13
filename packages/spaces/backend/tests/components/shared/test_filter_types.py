"""The shared filter tree: one model for an owner's locked filter and a
caller's query filter, with the caps every store relies on."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import TypeAdapter, ValidationError

from syft_space.components.shared.filter_types import (
    MAX_CONDITIONS,
    MAX_DEPTH,
    MAX_LIST_VALUES,
    WIRE_LOGIC,
    WIRE_OPERATORS,
    FieldFilterSpec,
    FilterCondition,
    FilterGroup,
    FilterNode,
    FilterOperator,
    FilterValueDtype,
    LogicalOperator,
    condition_count,
    depth,
    dtype_for,
    ops_for,
    specs_for,
)
from syft_space.components.shared.metadata_types import MetadataField, MetadataType

NODE = TypeAdapter(FilterNode)


def _cond(field: str = "f", op: str = "eq", value=1, **extra) -> dict:
    return {"type": "condition", "field": field, "op": op, "value": value, **extra}


def _group(op: str, *operands: dict) -> dict:
    return {"type": "group", "op": op, "operands": list(operands)}


def _nested(levels: int) -> dict:
    node = _cond()
    for _ in range(levels):
        node = _group("and", node)
    return node


# ============== the condition ==============


def test_field_is_canonical_and_property_is_accepted():
    """Stored Weaviate configs and the current form send ``property``."""
    by_field = FilterCondition.model_validate(_cond("title"))
    by_property = FilterCondition.model_validate(
        {"type": "condition", "property": "title", "op": "eq", "value": 1}
    )
    assert by_field.field == by_property.field == "title"
    assert "field" in by_field.model_dump() and "property" not in by_field.model_dump()


def test_without_a_dtype_the_value_is_kept_as_sent():
    """A query carries no dtype: the binding coerces by the declared type."""
    c = FilterCondition.model_validate(_cond(op="gte", value="2024-01-01"))
    assert c.value_dtype is None
    assert c.value == "2024-01-01"


def test_with_a_dtype_the_value_is_coerced_and_the_operator_checked():
    c = FilterCondition.model_validate(
        _cond(op="gte", value="2024-01-01", value_dtype="datetime")
    )
    assert c.value == datetime(2024, 1, 1, tzinfo=timezone.utc)
    with pytest.raises(ValidationError, match="not allowed for dtype 'boolean'"):
        FilterCondition.model_validate(
            _cond(op="gt", value=True, value_dtype="boolean")
        )


@pytest.mark.parametrize("op", ["in", "nin"])
def test_in_and_nin_coerce_a_list(op):
    c = FilterCondition.model_validate(
        _cond(op=op, value=["1", "2"], value_dtype="numeric")
    )
    assert c.value == [1, 2]


def test_a_list_longer_than_the_cap_is_rejected():
    with pytest.raises(ValidationError, match=f"at most {MAX_LIST_VALUES}"):
        FilterCondition.model_validate(
            _cond(op="in", value=list(range(MAX_LIST_VALUES + 1)))
        )
    FilterCondition.model_validate(_cond(op="in", value=list(range(MAX_LIST_VALUES))))


# ============== the tree ==============


def test_nesting_is_allowed_to_max_depth_and_no_further():
    assert depth(NODE.validate_python(_nested(MAX_DEPTH))) == MAX_DEPTH
    with pytest.raises(ValidationError, match=f"deeper than {MAX_DEPTH}"):
        NODE.validate_python(_nested(MAX_DEPTH + 1))


def test_depth_counts_groups_on_the_longest_path():
    tree = NODE.validate_python(
        _group("or", _cond(), _group("and", _cond(), _group("or", _cond())))
    )
    assert depth(tree) == 3
    assert depth(NODE.validate_python(_cond())) == 0


def test_conditions_are_counted_over_the_whole_tree():
    tree = NODE.validate_python(_group("and", _cond(), _group("or", _cond(), _cond())))
    assert condition_count(tree) == 3
    with pytest.raises(ValidationError, match=f"more than {MAX_CONDITIONS}"):
        NODE.validate_python(_group("and", *[_cond()] * (MAX_CONDITIONS + 1)))


def test_a_group_needs_at_least_one_operand():
    with pytest.raises(ValidationError):
        FilterGroup.model_validate(_group("and"))


def test_the_discriminator_rejects_an_unknown_node_type():
    with pytest.raises(ValidationError):
        NODE.validate_python({"type": "clause", "op": "eq"})


# ============== what a query may send ==============


def test_the_wire_set_leaves_like_is_none_and_not_to_the_owner():
    assert FilterOperator.LIKE not in WIRE_OPERATORS
    assert FilterOperator.IS_NONE not in WIRE_OPERATORS
    assert LogicalOperator.NOT not in WIRE_LOGIC
    assert {op.value for op in WIRE_OPERATORS} == {
        "eq",
        "ne",
        "gt",
        "gte",
        "lt",
        "lte",
        "in",
        "nin",
        "contains_any",
        "contains_all",
    }


@pytest.mark.parametrize(
    ("type", "ops"),
    [
        (MetadataType.STRING, {"eq", "ne", "in", "nin"}),
        (MetadataType.NUMBER, {"eq", "ne", "gt", "gte", "lt", "lte", "in", "nin"}),
        (MetadataType.BOOLEAN, {"eq", "ne"}),
        (MetadataType.DATETIME, {"eq", "ne", "gt", "gte", "lt", "lte"}),
        (MetadataType.STRING_LIST, {"contains_any", "contains_all"}),
        (MetadataType.NUMBER_LIST, {"contains_any", "contains_all"}),
    ],
)
def test_ops_for_each_type(type, ops):
    assert {op.value for op in ops_for(type)} == ops
    assert set(ops_for(type)) <= WIRE_OPERATORS


def test_dtype_for_maps_every_type_onto_the_existing_coercer():
    assert {t: dtype_for(t) for t in MetadataType} == {
        MetadataType.STRING: FilterValueDtype.STRING,
        MetadataType.NUMBER: FilterValueDtype.NUMERIC,
        MetadataType.BOOLEAN: FilterValueDtype.BOOLEAN,
        MetadataType.DATETIME: FilterValueDtype.DATETIME,
        MetadataType.STRING_LIST: FilterValueDtype.STRING,
        MetadataType.NUMBER_LIST: FilterValueDtype.NUMERIC,
    }


def test_specs_cut_each_field_to_the_store_and_drop_untyped_or_empty():
    fields = (
        MetadataField(name="n", type=MetadataType.NUMBER),
        MetadataField(name="tags", type=MetadataType.STRING_LIST),
        MetadataField(name="remote", type=None),
    )
    store_can = frozenset({FilterOperator.EQUAL, FilterOperator.GREATER_THAN})
    assert specs_for(fields, store_can) == {
        "n": FieldFilterSpec(
            type=MetadataType.NUMBER,
            ops=(FilterOperator.EQUAL, FilterOperator.GREATER_THAN),
        )
    }


def test_a_spec_serialises_to_type_and_ops():
    spec = FieldFilterSpec(
        type=MetadataType.DATETIME, ops=ops_for(MetadataType.DATETIME)
    )
    assert spec.model_dump(mode="json") == {
        "type": "datetime",
        "ops": ["eq", "ne", "gt", "gte", "lt", "lte"],
    }
