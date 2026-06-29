"""PAIE-6c : affectation de rubriques de paie par salarié

Revision ID: 20260629_0028
Revises: 20260629_0027
Create Date: 2026-06-29
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260629_0028"
down_revision: str | None = "20260629_0027"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "store_employee_rubriques",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False, index=True),
        sa.Column("employee_matricule", sa.String(32), nullable=False, index=True),
        sa.Column("code", sa.String(40), nullable=False),
        sa.Column("valeur", sa.Numeric(18, 2), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("store_employee_rubriques")
