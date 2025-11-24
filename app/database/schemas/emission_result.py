"""
EmissionResult SQLAlchemy model.

Converted from Django ORM to SQLAlchemy async following kkb_fastapi pattern.
Note: Django's GenericForeignKey is replaced with activity_type and activity_id fields.
"""
import uuid
from datetime import datetime, date
from decimal import Decimal

from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, Numeric, String, JSON, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class EmissionResultDBModel(Base):
    """
    Calculated emission result.

    Links activity data to emission factors and stores the calculated CO2e emissions.
    Uses activity_type and activity_id instead of Django's GenericForeignKey.
    """

    __tablename__ = "emission_results"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Reference to activity data (replaces Django GenericForeignKey)
    activity_type = Column(
        String(100),
        nullable=False,
        comment="Type of activity data (Electricity, Air Travel, Purchased Goods and Services)",
    )

    activity_id = Column(
        UUID(as_uuid=True),
        nullable=False,
        comment="ID of the specific activity record",
    )

    # Emission factor used for calculation
    emission_factor_id = Column(
        UUID(as_uuid=True),
        ForeignKey("emission_factors.id", ondelete="RESTRICT"),
        nullable=False,
        comment="Emission factor used in the calculation",
    )

    emission_factor = relationship("EmissionFactorDBModel", backref="emission_results")

    # Calculated emissions
    # Note: decimal_places=7 to preserve precision from emission factors
    # Some factors have 5-6 decimal places (e.g., 0.15573 kgCO2e/km)
    # and calculations can produce 7 decimal place results
    co2e_tonnes = Column(
        Numeric(15, 7),
        nullable=False,
        comment="Calculated CO2e emissions in tonnes",
    )

    # Matching confidence score
    confidence_score = Column(
        Numeric(3, 2),
        nullable=False,
        default=Decimal("1.0"),
        comment="Confidence score for emission factor matching (0.0 to 1.0)",
    )

    # Calculation metadata
    calculation_metadata = Column(
        JSON,
        nullable=True,
        default=dict,
        comment="Additional calculation details (method, intermediate values, etc.)",
    )

    calculation_date = Column(
        Date,
        nullable=False,
        default=date.today,
        comment="Date when the emission was calculated",
    )

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_emission_results_activity", "activity_type", "activity_id"),
        Index("ix_emission_results_created_desc", "created_at"),
        Index("ix_emission_results_calculation_date", "calculation_date"),
        {"comment": "Calculated emission results linking activities to emission factors"},
    )

    def __repr__(self):
        return f"<EmissionResultDBModel: {self.co2e_tonnes} tCO2e, confidence={self.confidence_score}>"

    @property
    def co2e_kg(self) -> Decimal:
        """Get emissions in kilograms."""
        return self.co2e_tonnes * Decimal("1000")
