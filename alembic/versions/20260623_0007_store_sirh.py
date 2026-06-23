"""SIRH-1 : registres employés / contrats / absences

Revision ID: 20260623_0007
Revises: 20260623_0006
Create Date: 2026-06-23

Tables du Core HR (système de référence léger) : employés, contrats, absences.
Schéma par défaut, portable PostgreSQL/SQLite.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260623_0007"
down_revision: str | None = "20260623_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "store_employees",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("matricule", sa.String(32), nullable=False),
        sa.Column("nom_complet", sa.String(200), nullable=False),
        sa.Column("genre", sa.String(4), nullable=False, server_default="NC"),
        sa.Column("date_naissance", sa.Date, nullable=True),
        sa.Column("date_embauche", sa.Date, nullable=False),
        sa.Column("poste", sa.String(120), nullable=False, server_default=""),
        sa.Column("departement", sa.String(120), nullable=False, server_default=""),
        sa.Column("manager_matricule", sa.String(32), nullable=True),
        sa.Column("categorie", sa.String(40), nullable=True),
        sa.Column("salaire_base_xaf", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("quotite", sa.Numeric(4, 2), nullable=False, server_default="1"),
        sa.Column("statut", sa.String(8), nullable=False, server_default="actif"),
        sa.Column("date_sortie", sa.Date, nullable=True),
        sa.Column("motif_sortie", sa.String(120), nullable=True),
        sa.Column("country", sa.String(2), nullable=False, server_default="cg"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_store_employees_tenant_id", "store_employees", ["tenant_id"])

    op.create_table(
        "store_contracts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("employee_matricule", sa.String(32), nullable=False),
        sa.Column("type", sa.String(16), nullable=False, server_default="CDI"),
        sa.Column("date_debut", sa.Date, nullable=False),
        sa.Column("date_fin", sa.Date, nullable=True),
        sa.Column("fin_periode_essai", sa.Date, nullable=True),
        sa.Column("statut", sa.String(12), nullable=False, server_default="actif"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_store_contracts_tenant_id", "store_contracts", ["tenant_id"])
    op.create_index("ix_store_contracts_emp", "store_contracts", ["employee_matricule"])

    op.create_table(
        "store_absences",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("employee_matricule", sa.String(32), nullable=False),
        sa.Column("type", sa.String(16), nullable=False, server_default="conge_paye"),
        sa.Column("date_debut", sa.Date, nullable=False),
        sa.Column("date_fin", sa.Date, nullable=False),
        sa.Column("jours", sa.Numeric(6, 2), nullable=False, server_default="0"),
        sa.Column("statut", sa.String(12), nullable=False, server_default="valide"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_store_absences_tenant_id", "store_absences", ["tenant_id"])
    op.create_index("ix_store_absences_emp", "store_absences", ["employee_matricule"])


def downgrade() -> None:
    op.drop_index("ix_store_absences_emp", table_name="store_absences")
    op.drop_index("ix_store_absences_tenant_id", table_name="store_absences")
    op.drop_table("store_absences")
    op.drop_index("ix_store_contracts_emp", table_name="store_contracts")
    op.drop_index("ix_store_contracts_tenant_id", table_name="store_contracts")
    op.drop_table("store_contracts")
    op.drop_index("ix_store_employees_tenant_id", table_name="store_employees")
    op.drop_table("store_employees")
