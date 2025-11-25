"""
Pydantic models for Emission Summaries.

Pre-aggregated emission summary models for efficient querying.
"""

from datetime import date as DateType
from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class EmissionSummaryBase(BaseModel):
    """Base emission summary model."""

    from_date: DateType = Field(
        ...,
        description="Start date of the summary period (inclusive)",
        examples=["2025-11-01"]
    )
    to_date: DateType = Field(
        ...,
        description="End date of the summary period (inclusive)",
        examples=["2025-11-30"]
    )
    scope: Optional[int] = Field(
        None,
        description="GHG Protocol scope (2 or 3) - NULL for all scopes",
        examples=[2]
    )
    category: Optional[int] = Field(
        None,
        description="Scope 3 category (1 or 6) - NULL for all categories",
        examples=[1]
    )
    activity_type: Optional[str] = Field(
        None,
        description="Activity type - NULL for all activity types",
        examples=["Electricity"]
    )
    total_co2e_tonnes: Decimal = Field(
        ...,
        description="Total CO2e emissions in tonnes for this summary",
        examples=[Decimal("1247.5893")]
    )
    activity_count: int = Field(
        ...,
        description="Number of individual activities included in this summary",
        examples=[1542]
    )
    summary_type: str = Field(
        ...,
        description="Type of summary: daily, weekly, monthly, yearly, custom",
        examples=["monthly"]
    )


class EmissionSummaryPydModel(EmissionSummaryBase):
    """Model for emission summary response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    calculation_metadata: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class EmissionSummaryCreate(EmissionSummaryBase):
    """Model for creating emission summaries."""

    pass


class AggregationRequest(BaseModel):
    """Request model for triggering emission aggregation."""

    aggregation_type: str = Field(
        ...,
        description="Type of aggregation: daily, monthly, custom",
        examples=["monthly"]
    )
    target_date: Optional[DateType] = Field(
        None,
        description="Target date for daily aggregation",
        examples=["2025-11-25"]
    )
    year: Optional[int] = Field(
        None,
        description="Year for monthly aggregation",
        examples=[2025]
    )
    month: Optional[int] = Field(
        None,
        description="Month for monthly aggregation (1-12)",
        examples=[11]
    )
    from_date: Optional[DateType] = Field(
        None,
        description="Start date for custom range aggregation",
        examples=["2025-11-01"]
    )
    to_date: Optional[DateType] = Field(
        None,
        description="End date for custom range aggregation",
        examples=["2025-11-30"]
    )


class AggregationResponse(BaseModel):
    """Response model for aggregation operations."""

    success: bool = Field(..., description="Whether the aggregation was successful")
    message: str = Field(..., description="Status message")
    summaries_created: int = Field(
        ...,
        description="Number of summaries created or updated"
    )
    summaries: list[EmissionSummaryPydModel] = Field(
        ...,
        description="List of created/updated summaries"
    )
