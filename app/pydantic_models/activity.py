"""
Pydantic models for Activity Data following kkb_fastapi pattern.
"""

import json
from datetime import date as DateType
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.database.schemas.activity_data import (
    AirTravelActivityDBModel,
    ElectricityActivityDBModel,
    GoodsServicesActivityDBModel,
)
from app.services.calculators.unit_converter import UnitConverter


def _column_max(model: type, name: str) -> Decimal:
    """Largest value a Numeric(precision, scale) column can store."""
    column_type = model.__table__.c[name].type
    whole_digits = column_type.precision - column_type.scale
    return Decimal(10) ** whole_digits - Decimal(10) ** -column_type.scale


class _StorableInPostgres(BaseModel):
    """Rejects values Postgres refuses, so callers get a 422 instead of a database 500."""

    @field_validator("*")
    @classmethod
    def _storable(cls, value: Any) -> Any:
        if isinstance(value, str) and "\x00" in value:
            raise ValueError("text must not contain NUL characters")
        if isinstance(value, dict):
            json.dumps(value, allow_nan=False)  # NaN and Infinity are not valid JSON
        return value


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


class ElectricityActivityCreate(_StorableInPostgres, ElectricityActivityBase):
    """Model for creating electricity activity."""

    usage_kwh: Decimal = Field(
        ..., ge=0, le=_column_max(ElectricityActivityDBModel, "usage_kwh")
    )


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


class GoodsServicesActivityCreate(_StorableInPostgres, GoodsServicesActivityBase):
    """Model for creating goods & services activity."""

    spend_gbp: Decimal = Field(
        ..., ge=0, le=_column_max(GoodsServicesActivityDBModel, "spend_gbp")
    )


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


class AirTravelActivityCreate(_StorableInPostgres):
    """Model for creating air travel activity."""

    date: DateType
    distance_miles: Decimal = Field(
        ..., ge=0, le=_column_max(AirTravelActivityDBModel, "distance_miles")
    )
    flight_range: str = Field(..., max_length=50)
    passenger_class: str = Field(..., max_length=50)
    source_file: str | None = Field(None, max_length=255)
    raw_data: dict[str, Any] | None = Field(default_factory=dict)

    # distance_km will be calculated automatically

    @field_validator("distance_miles")
    @classmethod
    def _km_fits(cls, miles: Decimal) -> Decimal:
        if UnitConverter.miles_to_km(miles) > _column_max(AirTravelActivityDBModel, "distance_km"):
            raise ValueError("distance is too large to store in kilometres")
        return miles


class AirTravelActivityPydModel(AirTravelActivityBase):
    """Model for air travel activity response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    activity_type: str
    is_deleted: bool
    created_at: datetime
    updated_at: datetime
