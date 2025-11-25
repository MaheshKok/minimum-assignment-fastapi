"""create_emission_summaries_table

Revision ID: b7c8d9e0f1a2
Revises: a1b2c3d4e5f6
Create Date: 2025-11-25 02:08:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "b7c8d9e0f1a2"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "emission_summaries",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "from_date",
            sa.Date(),
            nullable=False,
            comment="Start date of the summary period (inclusive)",
        ),
        sa.Column(
            "to_date",
            sa.Date(),
            nullable=False,
            comment="End date of the summary period (inclusive)",
        ),
        sa.Column(
            "scope",
            sa.Integer(),
            nullable=True,
            comment="GHG Protocol scope (2 or 3) - NULL for all scopes",
        ),
        sa.Column(
            "category",
            sa.Integer(),
            nullable=True,
            comment="Scope 3 category (1 or 6) - NULL for all categories",
        ),
        sa.Column(
            "activity_type",
            sa.String(length=100),
            nullable=True,
            comment="Activity type - NULL for all activity types",
        ),
        sa.Column(
            "total_co2e_tonnes",
            sa.Numeric(precision=15, scale=7),
            nullable=False,
            comment="Total CO2e emissions in tonnes for this summary",
        ),
        sa.Column(
            "activity_count",
            sa.Integer(),
            nullable=False,
            comment="Number of individual activities included in this summary",
        ),
        sa.Column(
            "summary_type",
            sa.String(length=50),
            nullable=False,
            comment="Type of summary: daily, weekly, monthly, yearly, custom",
        ),
        sa.Column(
            "calculation_metadata",
            sa.String(),
            nullable=True,
            comment="Additional metadata about the aggregation calculation",
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        comment="Pre-aggregated emission summaries for efficient querying",
    )

    # Create indexes for efficient querying
    op.create_index(
        "ix_emission_summaries_from_date",
        "emission_summaries",
        ["from_date"],
        unique=False,
    )
    op.create_index(
        "ix_emission_summaries_to_date",
        "emission_summaries",
        ["to_date"],
        unique=False,
    )
    op.create_index(
        "ix_emission_summaries_scope",
        "emission_summaries",
        ["scope"],
        unique=False,
    )
    op.create_index(
        "ix_emission_summaries_category",
        "emission_summaries",
        ["category"],
        unique=False,
    )
    op.create_index(
        "ix_emission_summaries_activity_type",
        "emission_summaries",
        ["activity_type"],
        unique=False,
    )

    # Composite indexes for common query patterns
    op.create_index(
        "ix_emission_summaries_date_scope_category",
        "emission_summaries",
        ["from_date", "to_date", "scope", "category"],
        unique=False,
    )
    op.create_index(
        "ix_emission_summaries_date_activity",
        "emission_summaries",
        ["from_date", "to_date", "activity_type"],
        unique=False,
    )
    op.create_index(
        "ix_emission_summaries_scope_category_activity",
        "emission_summaries",
        ["scope", "category", "activity_type"],
        unique=False,
    )

    # Unique constraint to prevent duplicate summaries
    op.create_index(
        "ix_emission_summaries_unique_period",
        "emission_summaries",
        ["from_date", "to_date", "scope", "category", "activity_type"],
        unique=True,
        postgresql_where=sa.text("activity_type IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "ix_emission_summaries_unique_period", table_name="emission_summaries"
    )
    op.drop_index(
        "ix_emission_summaries_scope_category_activity",
        table_name="emission_summaries",
    )
    op.drop_index(
        "ix_emission_summaries_date_activity", table_name="emission_summaries"
    )
    op.drop_index(
        "ix_emission_summaries_date_scope_category", table_name="emission_summaries"
    )
    op.drop_index(
        "ix_emission_summaries_activity_type", table_name="emission_summaries"
    )
    op.drop_index("ix_emission_summaries_category", table_name="emission_summaries")
    op.drop_index("ix_emission_summaries_scope", table_name="emission_summaries")
    op.drop_index("ix_emission_summaries_to_date", table_name="emission_summaries")
    op.drop_index("ix_emission_summaries_from_date", table_name="emission_summaries")
    op.drop_table("emission_summaries")
