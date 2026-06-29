"""PAIE-5 : validation experte d'un barème de paie (lève le verrou)

Revision ID: 20260629_0025
Revises: 20260629_0024
Create Date: 2026-06-29
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260629_0025"
down_revision: str | None = "20260629_0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "store_payroll_validations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False, index=True),
        sa.Column("country", sa.String(2), nullable=False, server_default="cg"),
        sa.Column("version", sa.String(64), nullable=False),
        sa.Column("validated", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("validated_by", sa.String(120), nullable=False, server_default=""),
        sa.Column("note", sa.Text, nullable=False, server_default=""),
        sa.Column("validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("store_payroll_validations")
