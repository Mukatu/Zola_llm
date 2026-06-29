"""PAIE-3e : rubriques déclaratives secondaires DAS 1 sur le bulletin

Revision ID: 20260629_0024
Revises: 20260626_0023
Create Date: 2026-06-29
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260629_0024"
down_revision: str | None = "20260626_0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "store_payslips",
        sa.Column("avantages_nature_xaf", sa.Numeric(18, 2), nullable=False, server_default="0"),
    )
    op.add_column(
        "store_payslips",
        sa.Column(
            "indemnites_non_imposables_xaf", sa.Numeric(18, 2), nullable=False, server_default="0"
        ),
    )


def downgrade() -> None:
    op.drop_column("store_payslips", "indemnites_non_imposables_xaf")
    op.drop_column("store_payslips", "avantages_nature_xaf")
