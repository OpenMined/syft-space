"""Filter schemas and logic for Remote Weaviate dataset type."""

from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, Field, model_validator


class FilterOperator(str, Enum):
    """Comparison operators for property filters."""

    EQUAL = "eq"
    NOT_EQUAL = "ne"
    GREATER_THAN = "gt"
    GREATER_OR_EQUAL = "gte"
    LESS_THAN = "lt"
    LESS_OR_EQUAL = "lte"
    LIKE = "like"
    IS_NONE = "is_none"
    CONTAINS_ANY = "contains_any"
    CONTAINS_ALL = "contains_all"


class FilterValueDtype(str, Enum):
    """Value type categories for filter conditions (GA-style)."""

    STRING = "string"
    NUMERIC = "numeric"
    DATETIME = "datetime"
    BOOLEAN = "boolean"


class LogicalOperator(str, Enum):
    """Logical operators for combining filter conditions."""

    AND = "and"
    OR = "or"
    NOT = "not"


def _coerce_single_value(
    raw: Any, dtype: "FilterValueDtype"
) -> str | int | float | bool | datetime:
    """Coerce a single raw value to the target dtype."""
    if dtype == FilterValueDtype.STRING:
        return str(raw)
    elif dtype == FilterValueDtype.NUMERIC:
        s = str(raw).strip()
        if "." in s:
            return float(s)
        return int(s)
    elif dtype == FilterValueDtype.BOOLEAN:
        if isinstance(raw, bool):
            return raw
        s = str(raw).lower().strip()
        if s in ("true", "1", "yes"):
            return True
        if s in ("false", "0", "no"):
            return False
        raise ValueError(f"Cannot coerce '{raw}' to boolean")
    elif dtype == FilterValueDtype.DATETIME:
        if isinstance(raw, datetime):
            return raw
        s = str(raw).strip()
        dt = datetime.fromisoformat(s)
        # Ensure timezone-aware (Weaviate requires it); default to UTC
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    raise ValueError(f"Unknown dtype: {dtype}")


DTYPE_ALLOWED_OPERATORS: dict[FilterValueDtype, list[FilterOperator]] = {
    FilterValueDtype.STRING: [
        FilterOperator.EQUAL,
        FilterOperator.NOT_EQUAL,
        FilterOperator.LIKE,
        FilterOperator.CONTAINS_ANY,
        FilterOperator.CONTAINS_ALL,
        FilterOperator.IS_NONE,
    ],
    FilterValueDtype.NUMERIC: [
        FilterOperator.EQUAL,
        FilterOperator.NOT_EQUAL,
        FilterOperator.GREATER_THAN,
        FilterOperator.GREATER_OR_EQUAL,
        FilterOperator.LESS_THAN,
        FilterOperator.LESS_OR_EQUAL,
        FilterOperator.CONTAINS_ANY,
        FilterOperator.CONTAINS_ALL,
        FilterOperator.IS_NONE,
    ],
    FilterValueDtype.DATETIME: [
        FilterOperator.EQUAL,
        FilterOperator.NOT_EQUAL,
        FilterOperator.GREATER_THAN,
        FilterOperator.GREATER_OR_EQUAL,
        FilterOperator.LESS_THAN,
        FilterOperator.LESS_OR_EQUAL,
        FilterOperator.IS_NONE,
    ],
    FilterValueDtype.BOOLEAN: [
        FilterOperator.EQUAL,
        FilterOperator.NOT_EQUAL,
        FilterOperator.IS_NONE,
    ],
}


class FilterCondition(BaseModel):
    """A single property filter condition."""

    type: Literal["condition"] = "condition"
    property: str = Field(..., description="Weaviate property name to filter on")
    op: FilterOperator = Field(..., description="Comparison operator")
    value_dtype: FilterValueDtype = Field(
        default=FilterValueDtype.STRING,
        description="Value type category: string, numeric, datetime, or boolean.",
    )
    value: str | int | float | bool | datetime | list[str | int | float | datetime] = (
        Field(
            ...,
            description="Value to compare against. Use a list for contains_any/contains_all.",
        )
    )

    @model_validator(mode="after")
    def validate_and_coerce(self) -> "FilterCondition":
        """Validate operator is allowed for the dtype and coerce value."""
        allowed_ops = DTYPE_ALLOWED_OPERATORS.get(self.value_dtype, [])
        if self.op not in allowed_ops:
            raise ValueError(
                f"operator '{self.op.value}' not allowed for dtype "
                f"'{self.value_dtype.value}'. Allowed: {[o.value for o in allowed_ops]}"
            )

        try:
            if self.op in (FilterOperator.CONTAINS_ANY, FilterOperator.CONTAINS_ALL):
                # Ensure value is a list; split comma-separated string if needed
                if isinstance(self.value, str):
                    items = [v.strip() for v in self.value.split(",") if v.strip()]
                elif isinstance(self.value, list):
                    items = self.value
                else:
                    items = [self.value]
                self.value = [_coerce_single_value(v, self.value_dtype) for v in items]
            else:
                self.value = _coerce_single_value(self.value, self.value_dtype)
        except (ValueError, TypeError) as e:
            raise ValueError(
                f"Cannot coerce value '{self.value}' to {self.value_dtype.value}: {e}"
            ) from e

        return self


class FilterGroup(BaseModel):
    """A group of conditions combined with a logical operator.

    Supports 1 level of nesting: operands can be conditions or sub-groups,
    but sub-groups can only contain conditions.
    """

    type: Literal["group"] = "group"
    op: LogicalOperator = Field(..., description="Logical operator to combine operands")
    operands: list[
        Annotated[Union[FilterCondition, "FilterGroup"], Field(discriminator="type")]
    ] = Field(..., description="Conditions or sub-groups to combine")

    @model_validator(mode="after")
    def validate_nesting_depth(self) -> "FilterGroup":
        """Ensure max 1 level of nesting."""
        for operand in self.operands:
            if isinstance(operand, FilterGroup):
                for inner in operand.operands:
                    if isinstance(inner, FilterGroup):
                        raise ValueError("Max 1 level of filter nesting allowed")
        return self


FilterGroup.model_rebuild()

WeaviateFilter = Annotated[FilterCondition | FilterGroup, Field(discriminator="type")]

OPERATOR_MAP: dict[FilterOperator, str] = {
    FilterOperator.EQUAL: "equal",
    FilterOperator.NOT_EQUAL: "not_equal",
    FilterOperator.GREATER_THAN: "greater_than",
    FilterOperator.GREATER_OR_EQUAL: "greater_or_equal",
    FilterOperator.LESS_THAN: "less_than",
    FilterOperator.LESS_OR_EQUAL: "less_or_equal",
    FilterOperator.LIKE: "like",
    FilterOperator.IS_NONE: "is_none",
    FilterOperator.CONTAINS_ANY: "contains_any",
    FilterOperator.CONTAINS_ALL: "contains_all",
}


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
        prop_filter = filter_cls.by_property(node.property)
        method = getattr(prop_filter, OPERATOR_MAP[node.op])
        return method(node.value)

    # FilterGroup
    built = [build_filter_node(op, filter_cls) for op in node.operands]

    if node.op == LogicalOperator.AND:
        return filter_cls.all_of(built)
    elif node.op == LogicalOperator.OR:
        return filter_cls.any_of(built)
    else:  # NOT
        inner = filter_cls.all_of(built) if len(built) > 1 else built[0]
        return filter_cls.not_(inner)
