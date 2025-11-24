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

    activity_type: str = Field(..., max_length=100, description="Type of activity")
    activity_id: UUID = Field(..., description="ID of activity record")
    emission_factor_id: UUID = Field(..., description="ID of emission factor used")
    co2e_tonnes: Decimal = Field(..., ge=0, description="CO2e emissions in tonnes")
    confidence_score: Decimal = Field(Decimal("1.0"), ge=0, le=1, description="Matching confidence score")
    calculation_metadata: dict[str, Any] | None = Field(default_factory=dict, description="Calculation metadata")
    calculation_date: DateType = Field(default_factory=DateType.today, description="Calculation date")


class EmissionResultCreate(EmissionResultBase):
    """Model for creating emission result."""


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

    activity_ids: list[UUID] = Field(..., description="List of activity IDs to calculate emissions for")
    recalculate: bool = Field(False, description="Whether to recalculate existing results")


class EmissionSummary(BaseModel):
    """Summary of emissions by scope and category."""

    total_co2e_tonnes: Decimal
    scope_2_tonnes: Decimal
    scope_3_tonnes: Decimal
    scope_3_category_1_tonnes: Decimal  # Purchased Goods and Services
    scope_3_category_6_tonnes: Decimal  # Business Travel
    total_activities: int
    calculation_date: DateType


class EmissionReportResponse(BaseModel):
    """Comprehensive emission report response."""

    summary: EmissionSummary
    results: list[EmissionResultPydModel]
    breakdown_by_activity_type: dict[str, Decimal]
