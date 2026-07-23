"""scan queue columns: domains + job_id

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-22
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("scans", sa.Column("job_id", sa.String(), nullable=True))
    op.add_column(
        "scans",
        sa.Column("domains", postgresql.JSONB(), nullable=False, server_default="[]"),
    )


def downgrade() -> None:
    op.drop_column("scans", "domains")
    op.drop_column("scans", "job_id")
