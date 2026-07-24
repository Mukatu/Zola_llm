"""Multi-devise : traçabilité comptes/flux/projets (devise + montant + taux)

Revision ID: 20260724_0056
Revises: 20260724_0055
Create Date: 2026-07-24
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260724_0056"
down_revision: str | None = "20260724_0055"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "store_bank_accounts",
        sa.Column("solde_initial_devise", sa.Numeric(18, 2), nullable=True),
    )
    op.add_column(
        "store_bank_accounts", sa.Column("taux_applique", sa.Numeric(18, 6), nullable=True)
    )

    op.add_column(
        "store_cash_flows",
        sa.Column("devise", sa.String(3), nullable=False, server_default="XAF"),
    )
    op.add_column(
        "store_cash_flows", sa.Column("montant_devise", sa.Numeric(18, 2), nullable=True)
    )
    op.add_column(
        "store_cash_flows", sa.Column("taux_applique", sa.Numeric(18, 6), nullable=True)
    )

    op.add_column(
        "store_projects",
        sa.Column("budget_total_devise", sa.Numeric(18, 2), nullable=True),
    )
    op.add_column(
        "store_projects", sa.Column("taux_applique", sa.Numeric(18, 6), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("store_projects", "taux_applique")
    op.drop_column("store_projects", "budget_total_devise")
    op.drop_column("store_cash_flows", "taux_applique")
    op.drop_column("store_cash_flows", "montant_devise")
    op.drop_column("store_cash_flows", "devise")
    op.drop_column("store_bank_accounts", "taux_applique")
    op.drop_column("store_bank_accounts", "solde_initial_devise")
