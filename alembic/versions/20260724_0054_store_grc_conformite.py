"""GRC : registre de conformité (obligations, contrôles, constats)

Revision ID: 20260724_0054
Revises: 20260723_0053
Create Date: 2026-07-24
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260724_0054"
down_revision: str | None = "20260723_0053"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "store_obligations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("reference", sa.String(64), nullable=False, server_default=""),
        sa.Column("intitule", sa.String(300), nullable=False),
        sa.Column("domaine", sa.String(20), nullable=False, server_default="autre"),
        sa.Column("autorite", sa.String(120), nullable=False, server_default=""),
        sa.Column("periodicite", sa.String(16), nullable=False, server_default="ponctuelle"),
        sa.Column("echeance", sa.Date, nullable=True),
        sa.Column("base_legale", sa.Text, nullable=False, server_default=""),
        sa.Column("statut", sa.String(12), nullable=False, server_default="active"),
        sa.Column("country", sa.String(2), nullable=False, server_default="cg"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_store_obligations_tenant_id", "store_obligations", ["tenant_id"])

    op.create_table(
        "store_controls",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("obligation_id", sa.String(36), nullable=True),
        sa.Column("intitule", sa.String(300), nullable=False),
        sa.Column("type_controle", sa.String(12), nullable=False, server_default="preventif"),
        sa.Column("frequence", sa.String(16), nullable=False, server_default="ponctuel"),
        sa.Column("responsable", sa.String(120), nullable=False, server_default=""),
        sa.Column("derniere_execution", sa.Date, nullable=True),
        sa.Column("prochaine_execution", sa.Date, nullable=True),
        sa.Column("statut", sa.String(12), nullable=False, server_default="planifie"),
        sa.Column("country", sa.String(2), nullable=False, server_default="cg"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_store_controls_tenant_id", "store_controls", ["tenant_id"])
    op.create_index("ix_store_controls_obligation_id", "store_controls", ["obligation_id"])

    op.create_table(
        "store_findings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("obligation_id", sa.String(36), nullable=True),
        sa.Column("control_id", sa.String(36), nullable=True),
        sa.Column("intitule", sa.String(300), nullable=False),
        sa.Column("gravite", sa.String(10), nullable=False, server_default="mineur"),
        sa.Column("statut", sa.String(10), nullable=False, server_default="ouvert"),
        sa.Column("date_constat", sa.Date, nullable=False),
        sa.Column("echeance_correction", sa.Date, nullable=True),
        sa.Column("plan_action", sa.Text, nullable=False, server_default=""),
        sa.Column("responsable", sa.String(120), nullable=False, server_default=""),
        sa.Column("country", sa.String(2), nullable=False, server_default="cg"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_store_findings_tenant_id", "store_findings", ["tenant_id"])
    op.create_index("ix_store_findings_obligation_id", "store_findings", ["obligation_id"])


def downgrade() -> None:
    op.drop_index("ix_store_findings_obligation_id", table_name="store_findings")
    op.drop_index("ix_store_findings_tenant_id", table_name="store_findings")
    op.drop_table("store_findings")
    op.drop_index("ix_store_controls_obligation_id", table_name="store_controls")
    op.drop_index("ix_store_controls_tenant_id", table_name="store_controls")
    op.drop_table("store_controls")
    op.drop_index("ix_store_obligations_tenant_id", table_name="store_obligations")
    op.drop_table("store_obligations")
