"""système de référence léger : écritures + stocks (P2)

Revision ID: 20260623_0006
Revises: 20260623_0005
Create Date: 2026-06-23

Tables de persistance des écritures comptables (lignes en JSON) et des articles
de stock. Schéma par défaut (public), portable PostgreSQL/SQLite.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260623_0006"
down_revision: str | None = "20260623_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "store_journal_entries",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("date_ecriture", sa.Date, nullable=False),
        sa.Column("journal", sa.String(16), nullable=False, server_default="OD"),
        sa.Column("libelle", sa.String(200), nullable=False),
        sa.Column("reference", sa.String(64), nullable=True),
        sa.Column("lignes", sa.JSON, nullable=False),
        sa.Column("total_debit_xaf", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("total_credit_xaf", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("equilibre", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("country", sa.String(2), nullable=False, server_default="cg"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_store_journal_entries_tenant_id", "store_journal_entries", ["tenant_id"])

    op.create_table(
        "store_stock_items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("sku", sa.String(64), nullable=False),
        sa.Column("libelle", sa.String(200), nullable=False),
        sa.Column("quantite_actuelle", sa.Numeric(18, 3), nullable=False, server_default="0"),
        sa.Column("unite", sa.String(16), nullable=False, server_default="unité"),
        sa.Column("conso_moyenne_jour", sa.Numeric(18, 3), nullable=False, server_default="0"),
        sa.Column("delai_appro_jours", sa.Integer, nullable=False, server_default="0"),
        sa.Column("stock_securite", sa.Numeric(18, 3), nullable=False, server_default="0"),
        sa.Column("country", sa.String(2), nullable=False, server_default="cg"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_store_stock_items_tenant_id", "store_stock_items", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("ix_store_stock_items_tenant_id", table_name="store_stock_items")
    op.drop_table("store_stock_items")
    op.drop_index("ix_store_journal_entries_tenant_id", table_name="store_journal_entries")
    op.drop_table("store_journal_entries")
