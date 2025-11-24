"""create_goods_services_activities_table

Revision ID: 39ba91f95107
Revises: 787e683ffe9f
Create Date: 2025-11-24 12:01:47.762156

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "39ba91f95107"
down_revision = "787e683ffe9f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "goods_services_activities",
        sa.Column(
            "supplier_category",
            sa.String(length=200),
            nullable=False,
            comment="Industry or category of the supplier",
        ),
        sa.Column(
            "spend_gbp",
            sa.Numeric(precision=12, scale=2),
            nullable=False,
            comment="Amount spent in GBP",
        ),
        sa.Column(
            "description",
            sa.String(),
            nullable=True,
            comment="Additional description of the purchase",
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
        comment="Purchased goods and services activity data (Scope 3, Category 1)",
    )
    op.create_index(
        op.f("ix_goods_services_activities_date"),
        "goods_services_activities",
        ["date"],
        unique=False,
    )
    op.create_index(
        op.f("ix_goods_services_activities_supplier_category"),
        "goods_services_activities",
        ["supplier_category"],
        unique=False,
    )
    op.create_index(
        "ix_goods_services_activities_date_desc",
        "goods_services_activities",
        ["date"],
        unique=False,
    )
    op.create_index(
        "ix_goods_services_activities_date_category",
        "goods_services_activities",
        ["date", "supplier_category"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_goods_services_activities_date_category",
        table_name="goods_services_activities",
    )
    op.drop_index(
        "ix_goods_services_activities_date_desc",
        table_name="goods_services_activities",
    )
    op.drop_index(
        op.f("ix_goods_services_activities_supplier_category"),
        table_name="goods_services_activities",
    )
    op.drop_index(
        op.f("ix_goods_services_activities_date"),
        table_name="goods_services_activities",
    )
    op.drop_table("goods_services_activities")
