"""create_emission_results_table

Revision ID: 2d0c56b37799
Revises: 39ba91f95107
Create Date: 2025-11-24 12:01:48.190980

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "2d0c56b37799"
down_revision = "39ba91f95107"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "emission_results",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "activity_type",
            sa.String(length=100),
            nullable=False,
            comment=(
                "Type of activity data " "(Electricity, Air Travel, Purchased Goods and Services)"
            ),
        ),
        sa.Column(
            "activity_id",
            sa.UUID(),
            nullable=False,
            comment="ID of the specific activity record",
        ),
        sa.Column(
            "emission_factor_id",
            sa.UUID(),
            nullable=False,
            comment="Emission factor used in the calculation",
        ),
        sa.Column(
            "co2e_tonnes",
            sa.Numeric(precision=15, scale=7),
            nullable=False,
            comment="Calculated CO2e emissions in tonnes",
        ),
        sa.Column(
            "confidence_score",
            sa.Numeric(precision=3, scale=2),
            nullable=False,
            comment="Confidence score for emission factor matching (0.0 to 1.0)",
        ),
        sa.Column(
            "calculation_metadata",
            sa.JSON(),
            nullable=True,
            comment="Additional calculation details (method, intermediate values, etc.)",
        ),
        sa.Column(
            "calculation_date",
            sa.Date(),
            nullable=False,
            comment="Date when the emission was calculated",
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["emission_factor_id"], ["emission_factors.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        comment="Calculated emission results linking activities to emission factors",
    )
    op.create_index(
        "ix_emission_results_activity",
        "emission_results",
        ["activity_type", "activity_id"],
        unique=False,
    )
    op.create_index(
        "ix_emission_results_calculation_date",
        "emission_results",
        ["calculation_date"],
        unique=False,
    )
    op.create_index(
        "ix_emission_results_created_desc",
        "emission_results",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_emission_results_created_desc", table_name="emission_results")
    op.drop_index("ix_emission_results_calculation_date", table_name="emission_results")
    op.drop_index("ix_emission_results_activity", table_name="emission_results")
    op.drop_table("emission_results")
