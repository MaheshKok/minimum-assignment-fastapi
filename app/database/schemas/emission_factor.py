"""
EmissionFactor SQLAlchemy model.

Converted from Django ORM to SQLAlchemy async following kkb_fastapi pattern.
"""
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Column, DateTime, Integer, Numeric, String, Index
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class EmissionFactorDBModel(Base):
    """
    Emission factor lookup table.

    Maps activity types and lookup identifiers to CO2e emission factors.
    Based on standard emission factor databases (e.g., DEFRA, EPA).
    """

    __tablename__ = "emission_factors"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    activity_type = Column(
        String(100),
        nullable=False,
        index=True,
        comment="Type of activity this emission factor applies to",
    )

    lookup_identifier = Column(
        String(200),
        nullable=False,
        index=True,
        comment="Identifier used to match activity data (e.g., 'United Kingdom', 'Long-haul, Business class')",
    )

    unit = Column(
        String(50),
        nullable=False,
        comment="Unit of measurement (e.g., kWh, GBP, kilometres)",
    )

    co2e_factor = Column(
        Numeric(10, 6),
        nullable=False,
        comment="CO2e emission factor value (kgCO2e per unit)",
    )

    scope = Column(
        Integer,
        nullable=False,
        comment="GHG Protocol scope (1, 2, or 3)",
    )

    category = Column(
        Integer,
        nullable=True,
        comment="GHG Protocol Scope 3 category number (for Scope 3 only)",
    )

    source = Column(
        String(200),
        nullable=True,
        comment="Source of the emission factor (e.g., 'DEFRA 2024', 'EPA 2023')",
    )

    notes = Column(
        String,
        nullable=True,
        comment="Additional notes or context about this emission factor",
    )

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_emission_factors_activity_scope", "activity_type", "scope"),
        Index("ix_emission_factors_activity_lookup", "activity_type", "lookup_identifier"),
        {"comment": "Emission factor lookup table for CO2e calculations"},
    )

    def __repr__(self):
        return f"<EmissionFactorDBModel: {self.activity_type} - {self.lookup_identifier}>"
