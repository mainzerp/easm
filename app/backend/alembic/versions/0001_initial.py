"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-07-22
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "settings",
        sa.Column("key", sa.String(), primary_key=True),
        sa.Column("value", postgresql.JSONB(), nullable=True),
    )
    op.create_table(
        "scans",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("date", sa.String(), nullable=False, unique=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="running"),
        sa.Column("triggered_by", sa.String(), nullable=False, server_default="manual"),
        sa.Column("target_desc", sa.String(), nullable=False, server_default=""),
        sa.Column("output_dir", sa.String(), nullable=False, server_default=""),
        sa.Column("error", sa.Text(), nullable=True),
    )
    op.create_index("ix_scans_date", "scans", ["date"])
    op.create_table(
        "assets",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "scan_id", sa.Integer(), sa.ForeignKey("scans.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("domain", sa.String(), nullable=False, server_default=""),
        sa.Column("host", sa.String(), nullable=False),
        sa.Column("ip", sa.String(), nullable=True),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("tech", sa.Text(), nullable=True),
        sa.Column("ports", sa.Text(), nullable=True),
    )
    op.create_index("ix_assets_scan_id", "assets", ["scan_id"])
    op.create_index("ix_assets_domain", "assets", ["domain"])
    op.create_table(
        "findings",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "scan_id", sa.Integer(), sa.ForeignKey("scans.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("domain", sa.String(), nullable=False, server_default=""),
        sa.Column("host", sa.String(), nullable=True),
        sa.Column("template", sa.String(), nullable=True),
        sa.Column("severity", sa.String(), nullable=False, server_default="info"),
        sa.Column("raw", sa.Text(), nullable=False),
        sa.Column("first_seen", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_findings_scan_id", "findings", ["scan_id"])
    op.create_index("ix_findings_domain", "findings", ["domain"])
    op.create_index("ix_findings_severity", "findings", ["severity"])


def downgrade() -> None:
    op.drop_table("findings")
    op.drop_table("assets")
    op.drop_table("scans")
    op.drop_table("settings")
