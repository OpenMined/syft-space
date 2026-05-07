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


class CurrencyAmount(BaseModel):
    """A monetary amount in a specific currency.

    Revenue is reported per-currency rather than as a single sum because
    Syft Space supports multiple wallet types (xendit/IDR, mpp/USD) and
    cross-currency totals are not meaningful without an FX rate.
    """

    currency: str = Field(..., description="ISO currency code (e.g., 'USD', 'IDR')")
    amount: float = Field(..., description="Amount in that currency")


class RevenueStatCard(BaseModel):
    """Revenue stat card with per-currency breakdowns.

    The frontend renders `breakdown` as the primary value and
    `change_breakdown` as the secondary comparison. Formatting is the
    frontend's responsibility because currency display rules vary.
    """

    breakdown: list[CurrencyAmount] = Field(
        ..., description="Revenue per currency for the selected period"
    )
    change_breakdown: list[CurrencyAmount] = Field(
        ..., description="Revenue per currency for the comparison window (this month)"
    )


class SummaryStatsResponse(BaseModel):
    """Response for the 4 dashboard stat cards."""

    active_endpoints: StatCard = Field(..., description="Count of published endpoints")
    total_queries: StatCard = Field(
        ..., description="Count of query events in selected range"
    )
    total_revenue: RevenueStatCard = Field(
        ..., description="Per-currency revenue in selected range"
    )
    active_users: StatCard = Field(
        ..., description="Count of distinct users in selected range"
    )


# ============== Time Series ==============


class TimeSeriesPoint(BaseModel):
    """A single data point in a time series."""

    label: str = Field(..., description="Human-readable bucket label")
    value: float = Field(..., description="Aggregated value for this bucket")


class CurrencySeries(BaseModel):
    """A revenue time series in a single currency.

    All series in a TimeSeriesResponse share the same x-axis labels so the
    frontend can stack/overlay them without re-aligning buckets.
    """

    currency: str = Field(..., description="ISO currency code")
    points: list[TimeSeriesPoint] = Field(
        ..., description="Revenue per time bucket for this currency"
    )


class TimeSeriesResponse(BaseModel):
    """Response containing 3 time-bucketed series."""

    query_volume: list[TimeSeriesPoint] = Field(
        ..., description="Query count per time bucket"
    )
    user_activity: list[TimeSeriesPoint] = Field(
        ..., description="Distinct user count per time bucket"
    )
    revenue: list[CurrencySeries] = Field(
        ...,
        description=(
            "Revenue per currency, one series per currency present in the data. "
            "Empty list when there is no revenue in the period."
        ),
    )


# ============== Top Users ==============


class TopUserEntry(BaseModel):
    """A single user entry in the top users list."""

    user_email: str = Field(..., description="User email address")
    query_count: int = Field(..., description="Number of queries in the time range")
    revenue: list[CurrencyAmount] = Field(
        ...,
        description=(
            "Revenue from this user's queries, broken down by currency. "
            "Empty list if the user only triggered free or refunded queries."
        ),
    )


class TopUsersResponse(BaseModel):
    """Response containing the ranked list of top users."""

    users: list[TopUserEntry] = Field(
        ..., description="Top users sorted by query count descending"
    )


# ============== Word Cloud ==============


class WordCloudEntry(BaseModel):
    """A single word with its frequency weight."""

    word: str = Field(..., description="Cleaned, lemmatized word")
    count: int = Field(..., description="Frequency count across matched queries")


class WordCloudResponse(BaseModel):
    """Response containing word frequency data for cloud rendering."""

    words: list[WordCloudEntry] = Field(
        ..., description="Words sorted by count descending"
    )
