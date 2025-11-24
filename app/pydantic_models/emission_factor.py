"""
Pydantic models for EmissionFactor following kkb_fastapi pattern.
"""
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class EmissionFactorBase(BaseModel):
    """Base emission factor model."""

    activity_type: str = Field(..., max_length=100, description="Type of activity")
    lookup_identifier: str = Field(..., max_length=200, description="Lookup identifier for matching")
    unit: str = Field(..., max_length=50, description="Unit of measurement")
    co2e_factor: Decimal = Field(..., description="CO2e emission factor value")
    scope: int = Field(..., ge=1, le=3, description="GHG Protocol scope (1, 2, or 3)")
    category: int | None = Field(None, description="GHG Protocol Scope 3 category")
    source: str | None = Field(None, max_length=200, description="Source of emission factor")
    notes: str | None = Field(None, description="Additional notes")


class EmissionFactorCreate(EmissionFactorBase):
    """Model for creating emission factor."""


class EmissionFactorUpdate(BaseModel):
    """Model for updating emission factor."""

    activity_type: str | None = Field(None, max_length=100)
    lookup_identifier: str | None = Field(None, max_length=200)
    unit: str | None = Field(None, max_length=50)
    co2e_factor: Decimal | None = None
    scope: int | None = Field(None, ge=1, le=3)
    category: int | None = None
    source: str | None = Field(None, max_length=200)
    notes: str | None = None


class EmissionFactorPydModel(EmissionFactorBase):
    """Model for emission factor response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime
    updated_at: datetime
