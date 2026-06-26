"""Pilotage Achats : budgets d'achats par direction et exercice

Revision ID: 20260626_0016
Revises: 20260626_0015
Create Date: 2026-06-26
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260626_0016"
down_revision: str | None = "20260626_0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "store_purchase_budgets",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("direction", sa.String(40), nullable=False),
        sa.Column("exercice", sa.String(8), nullable=False),
        sa.Column("budget_xaf", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("country", sa.String(2), nullable=False, server_default="cg"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_store_purchase_budgets_tenant_id", "store_purchase_budgets", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("ix_store_purchase_budgets_tenant_id", table_name="store_purchase_budgets")
    op.drop_table("store_purchase_budgets")
