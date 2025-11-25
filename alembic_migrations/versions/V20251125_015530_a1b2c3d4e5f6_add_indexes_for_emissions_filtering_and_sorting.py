"""add_indexes_for_emissions_filtering_and_sorting

Revision ID: a1b2c3d4e5f6
Revises: 2d0c56b37799
Create Date: 2025-11-25 01:55:30.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f6"
down_revision = "2d0c56b37799"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add index on emission_factors (scope, category) for filtering
    op.create_index(
        "ix_emission_factors_scope_category",
        "emission_factors",
        ["scope", "category"],
        unique=False,
    )

    # Add index on emission_results (co2e_tonnes) for sorting
    op.create_index(
        "ix_emission_results_co2e_tonnes",
        "emission_results",
        ["co2e_tonnes"],
        unique=False,
    )

    # Add index on emission_results (emission_factor_id) for joins
    op.create_index(
        "ix_emission_results_emission_factor_id",
        "emission_results",
        ["emission_factor_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_emission_results_emission_factor_id", table_name="emission_results")
    op.drop_index("ix_emission_results_co2e_tonnes", table_name="emission_results")
    op.drop_index("ix_emission_factors_scope_category", table_name="emission_factors")
