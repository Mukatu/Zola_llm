"""PAIE-10 : archivage des bulletins (coffre-fort)

Revision ID: 20260701_0031
Revises: 20260629_0030
Create Date: 2026-07-01
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260701_0031"
down_revision: str | None = "20260629_0030"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "store_payslip_archives",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False, index=True),
        sa.Column("employee_matricule", sa.String(32), nullable=False, index=True),
        sa.Column("periode", sa.String(7), nullable=False, index=True),
        sa.Column("snapshot", sa.JSON, nullable=False),
        sa.Column("html", sa.Text, nullable=False, server_default=""),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("store_payslip_archives")
