"""create_air_travel_activities_table

Revision ID: 787e683ffe9f
Revises: c81de53709ac
Create Date: 2025-11-24 12:01:46.783122

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "787e683ffe9f"
down_revision = "c81de53709ac"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "air_travel_activities",
        sa.Column(
            "distance_miles",
            sa.Numeric(precision=10, scale=2),
            nullable=False,
            comment="Distance traveled in miles",
        ),
        sa.Column(
            "distance_km",
            sa.Numeric(precision=10, scale=2),
            nullable=False,
            comment="Distance traveled in kilometres (converted from miles)",
        ),
        sa.Column(
            "flight_range",
            sa.String(length=50),
            nullable=False,
            comment=("Flight range category " "(e.g., Short-haul, Long-haul, International)"),
        ),
        sa.Column(
            "passenger_class",
            sa.String(length=50),
            nullable=False,
            comment="Passenger class (e.g., Economy, Business, First)",
        ),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "date",
            sa.Date(),
            nullable=False,
            comment="Date when the activity occurred",
        ),
        sa.Column(
            "activity_type",
            sa.String(length=100),
            nullable=False,
            comment="Type of activity",
        ),
        sa.Column(
            "source_file",
            sa.String(length=255),
            nullable=True,
            comment="Original CSV filename if imported from file",
        ),
        sa.Column(
            "raw_data",
            sa.JSON(),
            nullable=True,
            comment="Original CSV row data for audit trail",
        ),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        comment="Air travel activity data (Scope 3, Category 6)",
    )
    op.create_index(
        op.f("ix_air_travel_activities_date"),
        "air_travel_activities",
        ["date"],
        unique=False,
    )
    op.create_index(
        op.f("ix_air_travel_activities_flight_range"),
        "air_travel_activities",
        ["flight_range"],
        unique=False,
    )
    op.create_index(
        "ix_air_travel_activities_date_desc",
        "air_travel_activities",
        ["date"],
        unique=False,
    )
    op.create_index(
        "ix_air_travel_activities_date_range",
        "air_travel_activities",
        ["date", "flight_range"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_air_travel_activities_date_range", table_name="air_travel_activities")
    op.drop_index("ix_air_travel_activities_date_desc", table_name="air_travel_activities")
    op.drop_index(
        op.f("ix_air_travel_activities_flight_range"),
        table_name="air_travel_activities",
    )
    op.drop_index(op.f("ix_air_travel_activities_date"), table_name="air_travel_activities")
    op.drop_table("air_travel_activities")
