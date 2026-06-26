"""TRESO-1 : trésorerie (comptes bancaires/caisse + flux de trésorerie)

Revision ID: 20260626_0018
Revises: 20260626_0017
Create Date: 2026-06-26
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260626_0018"
down_revision: str | None = "20260626_0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "store_bank_accounts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column("libelle", sa.String(120), nullable=False),
        sa.Column("banque", sa.String(120), nullable=False, server_default=""),
        sa.Column("type", sa.String(16), nullable=False, server_default="banque"),
        sa.Column("devise", sa.String(3), nullable=False, server_default="XAF"),
        sa.Column("iban", sa.String(34), nullable=True),
        sa.Column("solde_initial_xaf", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("country", sa.String(2), nullable=False, server_default="cg"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_store_bank_accounts_tenant_id", "store_bank_accounts", ["tenant_id"])

    op.create_table(
        "store_cash_flows",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("reference", sa.String(64), nullable=False),
        sa.Column("compte_code", sa.String(32), nullable=False),
        sa.Column("sens", sa.String(13), nullable=False, server_default="encaissement"),
        sa.Column("montant_xaf", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("date_operation", sa.Date, nullable=False),
        sa.Column("date_prevue", sa.Date, nullable=True),
        sa.Column("statut", sa.String(8), nullable=False, server_default="realise"),
        sa.Column("categorie", sa.String(60), nullable=False, server_default=""),
        sa.Column("tiers", sa.String(200), nullable=False, server_default=""),
        sa.Column("libelle", sa.String(200), nullable=False, server_default=""),
        sa.Column("mode", sa.String(16), nullable=False, server_default="virement"),
        sa.Column("invoice_id", sa.String(36), nullable=True),
        sa.Column("country", sa.String(2), nullable=False, server_default="cg"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_store_cash_flows_tenant_id", "store_cash_flows", ["tenant_id"])
    op.create_index("ix_store_cash_flows_compte_code", "store_cash_flows", ["compte_code"])


def downgrade() -> None:
    op.drop_index("ix_store_cash_flows_compte_code", table_name="store_cash_flows")
    op.drop_index("ix_store_cash_flows_tenant_id", table_name="store_cash_flows")
    op.drop_table("store_cash_flows")
    op.drop_index("ix_store_bank_accounts_tenant_id", table_name="store_bank_accounts")
    op.drop_table("store_bank_accounts")
