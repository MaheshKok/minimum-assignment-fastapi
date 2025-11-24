"""
Pydantic models for EmissionFactor following kkb_fastapi pattern.
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class EmissionFactorBase(BaseModel):
    """Base emission factor model."""

    activity_type: str = Field(..., max_length=100, description="Type of activity")
    lookup_identifier: str = Field(..., max_length=200, description="Lookup identifier for matching")
    unit: str = Field(..., max_length=50, description="Unit of measurement")
    co2e_factor: Decimal = Field(..., description="CO2e emission factor value")
    scope: int = Field(..., ge=1, le=3, description="GHG Protocol scope (1, 2, or 3)")
    category: Optional[int] = Field(None, description="GHG Protocol Scope 3 category")
    source: Optional[str] = Field(None, max_length=200, description="Source of emission factor")
    notes: Optional[str] = Field(None, description="Additional notes")


class EmissionFactorCreate(EmissionFactorBase):
    """Model for creating emission factor."""
    pass


class EmissionFactorUpdate(BaseModel):
    """Model for updating emission factor."""

    activity_type: Optional[str] = Field(None, max_length=100)
    lookup_identifier: Optional[str] = Field(None, max_length=200)
    unit: Optional[str] = Field(None, max_length=50)
    co2e_factor: Optional[Decimal] = None
    scope: Optional[int] = Field(None, ge=1, le=3)
    category: Optional[int] = None
    source: Optional[str] = Field(None, max_length=200)
    notes: Optional[str] = None


class EmissionFactorPydModel(EmissionFactorBase):
    """Model for emission factor response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime
    updated_at: datetime
