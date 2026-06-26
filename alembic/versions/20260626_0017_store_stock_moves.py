"""STOCK-1 : mouvements de stock (grand-livre valorisé) + PMP sur l'article

Revision ID: 20260626_0017
Revises: 20260626_0016
Create Date: 2026-06-26
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260626_0017"
down_revision: str | None = "20260626_0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "store_stock_items",
        sa.Column("pmp_xaf", sa.Numeric(18, 2), nullable=False, server_default="0"),
    )
    op.create_table(
        "store_stock_moves",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("reference", sa.String(64), nullable=False),
        sa.Column("type", sa.String(12), nullable=False, server_default="entree"),
        sa.Column("sku", sa.String(64), nullable=False),
        sa.Column("quantite", sa.Numeric(18, 3), nullable=False, server_default="0"),
        sa.Column("cout_unitaire_xaf", sa.Numeric(18, 2), nullable=True),
        sa.Column("valeur_xaf", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("emplacement", sa.String(64), nullable=True),
        sa.Column("emplacement_dest", sa.String(64), nullable=True),
        sa.Column("lot", sa.String(64), nullable=True),
        sa.Column("date_peremption", sa.Date, nullable=True),
        sa.Column("statut", sa.String(12), nullable=False, server_default="brouillon"),
        sa.Column("motif", sa.String(200), nullable=False, server_default=""),
        sa.Column("date_mouvement", sa.Date, nullable=False),
        sa.Column("country", sa.String(2), nullable=False, server_default="cg"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_store_stock_moves_tenant_id", "store_stock_moves", ["tenant_id"])
    op.create_index("ix_store_stock_moves_sku", "store_stock_moves", ["sku"])


def downgrade() -> None:
    op.drop_index("ix_store_stock_moves_sku", table_name="store_stock_moves")
    op.drop_index("ix_store_stock_moves_tenant_id", table_name="store_stock_moves")
    op.drop_table("store_stock_moves")
    op.drop_column("store_stock_items", "pmp_xaf")
