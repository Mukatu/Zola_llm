"""TRESO-3 : gouvernance trésorerie (validation décaissements + rapprochement)

Revision ID: 20260626_0019
Revises: 20260626_0018
Create Date: 2026-06-26
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260626_0019"
down_revision: str | None = "20260626_0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "store_cash_flows",
        sa.Column("niveau_validation", sa.String(8), nullable=False, server_default=""),
    )
    op.add_column(
        "store_cash_flows",
        sa.Column("rapproche", sa.Boolean, nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("store_cash_flows", "rapproche")
    op.drop_column("store_cash_flows", "niveau_validation")
