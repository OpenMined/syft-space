"""Translation of the shared filter tree into Weaviate ``Filter`` objects."""

from __future__ import annotations

from typing import Any

from syft_space.components.shared.filter_types import (
    FilterCondition,
    FilterGroup,
    FilterOperator,
    LogicalOperator,
)

__all__ = ["OPERATOR_MAP", "build_filter_node"]

# Weaviate's ``_FilterByProperty`` method per operator. ``in`` is
# ``contains_any`` on a scalar property; ``nin`` is its negation, built
# explicitly below.
OPERATOR_MAP: dict[FilterOperator, str] = {
    FilterOperator.EQUAL: "equal",
    FilterOperator.NOT_EQUAL: "not_equal",
    FilterOperator.GREATER_THAN: "greater_than",
    FilterOperator.GREATER_OR_EQUAL: "greater_or_equal",
    FilterOperator.LESS_THAN: "less_than",
    FilterOperator.LESS_OR_EQUAL: "less_or_equal",
    FilterOperator.IN: "contains_any",
    FilterOperator.NOT_IN: "contains_any",
    FilterOperator.LIKE: "like",
    FilterOperator.IS_NONE: "is_none",
    FilterOperator.CONTAINS_ANY: "contains_any",
    FilterOperator.CONTAINS_ALL: "contains_all",
}

# The store's own object timestamp, not a property: filtered via
# ``Filter.by_creation_time()``.
CREATION_TIME = "creation_time"


def build_filter_node(node: FilterCondition | FilterGroup, filter_cls: Any) -> Any:
    """Recursively build a Weaviate Filter object from a filter node.

    Args:
        node: A FilterCondition or FilterGroup to convert.
        filter_cls: The Weaviate ``Filter`` class (passed in to avoid
            a hard dependency on the weaviate package at import time).

    Returns:
        A Weaviate _Filters object ready to pass to a query.
    """
    if isinstance(node, FilterCondition):
        if node.field == CREATION_TIME:
            target = filter_cls.by_creation_time()
        else:
            target = filter_cls.by_property(node.field)
        built = getattr(target, OPERATOR_MAP[node.op])(node.value)
        if node.op is FilterOperator.NOT_IN:
            return filter_cls.not_(built)
        return built

    # FilterGroup
    built = [build_filter_node(op, filter_cls) for op in node.operands]

    if node.op == LogicalOperator.AND:
        return filter_cls.all_of(built)
    elif node.op == LogicalOperator.OR:
        return filter_cls.any_of(built)
    else:  # NOT
        inner = filter_cls.all_of(built) if len(built) > 1 else built[0]
        return filter_cls.not_(inner)
