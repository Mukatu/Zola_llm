"""Multi-devise : traçabilité des factures en devise (montant d'origine + taux)

Revision ID: 20260723_0051
Revises: 20260723_0050
Create Date: 2026-07-23
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260723_0051"
down_revision: str | None = "20260723_0050"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "store_invoices", sa.Column("montant_ht_devise", sa.Numeric(18, 2), nullable=True)
    )
    op.add_column(
        "store_invoices", sa.Column("montant_ttc_devise", sa.Numeric(18, 2), nullable=True)
    )
    op.add_column(
        "store_invoices", sa.Column("taux_applique", sa.Numeric(18, 6), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("store_invoices", "taux_applique")
    op.drop_column("store_invoices", "montant_ttc_devise")
    op.drop_column("store_invoices", "montant_ht_devise")
