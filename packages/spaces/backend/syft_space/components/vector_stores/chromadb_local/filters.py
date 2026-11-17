"""Translation of the shared filter tree into a ChromaDB ``where`` clause."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from syft_space.components.shared.filter_types import (
    FilterCondition,
    FilterGroup,
    FilterOperator,
    FilterValueDtype,
    LogicalOperator,
)

__all__ = ["OPERATOR_MAP", "build_where"]

# ChromaDB's ``where`` operator per wire operator. ``contains_*`` is built
# from ``$contains`` (array membership of one value) below.
OPERATOR_MAP: dict[FilterOperator, str] = {
    FilterOperator.EQUAL: "$eq",
    FilterOperator.NOT_EQUAL: "$ne",
    FilterOperator.GREATER_THAN: "$gt",
    FilterOperator.GREATER_OR_EQUAL: "$gte",
    FilterOperator.LESS_THAN: "$lt",
    FilterOperator.LESS_OR_EQUAL: "$lte",
    FilterOperator.IN: "$in",
    FilterOperator.NOT_IN: "$nin",
}

_LOGIC = {LogicalOperator.AND: "$and", LogicalOperator.OR: "$or"}


def build_where(node: FilterCondition | FilterGroup) -> dict[str, Any]:
    """A validated tree as a ChromaDB ``where`` dict.

    A datetime condition targets the ``{field}_ts`` epoch twin that
    ``_chroma_scalars`` writes beside the ISO string. ``contains_any`` is an
    ``$or`` of ``$contains``, ``contains_all`` an ``$and``. ChromaDB wants
    at least two operands in a group, so a single operand is unwrapped.
    """
    if isinstance(node, FilterGroup):
        if node.op not in _LOGIC:
            raise ValueError(f"'{node.op.value}' is not a query operator")
        return _group(_LOGIC[node.op], [build_where(o) for o in node.operands])

    key, value = node.field, node.value
    if node.value_dtype is FilterValueDtype.DATETIME:
        key = f"{key}_ts"
        value = _epoch(value)

    if node.op is FilterOperator.CONTAINS_ANY:
        return _group("$or", [{key: {"$contains": v}} for v in value])
    if node.op is FilterOperator.CONTAINS_ALL:
        return _group("$and", [{key: {"$contains": v}} for v in value])
    return {key: {OPERATOR_MAP[node.op]: value}}


def _group(op: str, clauses: list[dict[str, Any]]) -> dict[str, Any]:
    return clauses[0] if len(clauses) == 1 else {op: clauses}


def _epoch(value: Any) -> Any:
    if isinstance(value, list):
        return [_epoch(v) for v in value]
    return int(value.timestamp()) if isinstance(value, datetime) else value
