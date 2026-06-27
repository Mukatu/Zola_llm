"""OPS-1 : Facility (actifs, échéances) + HSE (risques, incidents)

Revision ID: 20260626_0021
Revises: 20260626_0020
Create Date: 2026-06-27
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260626_0021"
down_revision: str | None = "20260626_0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "store_assets",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("id_externe", sa.String(64), nullable=False),
        sa.Column("libelle", sa.String(200), nullable=False),
        sa.Column("type_actif", sa.String(20), nullable=False, server_default="autre"),
        sa.Column("maintenance_intervalle_jours", sa.Integer, nullable=False, server_default="0"),
        sa.Column("derniere_maintenance", sa.Date, nullable=True),
        sa.Column("country", sa.String(2), nullable=False, server_default="cg"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_store_assets_tenant_id", "store_assets", ["tenant_id"])

    op.create_table(
        "store_echeances",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("id_externe", sa.String(64), nullable=False),
        sa.Column("asset_id", sa.String(64), nullable=True),
        sa.Column("type_echeance", sa.String(20), nullable=False, server_default="autre"),
        sa.Column("libelle", sa.String(200), nullable=False),
        sa.Column("date_echeance", sa.Date, nullable=False),
        sa.Column("country", sa.String(2), nullable=False, server_default="cg"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_store_echeances_tenant_id", "store_echeances", ["tenant_id"])

    op.create_table(
        "store_risques",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("id_externe", sa.String(64), nullable=False),
        sa.Column("libelle", sa.String(200), nullable=False),
        sa.Column("probabilite", sa.Integer, nullable=False, server_default="1"),
        sa.Column("gravite", sa.Integer, nullable=False, server_default="1"),
        sa.Column("country", sa.String(2), nullable=False, server_default="cg"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_store_risques_tenant_id", "store_risques", ["tenant_id"])

    op.create_table(
        "store_incidents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("id_externe", sa.String(64), nullable=False),
        sa.Column("date_incident", sa.Date, nullable=False),
        sa.Column("type_incident", sa.String(20), nullable=False, server_default="autre"),
        sa.Column("gravite", sa.String(12), nullable=False, server_default="mineur"),
        sa.Column("description", sa.Text, nullable=False, server_default=""),
        sa.Column("jours_arret", sa.Integer, nullable=False, server_default="0"),
        sa.Column("country", sa.String(2), nullable=False, server_default="cg"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_store_incidents_tenant_id", "store_incidents", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("ix_store_incidents_tenant_id", table_name="store_incidents")
    op.drop_table("store_incidents")
    op.drop_index("ix_store_risques_tenant_id", table_name="store_risques")
    op.drop_table("store_risques")
    op.drop_index("ix_store_echeances_tenant_id", table_name="store_echeances")
    op.drop_table("store_echeances")
    op.drop_index("ix_store_assets_tenant_id", table_name="store_assets")
    op.drop_table("store_assets")
