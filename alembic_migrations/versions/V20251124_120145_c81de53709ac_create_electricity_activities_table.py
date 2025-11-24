"""create_electricity_activities_table

Revision ID: c81de53709ac
Revises: 02010423781e
Create Date: 2025-11-24 12:01:45.774299

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "c81de53709ac"
down_revision = "02010423781e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "electricity_activities",
        sa.Column(
            "country",
            sa.String(length=100),
            nullable=False,
            comment="Country where electricity was consumed",
        ),
        sa.Column(
            "usage_kwh",
            sa.Numeric(precision=12, scale=4),
            nullable=False,
            comment="Electricity consumption in kilowatt-hours",
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
        comment="Electricity consumption activity data (Scope 2)",
    )
    op.create_index(
        op.f("ix_electricity_activities_country"),
        "electricity_activities",
        ["country"],
        unique=False,
    )
    op.create_index(
        op.f("ix_electricity_activities_date"),
        "electricity_activities",
        ["date"],
        unique=False,
    )
    op.create_index(
        "ix_electricity_activities_date_country",
        "electricity_activities",
        ["date", "country"],
        unique=False,
    )
    op.create_index(
        "ix_electricity_activities_date_desc",
        "electricity_activities",
        ["date"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_electricity_activities_date_desc", table_name="electricity_activities")
    op.drop_index("ix_electricity_activities_date_country", table_name="electricity_activities")
    op.drop_index(op.f("ix_electricity_activities_date"), table_name="electricity_activities")
    op.drop_index(op.f("ix_electricity_activities_country"), table_name="electricity_activities")
    op.drop_table("electricity_activities")
