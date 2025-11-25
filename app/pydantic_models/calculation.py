"""
Pydantic models for Emission Calculations and Results following kkb_fastapi pattern.
"""

from datetime import date as DateType
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class EmissionResultBase(BaseModel):
    """Base emission result model."""

    activity_type: str = Field(
        ...,
        max_length=100,
        description="Type of activity",
        examples=["Electricity"]
    )
    activity_id: UUID = Field(
        ...,
        description="ID of activity record",
        examples=["3fa85f64-5717-4562-b3fc-2c963f66afa6"]
    )
    emission_factor_id: UUID = Field(
        ...,
        description="ID of emission factor used",
        examples=["7b2c91f3-8a45-4d21-9e76-1f8d3c5a9b42"]
    )
    co2e_tonnes: Decimal = Field(
        ...,
        ge=0,
        description="CO2e emissions in tonnes",
        examples=[Decimal("125.4567")]
    )
    confidence_score: Decimal = Field(
        Decimal("1.0"),
        ge=0,
        le=1,
        description="Matching confidence score",
        examples=[Decimal("1.0")]
    )
    calculation_metadata: dict[str, Any] | None = Field(
        default_factory=dict,
        description="Calculation metadata",
        examples=[{"method": "direct_measurement", "source": "utility_bill"}]
    )
    calculation_date: DateType = Field(
        default_factory=DateType.today,
        description="Calculation date",
        examples=["2025-11-25"]
    )



class EmissionResultPydModel(EmissionResultBase):
    """Model for emission result response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime
    updated_at: datetime

    @property
    def co2e_kg(self) -> Decimal:
        """Get emissions in kilograms."""
        return self.co2e_tonnes * Decimal("1000")


class EmissionCalculationRequest(BaseModel):
    """Request model for calculating emissions."""

    activity_ids: list[UUID] = Field(
        ..., description="List of activity IDs to calculate emissions for"
    )
    recalculate: bool = Field(
        False, description="Whether to recalculate existing results"
    )


class EmissionSummary(BaseModel):
    """Summary of emissions by scope and category."""

    total_co2e_tonnes: Decimal = Field(
        ...,
        description="Total CO2e emissions in tonnes across all scopes",
        examples=[Decimal("373.1459")]
    )
    scope_2_tonnes: Decimal = Field(
        ...,
        description="Total CO2e emissions in tonnes for Scope 2 (purchased electricity)",
        examples=[Decimal("125.8934")]
    )
    scope_3_tonnes: Decimal = Field(
        ...,
        description="Total CO2e emissions in tonnes for Scope 3 (value chain)",
        examples=[Decimal("247.2525")]
    )
    scope_3_category_1_tonnes: Decimal = Field(
        ...,
        description="Scope 3 Category 1: Purchased Goods and Services (tonnes CO2e)",
        examples=[Decimal("187.6834")]
    )
    scope_3_category_6_tonnes: Decimal = Field(
        ...,
        description="Scope 3 Category 6: Business Travel (tonnes CO2e)",
        examples=[Decimal("59.5691")]
    )
    total_activities: int = Field(
        ...,
        description="Total number of activities included in the summary",
        examples=[42]
    )
    calculation_date: DateType = Field(
        ...,
        description="Date when the emissions were calculated",
        examples=["2025-11-25"]
    )


class EmissionReportResponse(BaseModel):
    """Comprehensive emission report response."""

    summary: EmissionSummary = Field(
        ...,
        description="Aggregated summary of emissions by scope and category"
    )
    results: list[EmissionResultPydModel] = Field(
        ...,
        description="Detailed list of individual emission calculation results"
    )
    breakdown_by_activity_type: dict[str, Decimal] = Field(
        ...,
        description="Emissions breakdown by activity type",
        examples=[{
            "electricity": Decimal("125.8934"),
            "goods_services": Decimal("187.6834"),
            "air_travel": Decimal("59.5691")
        }]
    )
