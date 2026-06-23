"""système de référence léger : store_invoices (addendum persistance légère)

Revision ID: 20260623_0005
Revises: 20260517_0004
Create Date: 2026-06-23

Table de persistance des factures (système de référence léger pour les clients
sans ERP). Schéma par défaut (public) pour rester cohérent avec l'ORM `StoreBase`
portable PostgreSQL/SQLite. Préfixe `store_` = regroupement logique.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260623_0005"
down_revision: str | None = "20260517_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "store_invoices",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("numero", sa.String(64), nullable=False),
        sa.Column("sens", sa.String(8), nullable=False, server_default="vente"),
        sa.Column("tiers", sa.String(200), nullable=False),
        sa.Column("date_emission", sa.Date, nullable=False),
        sa.Column("date_echeance", sa.Date, nullable=True),
        sa.Column("montant_ht_xaf", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("montant_tva_xaf", sa.Numeric(18, 2), nullable=True),
        sa.Column("montant_ttc_xaf", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("devise", sa.String(3), nullable=False, server_default="XAF"),
        sa.Column("payee", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("country", sa.String(2), nullable=False, server_default="cg"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_store_invoices_tenant_id", "store_invoices", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("ix_store_invoices_tenant_id", table_name="store_invoices")
    op.drop_table("store_invoices")
