"""
Pydantic models for Activity Data following kkb_fastapi pattern.
"""

from datetime import date as DateType
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# Electricity Activity Models
class ElectricityActivityBase(BaseModel):
    """Base electricity activity model."""

    date: DateType = Field(..., description="Date of activity")
    country: str = Field(
        ..., max_length=100, description="Country where electricity was consumed"
    )
    usage_kwh: Decimal = Field(..., ge=0, description="Electricity consumption in kWh")
    source_file: str | None = Field(None, max_length=255, description="Source CSV file")
    raw_data: dict[str, Any] | None = Field(
        default_factory=dict, description="Raw CSV data"
    )


class ElectricityActivityCreate(ElectricityActivityBase):
    """Model for creating electricity activity."""


class ElectricityActivityPydModel(ElectricityActivityBase):
    """Model for electricity activity response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    activity_type: str
    is_deleted: bool
    created_at: datetime
    updated_at: datetime


# Goods & Services Activity Models
class GoodsServicesActivityBase(BaseModel):
    """Base goods & services activity model."""

    date: DateType = Field(..., description="Date of activity")
    supplier_category: str = Field(
        ..., max_length=200, description="Supplier industry/category"
    )
    spend_gbp: Decimal = Field(..., ge=0, description="Amount spent in GBP")
    description: str | None = Field(None, description="Purchase description")
    source_file: str | None = Field(None, max_length=255, description="Source CSV file")
    raw_data: dict[str, Any] | None = Field(
        default_factory=dict, description="Raw CSV data"
    )


class GoodsServicesActivityCreate(GoodsServicesActivityBase):
    """Model for creating goods & services activity."""


class GoodsServicesActivityPydModel(GoodsServicesActivityBase):
    """Model for goods & services activity response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    activity_type: str
    is_deleted: bool
    created_at: datetime
    updated_at: datetime


# Air Travel Activity Models
class AirTravelActivityBase(BaseModel):
    """Base air travel activity model."""

    date: DateType = Field(..., description="Date of activity")
    distance_miles: Decimal = Field(..., ge=0, description="Distance in miles")
    distance_km: Decimal = Field(..., ge=0, description="Distance in kilometres")
    flight_range: str = Field(
        ...,
        max_length=50,
        description="Flight range (Short-haul, Long-haul, etc.)",
    )
    passenger_class: str = Field(..., max_length=50, description="Passenger class")
    source_file: str | None = Field(None, max_length=255, description="Source CSV file")
    raw_data: dict[str, Any] | None = Field(
        default_factory=dict, description="Raw CSV data"
    )


class AirTravelActivityCreate(BaseModel):
    """Model for creating air travel activity."""

    date: DateType
    distance_miles: Decimal = Field(..., ge=0)
    flight_range: str = Field(..., max_length=50)
    passenger_class: str = Field(..., max_length=50)
    source_file: str | None = None
    raw_data: dict[str, Any] | None = Field(default_factory=dict)

    # distance_km will be calculated automatically


class AirTravelActivityPydModel(AirTravelActivityBase):
    """Model for air travel activity response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    activity_type: str
    is_deleted: bool
    created_at: datetime
    updated_at: datetime
