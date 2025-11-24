"""
Activity data SQLAlchemy models.

Converted from Django ORM to SQLAlchemy async following kkb_fastapi pattern.
"""

import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, Column, Date, DateTime, Index, Numeric, String
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class BaseActivityMixin:
    """
    Base mixin for all activity data models.

    Provides common fields for timestamps and soft delete.
    """

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    date = Column(
        Date,
        nullable=False,
        index=True,
        comment="Date when the activity occurred",
    )

    activity_type = Column(
        String(100),
        nullable=False,
        comment="Type of activity",
    )

    source_file = Column(
        String(255),
        nullable=True,
        comment="Original CSV filename if imported from file",
    )

    raw_data = Column(
        JSON,
        nullable=True,
        default=dict,
        comment="Original CSV row data for audit trail",
    )

    # Soft delete
    is_deleted = Column(Boolean, default=False, nullable=False)
    deleted_at = Column(DateTime, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class ElectricityActivityDBModel(Base, BaseActivityMixin):
    """
    Electricity usage activity data (Scope 2).

    Represents purchased electricity consumption.
    """

    __tablename__ = "electricity_activities"

    country = Column(
        String(100),
        nullable=False,
        index=True,
        comment="Country where electricity was consumed",
    )

    usage_kwh = Column(
        Numeric(12, 4),
        nullable=False,
        comment="Electricity consumption in kilowatt-hours",
    )

    __table_args__ = (
        Index("ix_electricity_activities_date_country", "date", "country"),
        Index("ix_electricity_activities_date_desc", "date"),
        {"comment": "Electricity consumption activity data (Scope 2)"},
    )

    def __repr__(self):
        return f"<ElectricityActivityDBModel: {self.country} - {self.usage_kwh} kWh on {self.date}>"


class GoodsServicesActivityDBModel(Base, BaseActivityMixin):
    """
    Purchased goods and services activity data (Scope 3, Category 1).

    Represents spending on goods and services from various industries.
    """

    __tablename__ = "goods_services_activities"

    supplier_category = Column(
        String(200),
        nullable=False,
        index=True,
        comment="Industry or category of the supplier",
    )

    spend_gbp = Column(
        Numeric(12, 2),
        nullable=False,
        comment="Amount spent in GBP",
    )

    description = Column(
        String,
        nullable=True,
        comment="Additional description of the purchase",
    )

    __table_args__ = (
        Index(
            "ix_goods_services_activities_date_category", "date", "supplier_category"
        ),
        Index("ix_goods_services_activities_date_desc", "date"),
        {"comment": "Purchased goods and services activity data (Scope 3, Category 1)"},
    )

    def __repr__(self):
        return (
            f"<GoodsServicesActivityDBModel: {self.supplier_category} - "
            f"£{self.spend_gbp} on {self.date}>"
        )


class AirTravelActivityDBModel(Base, BaseActivityMixin):
    """
    Air travel activity data (Scope 3, Category 6).

    Represents business travel by air.
    """

    __tablename__ = "air_travel_activities"

    distance_miles = Column(
        Numeric(10, 2),
        nullable=False,
        comment="Distance traveled in miles",
    )

    distance_km = Column(
        Numeric(10, 2),
        nullable=False,
        comment="Distance traveled in kilometres (converted from miles)",
    )

    flight_range = Column(
        String(50),
        nullable=False,
        index=True,
        comment="Flight range category (e.g., Short-haul, Long-haul, International)",
    )

    passenger_class = Column(
        String(50),
        nullable=False,
        comment="Passenger class (e.g., Economy, Business, First)",
    )

    __table_args__ = (
        Index("ix_air_travel_activities_date_range", "date", "flight_range"),
        Index("ix_air_travel_activities_date_desc", "date"),
        {"comment": "Air travel activity data (Scope 3, Category 6)"},
    )

    def __repr__(self):
        return (
            f"<AirTravelActivityDBModel: {self.flight_range} - "
            f"{self.passenger_class} ({self.distance_km} km) on {self.date}>"
        )
