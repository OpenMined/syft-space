"""The one metadata filter model: an explicit tree of conditions and groups.

Used for an owner's locked filter in a store configuration and for the
filter a caller sends with a query. ``field`` is the canonical key;
``property`` is accepted for stored configurations and the current form.
A condition carries no ``value_dtype`` on the wire; the binding coerces by
the field's declared type. ``value_dtype`` stays optional for the owner's
configuration, where it is the coercion hint the form already sends.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, Any, Literal

from pydantic import AliasChoices, BaseModel, Field, model_validator

from syft_space.components.shared.metadata_types import MetadataField, MetadataType

__all__ = [
    "DTYPE_ALLOWED_OPERATORS",
    "MAX_CONDITIONS",
    "MAX_DEPTH",
    "MAX_LIST_VALUES",
    "WIRE_LOGIC",
    "WIRE_OPERATORS",
    "FieldFilterSpec",
    "FilterCondition",
    "FilterGroup",
    "FilterNode",
    "FilterOperator",
    "FilterValueDtype",
    "LogicalOperator",
    "condition_count",
    "depth",
    "dtype_for",
    "ops_for",
    "specs_for",
]

MAX_DEPTH = 5
MAX_CONDITIONS = 50
MAX_LIST_VALUES = 100


class FilterOperator(str, Enum):
    """Comparison operators for field filters."""

    EQUAL = "eq"
    NOT_EQUAL = "ne"
    GREATER_THAN = "gt"
    GREATER_OR_EQUAL = "gte"
    LESS_THAN = "lt"
    LESS_OR_EQUAL = "lte"
    IN = "in"
    NOT_IN = "nin"
    LIKE = "like"
    IS_NONE = "is_none"
    CONTAINS_ANY = "contains_any"
    CONTAINS_ALL = "contains_all"


class FilterValueDtype(str, Enum):
    """Coercion hint for a condition's value, as the owner's form sends it."""

    STRING = "string"
    NUMERIC = "numeric"
    DATETIME = "datetime"
    BOOLEAN = "boolean"


class LogicalOperator(str, Enum):
    """Logical operators for combining filter conditions."""

    AND = "and"
    OR = "or"
    NOT = "not"


# What a query may send. ``like``, ``is_none`` and ``not`` stay owner-only.
WIRE_OPERATORS: frozenset[FilterOperator] = frozenset(
    {
        FilterOperator.EQUAL,
        FilterOperator.NOT_EQUAL,
        FilterOperator.GREATER_THAN,
        FilterOperator.GREATER_OR_EQUAL,
        FilterOperator.LESS_THAN,
        FilterOperator.LESS_OR_EQUAL,
        FilterOperator.IN,
        FilterOperator.NOT_IN,
        FilterOperator.CONTAINS_ANY,
        FilterOperator.CONTAINS_ALL,
    }
)
WIRE_LOGIC: tuple[LogicalOperator, ...] = (LogicalOperator.AND, LogicalOperator.OR)

LIST_OPERATORS: frozenset[FilterOperator] = frozenset(
    {
        FilterOperator.IN,
        FilterOperator.NOT_IN,
        FilterOperator.CONTAINS_ANY,
        FilterOperator.CONTAINS_ALL,
    }
)

_COMPARISONS = (
    FilterOperator.EQUAL,
    FilterOperator.NOT_EQUAL,
    FilterOperator.GREATER_THAN,
    FilterOperator.GREATER_OR_EQUAL,
    FilterOperator.LESS_THAN,
    FilterOperator.LESS_OR_EQUAL,
)
_MEMBERSHIP = (FilterOperator.IN, FilterOperator.NOT_IN)
_CONTAINS = (FilterOperator.CONTAINS_ANY, FilterOperator.CONTAINS_ALL)

# Wire operators that make sense for a declared type.
_OPS_FOR_TYPE: dict[MetadataType, tuple[FilterOperator, ...]] = {
    MetadataType.STRING: (FilterOperator.EQUAL, FilterOperator.NOT_EQUAL, *_MEMBERSHIP),
    MetadataType.NUMBER: (*_COMPARISONS, *_MEMBERSHIP),
    MetadataType.BOOLEAN: (FilterOperator.EQUAL, FilterOperator.NOT_EQUAL),
    MetadataType.DATETIME: _COMPARISONS,
    MetadataType.STRING_LIST: _CONTAINS,
    MetadataType.NUMBER_LIST: _CONTAINS,
}

_DTYPE_FOR_TYPE: dict[MetadataType, FilterValueDtype] = {
    MetadataType.STRING: FilterValueDtype.STRING,
    MetadataType.NUMBER: FilterValueDtype.NUMERIC,
    MetadataType.BOOLEAN: FilterValueDtype.BOOLEAN,
    MetadataType.DATETIME: FilterValueDtype.DATETIME,
    MetadataType.STRING_LIST: FilterValueDtype.STRING,
    MetadataType.NUMBER_LIST: FilterValueDtype.NUMERIC,
}


def ops_for(type: MetadataType) -> tuple[FilterOperator, ...]:
    """The wire operators a field of this type supports, before any store cap."""
    return _OPS_FOR_TYPE[type]


def dtype_for(type: MetadataType) -> FilterValueDtype:
    """The coercion hint for values compared against a field of this type."""
    return _DTYPE_FOR_TYPE[type]


class FieldFilterSpec(BaseModel, frozen=True):
    """What a query may do with one field: its type and the operators."""

    type: MetadataType
    ops: tuple[FilterOperator, ...]


def specs_for(
    fields: tuple[MetadataField, ...], operators: frozenset[FilterOperator]
) -> dict[str, FieldFilterSpec]:
    """A spec per typed field: ``ops_for(type)`` cut to what the store can
    run. Untyped fields and fields left with no operator are dropped."""
    specs: dict[str, FieldFilterSpec] = {}
    for f in fields:
        if f.type is None:
            continue
        ops = tuple(op for op in ops_for(f.type) if op in operators)
        if ops:
            specs[f.name] = FieldFilterSpec(type=f.type, ops=ops)
    return specs


def _coerce_single_value(
    raw: Any, dtype: FilterValueDtype
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
        FilterOperator.IN,
        FilterOperator.NOT_IN,
        FilterOperator.LIKE,
        FilterOperator.CONTAINS_ANY,
        FilterOperator.CONTAINS_ALL,
        FilterOperator.IS_NONE,
    ],
    FilterValueDtype.NUMERIC: [
        *_COMPARISONS,
        FilterOperator.IN,
        FilterOperator.NOT_IN,
        FilterOperator.CONTAINS_ANY,
        FilterOperator.CONTAINS_ALL,
        FilterOperator.IS_NONE,
    ],
    FilterValueDtype.DATETIME: [
        *_COMPARISONS,
        FilterOperator.IN,
        FilterOperator.NOT_IN,
        FilterOperator.IS_NONE,
    ],
    FilterValueDtype.BOOLEAN: [
        FilterOperator.EQUAL,
        FilterOperator.NOT_EQUAL,
        FilterOperator.IN,
        FilterOperator.NOT_IN,
        FilterOperator.IS_NONE,
    ],
}


class FilterCondition(BaseModel):
    """A single field filter condition."""

    type: Literal["condition"] = "condition"
    field: str = Field(
        ...,
        validation_alias=AliasChoices("field", "property"),
        description="Metadata field to filter on",
    )
    op: FilterOperator = Field(..., description="Comparison operator")
    value_dtype: FilterValueDtype | None = Field(
        default=None,
        description=(
            "Coercion hint: string, numeric, datetime or boolean. Omitted on a "
            "query; the field's declared type decides."
        ),
    )
    value: str | int | float | bool | datetime | list[str | int | float | datetime] = (
        Field(
            ...,
            description="Value to compare against. A list for in/nin/contains_*.",
        )
    )

    @model_validator(mode="after")
    def validate_and_coerce(self) -> FilterCondition:
        """Cap list values; with a dtype, check the operator and coerce."""
        if isinstance(self.value, list) and len(self.value) > MAX_LIST_VALUES:
            raise ValueError(
                f"'{self.field}': at most {MAX_LIST_VALUES} values in a list"
            )
        if self.value_dtype is None:
            return self

        allowed_ops = DTYPE_ALLOWED_OPERATORS.get(self.value_dtype, [])
        if self.op not in allowed_ops:
            raise ValueError(
                f"operator '{self.op.value}' not allowed for dtype "
                f"'{self.value_dtype.value}'. Allowed: {[o.value for o in allowed_ops]}"
            )

        try:
            if self.op in LIST_OPERATORS:
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
    """Conditions or sub-groups combined with one logical operator.

    Nesting is bounded by ``MAX_DEPTH`` groups and ``MAX_CONDITIONS`` leaves
    over the whole tree.
    """

    type: Literal["group"] = "group"
    op: LogicalOperator = Field(..., description="Logical operator to combine operands")
    operands: list[
        Annotated[FilterCondition | FilterGroup, Field(discriminator="type")]
    ] = Field(..., min_length=1, description="Conditions or sub-groups to combine")

    @model_validator(mode="after")
    def validate_size(self) -> FilterGroup:
        if depth(self) > MAX_DEPTH:
            raise ValueError(f"filter nests deeper than {MAX_DEPTH} groups")
        if condition_count(self) > MAX_CONDITIONS:
            raise ValueError(f"filter has more than {MAX_CONDITIONS} conditions")
        return self


FilterGroup.model_rebuild()

FilterNode = Annotated[FilterCondition | FilterGroup, Field(discriminator="type")]


def depth(node: FilterCondition | FilterGroup) -> int:
    """Groups on the longest path: a bare condition is 0, a flat group 1."""
    if isinstance(node, FilterCondition):
        return 0
    return 1 + max(depth(o) for o in node.operands)


def condition_count(node: FilterCondition | FilterGroup) -> int:
    """Conditions in the whole tree."""
    if isinstance(node, FilterCondition):
        return 1
    return sum(condition_count(o) for o in node.operands)
