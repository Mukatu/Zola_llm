"""PAIE-6b : rubriques de paie paramétrables appliquées au bulletin

Revision ID: 20260629_0027
Revises: 20260629_0026
Create Date: 2026-06-29
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260629_0027"
down_revision: str | None = "20260629_0026"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "store_payslips",
        sa.Column("rubriques", sa.JSON, nullable=False, server_default="{}"),
    )


def downgrade() -> None:
    op.drop_column("store_payslips", "rubriques")
