"""P2c : Achats / Procurement (fournisseurs, bons de commande)

Revision ID: 20260626_0014
Revises: 20260626_0013
Create Date: 2026-06-26
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260626_0014"
down_revision: str | None = "20260626_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "store_suppliers",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("id_externe", sa.String(64), nullable=False),
        sa.Column("nom", sa.String(200), nullable=False),
        sa.Column("secteur", sa.String(120), nullable=True),
        sa.Column("note_qualite", sa.Numeric(2, 1), nullable=False, server_default="0"),
        sa.Column("delai_moyen_jours", sa.Integer, nullable=False, server_default="0"),
        sa.Column("documents_conformite", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("actif", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("country", sa.String(2), nullable=False, server_default="cg"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_store_suppliers_tenant_id", "store_suppliers", ["tenant_id"])

    op.create_table(
        "store_purchase_orders",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("id_externe", sa.String(64), nullable=False),
        sa.Column("numero", sa.String(64), nullable=False),
        sa.Column("fournisseur", sa.String(200), nullable=False),
        sa.Column("objet", sa.String(200), nullable=False, server_default=""),
        sa.Column("date_emission", sa.Date, nullable=False),
        sa.Column("statut", sa.String(12), nullable=False, server_default="brouillon"),
        sa.Column("lignes", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("montant_ht_xaf", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("montant_ttc_xaf", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("delai_livraison_jours", sa.Integer, nullable=False, server_default="0"),
        sa.Column("invoice_id", sa.String(36), nullable=True),
        sa.Column("country", sa.String(2), nullable=False, server_default="cg"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_store_purchase_orders_tenant_id", "store_purchase_orders", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("ix_store_purchase_orders_tenant_id", table_name="store_purchase_orders")
    op.drop_table("store_purchase_orders")
    op.drop_index("ix_store_suppliers_tenant_id", table_name="store_suppliers")
    op.drop_table("store_suppliers")
