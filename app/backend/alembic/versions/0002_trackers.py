"""tracker tables + scans.nuclei_enabled

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-22
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "scans",
        sa.Column("nuclei_enabled", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.create_table(
        "asset_tracker",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("domain", sa.String(), nullable=False, server_default=""),
        sa.Column("host", sa.String(), nullable=False, unique=True),
        sa.Column("first_seen", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen", sa.DateTime(timezone=True), nullable=False),
        sa.Column("first_scan_id", sa.Integer(), nullable=False),
        sa.Column("last_scan_id", sa.Integer(), nullable=False),
    )
    op.create_index("ix_asset_tracker_domain", "asset_tracker", ["domain"])
    op.create_index("ix_asset_tracker_host", "asset_tracker", ["host"])
    op.create_table(
        "finding_tracker",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("domain", sa.String(), nullable=False, server_default=""),
        sa.Column("template", sa.String(), nullable=False),
        sa.Column("host", sa.String(), nullable=False),
        sa.Column("severity", sa.String(), nullable=False, server_default="info"),
        sa.Column("raw", sa.Text(), nullable=False),
        sa.Column("first_seen", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen", sa.DateTime(timezone=True), nullable=False),
        sa.Column("first_scan_id", sa.Integer(), nullable=False),
        sa.Column("last_scan_id", sa.Integer(), nullable=False),
        sa.Column("resolved", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("resolved_scan_id", sa.Integer(), nullable=True),
    )
    op.create_index("ix_finding_tracker_domain", "finding_tracker", ["domain"])
    op.create_index("ix_finding_tracker_severity", "finding_tracker", ["severity"])
    op.create_index("ix_finding_tracker_resolved", "finding_tracker", ["resolved"])


def downgrade() -> None:
    op.drop_table("finding_tracker")
    op.drop_table("asset_tracker")
    op.drop_column("scans", "nuclei_enabled")
