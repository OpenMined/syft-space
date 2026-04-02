"""Analytics API request/response schemas."""

from enum import Enum

from pydantic import BaseModel, Field


class TimeRange(str, Enum):
    """Predefined time ranges for analytics queries."""

    SEVEN_DAYS = "7d"
    THIRTY_DAYS = "30d"
    NINETY_DAYS = "90d"
    ONE_YEAR = "1y"


# ============== Summary Statistics ==============


class StatCard(BaseModel):
    """A single stat card with value and comparison indicator."""

    value: float = Field(..., description="Raw numeric value")
    change_value: float = Field(
        ..., description="Raw comparison value (count, percentage, or amount)"
    )
    change_label: str = Field(
        ...,
        description="Pre-formatted comparison text (e.g., '+2 this period')",
    )


class SummaryStatsResponse(BaseModel):
    """Response for the 4 dashboard stat cards."""

    active_endpoints: StatCard = Field(..., description="Count of published endpoints")
    total_queries: StatCard = Field(
        ..., description="Count of query events in selected range"
    )
    total_revenue: StatCard = Field(..., description="Sum of revenue in selected range")
    active_users: StatCard = Field(
        ..., description="Count of distinct users in selected range"
    )


# ============== Time Series ==============


class TimeSeriesPoint(BaseModel):
    """A single data point in a time series."""

    label: str = Field(..., description="Human-readable bucket label")
    value: float = Field(..., description="Aggregated value for this bucket")


class TimeSeriesResponse(BaseModel):
    """Response containing 3 time-bucketed series."""

    query_volume: list[TimeSeriesPoint] = Field(
        ..., description="Query count per time bucket"
    )
    user_activity: list[TimeSeriesPoint] = Field(
        ..., description="Distinct user count per time bucket"
    )
    revenue: list[TimeSeriesPoint] = Field(
        ..., description="Revenue sum per time bucket"
    )


# ============== Top Users ==============


class TopUserEntry(BaseModel):
    """A single user entry in the top users list."""

    user_email: str = Field(..., description="User email address")
    query_count: int = Field(..., description="Number of queries in the time range")
    revenue: float = Field(..., description="Sum of revenue from this user's queries")


class TopUsersResponse(BaseModel):
    """Response containing the ranked list of top users."""

    users: list[TopUserEntry] = Field(
        ..., description="Top users sorted by query count descending"
    )
