"""P2b : CRM / Commercial (clients, opportunités, devis, interactions)

Revision ID: 20260626_0013
Revises: 20260624_0012
Create Date: 2026-06-26
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260626_0013"
down_revision: str | None = "20260624_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "store_customers",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("id_externe", sa.String(64), nullable=False),
        sa.Column("nom", sa.String(200), nullable=False),
        sa.Column("type", sa.String(12), nullable=False, server_default="prospect"),
        sa.Column("email", sa.String(200), nullable=True),
        sa.Column("telephone", sa.String(40), nullable=True),
        sa.Column("secteur", sa.String(120), nullable=True),
        sa.Column("source", sa.String(12), nullable=False, server_default="autre"),
        sa.Column("date_creation", sa.Date, nullable=True),
        sa.Column("derniere_interaction", sa.Date, nullable=True),
        sa.Column("country", sa.String(2), nullable=False, server_default="cg"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_store_customers_tenant_id", "store_customers", ["tenant_id"])

    op.create_table(
        "store_opportunities",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("id_externe", sa.String(64), nullable=False),
        sa.Column("client", sa.String(200), nullable=False),
        sa.Column("libelle", sa.String(200), nullable=False),
        sa.Column("montant_xaf", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("etape", sa.String(16), nullable=False, server_default="prospection"),
        sa.Column("probabilite", sa.Numeric(4, 3), nullable=True),
        sa.Column("date_creation", sa.Date, nullable=True),
        sa.Column("date_cloture_prevue", sa.Date, nullable=True),
        sa.Column("derniere_interaction", sa.Date, nullable=True),
        sa.Column("country", sa.String(2), nullable=False, server_default="cg"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_store_opportunities_tenant_id", "store_opportunities", ["tenant_id"])

    op.create_table(
        "store_quotes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("id_externe", sa.String(64), nullable=False),
        sa.Column("numero", sa.String(64), nullable=False),
        sa.Column("client", sa.String(200), nullable=False),
        sa.Column("date_emission", sa.Date, nullable=False),
        sa.Column("date_validite", sa.Date, nullable=True),
        sa.Column("statut", sa.String(12), nullable=False, server_default="brouillon"),
        sa.Column("lignes", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("montant_ht_xaf", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("montant_ttc_xaf", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("invoice_id", sa.String(36), nullable=True),
        sa.Column("country", sa.String(2), nullable=False, server_default="cg"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_store_quotes_tenant_id", "store_quotes", ["tenant_id"])

    op.create_table(
        "store_interactions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("customer_id", sa.String(36), nullable=True),
        sa.Column("opportunity_id", sa.String(36), nullable=True),
        sa.Column("type", sa.String(12), nullable=False, server_default="note"),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("resume", sa.Text, nullable=False, server_default=""),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_store_interactions_tenant_id", "store_interactions", ["tenant_id"])
    op.create_index("ix_store_interactions_customer", "store_interactions", ["customer_id"])
    op.create_index("ix_store_interactions_opportunity", "store_interactions", ["opportunity_id"])


def downgrade() -> None:
    op.drop_index("ix_store_interactions_opportunity", table_name="store_interactions")
    op.drop_index("ix_store_interactions_customer", table_name="store_interactions")
    op.drop_index("ix_store_interactions_tenant_id", table_name="store_interactions")
    op.drop_table("store_interactions")
    op.drop_index("ix_store_quotes_tenant_id", table_name="store_quotes")
    op.drop_table("store_quotes")
    op.drop_index("ix_store_opportunities_tenant_id", table_name="store_opportunities")
    op.drop_table("store_opportunities")
    op.drop_index("ix_store_customers_tenant_id", table_name="store_customers")
    op.drop_table("store_customers")
