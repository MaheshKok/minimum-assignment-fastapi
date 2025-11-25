"""
EmissionSummary SQLAlchemy model.

Pre-aggregated emission summaries for efficient querying.
Supports filtering by date range, scope, category, and activity type.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Column, Date, DateTime, Index, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class EmissionSummaryDBModel(Base):
    """
    Pre-aggregated emission summary table.

    Stores aggregated emissions by date range, scope, category, and activity type.
    This table is populated by aggregation jobs to enable fast querying without
    real-time joins on millions of emission results.

    Design:
    - Summaries are calculated periodically (daily/monthly)
    - Supports filtering by date range, scope, category, activity type
    - Indexed for fast lookups
    - Handles 1M+ activities per month efficiently
    """

    __tablename__ = "emission_summaries"

    __table_args__ = (
        # Composite index for common query patterns
        Index(
            "ix_emission_summaries_date_scope_category",
            "from_date",
            "to_date",
            "scope",
            "category",
        ),
        Index(
            "ix_emission_summaries_date_activity",
            "from_date",
            "to_date",
            "activity_type",
        ),
        Index(
            "ix_emission_summaries_scope_category_activity",
            "scope",
            "category",
            "activity_type",
        ),
        # Unique constraint to prevent duplicate summaries
        Index(
            "ix_emission_summaries_unique_period",
            "from_date",
            "to_date",
            "scope",
            "category",
            "activity_type",
            unique=True,
            postgresql_where="activity_type IS NOT NULL",
        ),
        {
            "comment": "Pre-aggregated emission summaries for efficient querying"
        },
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Date range for this summary
    from_date = Column(
        Date,
        nullable=False,
        index=True,
        comment="Start date of the summary period (inclusive)",
    )

    to_date = Column(
        Date,
        nullable=False,
        index=True,
        comment="End date of the summary period (inclusive)",
    )

    # Aggregation dimensions (nullable for rollups)
    scope = Column(
        Integer,
        nullable=True,
        index=True,
        comment="GHG Protocol scope (2 or 3) - NULL for all scopes",
    )

    category = Column(
        Integer,
        nullable=True,
        index=True,
        comment="Scope 3 category (1 or 6) - NULL for all categories",
    )

    activity_type = Column(
        String(100),
        nullable=True,
        index=True,
        comment="Activity type - NULL for all activity types",
    )

    # Aggregated metrics
    total_co2e_tonnes = Column(
        Numeric(15, 7),
        nullable=False,
        default=Decimal("0"),
        comment="Total CO2e emissions in tonnes for this summary",
    )

    activity_count = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of individual activities included in this summary",
    )

    # Summary metadata
    summary_type = Column(
        String(50),
        nullable=False,
        default="daily",
        comment="Type of summary: daily, weekly, monthly, yearly, custom",
    )

    calculation_metadata = Column(
        String,
        nullable=True,
        comment="Additional metadata about the aggregation calculation",
    )

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    def __repr__(self):
        return (
            f"<EmissionSummaryDBModel: {self.from_date} to {self.to_date}, "
            f"scope={self.scope}, category={self.category}, "
            f"activity={self.activity_type}, CO2e={self.total_co2e_tonnes}>"
        )
