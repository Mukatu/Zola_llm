"""FINTECH-3 : persistance dossiers de crédit + registres KYC

Revision ID: 20260708_0039
Revises: 20260707_0038
Create Date: 2026-07-08
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260708_0039"
down_revision: str | None = "20260707_0038"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "store_credit_applications",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("numero", sa.String(64), nullable=False),
        sa.Column("client", sa.String(200), nullable=False),
        sa.Column("montant_demande_xaf", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("duree_mois", sa.Integer, nullable=False, server_default="0"),
        sa.Column("score", sa.Integer, nullable=False, server_default="0"),
        sa.Column("grade", sa.String(2), nullable=False, server_default="E"),
        sa.Column("decision", sa.String(12), nullable=False, server_default="refuse"),
        sa.Column("statut", sa.String(16), nullable=False, server_default="evaluee"),
        sa.Column("taux_endettement_pct", sa.Numeric(6, 2), nullable=False, server_default="0"),
        sa.Column("mensualite_xaf", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("montant_max_xaf", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("dossier", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("resultat", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("commentaire", sa.Text, nullable=True),
        sa.Column("country", sa.String(2), nullable=False, server_default="cg"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index(
        "ix_store_credit_applications_tenant_id", "store_credit_applications", ["tenant_id"]
    )

    op.create_table(
        "store_kyc_records",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("nom", sa.String(200), nullable=False),
        sa.Column("type_client", sa.String(16), nullable=False, server_default="particulier"),
        sa.Column("niveau_risque", sa.String(8), nullable=False, server_default="faible"),
        sa.Column("score_risque", sa.Integer, nullable=False, server_default="0"),
        sa.Column("vigilance", sa.String(12), nullable=False, server_default="standard"),
        sa.Column("complet", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column(
            "peut_entrer_en_relation", sa.Boolean, nullable=False, server_default=sa.false()
        ),
        sa.Column("pep", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("statut", sa.String(16), nullable=False, server_default="a_valider"),
        sa.Column("profil", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("resultat", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("commentaire", sa.Text, nullable=True),
        sa.Column("country", sa.String(2), nullable=False, server_default="cg"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_store_kyc_records_tenant_id", "store_kyc_records", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("ix_store_kyc_records_tenant_id", table_name="store_kyc_records")
    op.drop_table("store_kyc_records")
    op.drop_index(
        "ix_store_credit_applications_tenant_id", table_name="store_credit_applications"
    )
    op.drop_table("store_credit_applications")
