"""create_emission_factors_table

Revision ID: 02010423781e
Revises:
Create Date: 2025-11-24 12:01:39.505091

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "02010423781e"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "emission_factors",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "activity_type",
            sa.String(length=100),
            nullable=False,
            comment="Type of activity this emission factor applies to",
        ),
        sa.Column(
            "lookup_identifier",
            sa.String(length=200),
            nullable=False,
            comment=(
                "Identifier used to match activity data "
                "(e.g., 'United Kingdom', 'Long-haul, Business class')"
            ),
        ),
        sa.Column(
            "unit",
            sa.String(length=50),
            nullable=False,
            comment="Unit of measurement (e.g., kWh, GBP, kilometres)",
        ),
        sa.Column(
            "co2e_factor",
            sa.Numeric(precision=10, scale=6),
            nullable=False,
            comment="CO2e emission factor value (kgCO2e per unit)",
        ),
        sa.Column(
            "scope",
            sa.Integer(),
            nullable=False,
            comment="GHG Protocol scope (1, 2, or 3)",
        ),
        sa.Column(
            "category",
            sa.Integer(),
            nullable=True,
            comment="GHG Protocol Scope 3 category number (for Scope 3 only)",
        ),
        sa.Column(
            "source",
            sa.String(length=200),
            nullable=True,
            comment="Source of the emission factor (e.g., 'DEFRA 2024', 'EPA 2023')",
        ),
        sa.Column(
            "notes",
            sa.String(),
            nullable=True,
            comment="Additional notes or context about this emission factor",
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        comment="Emission factor lookup table for CO2e calculations",
    )
    op.create_index(
        op.f("ix_emission_factors_activity_type"),
        "emission_factors",
        ["activity_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_emission_factors_lookup_identifier"),
        "emission_factors",
        ["lookup_identifier"],
        unique=False,
    )
    op.create_index(
        "ix_emission_factors_activity_scope",
        "emission_factors",
        ["activity_type", "scope"],
        unique=False,
    )
    op.create_index(
        "ix_emission_factors_activity_lookup",
        "emission_factors",
        ["activity_type", "lookup_identifier"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_emission_factors_activity_lookup", table_name="emission_factors")
    op.drop_index("ix_emission_factors_activity_scope", table_name="emission_factors")
    op.drop_index(op.f("ix_emission_factors_lookup_identifier"), table_name="emission_factors")
    op.drop_index(op.f("ix_emission_factors_activity_type"), table_name="emission_factors")
    op.drop_table("emission_factors")
