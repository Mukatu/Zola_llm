"""SIRH-2a : recrutement (vacances, candidats, candidatures, entretiens)

Revision ID: 20260623_0009
Revises: 20260623_0008
Create Date: 2026-06-23
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260623_0009"
down_revision: str | None = "20260623_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "store_vacancies",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("code_vacance", sa.String(32), nullable=False),
        sa.Column("code_emploi", sa.String(32), nullable=True),
        sa.Column("intitule", sa.String(200), nullable=False),
        sa.Column("motif", sa.String(20), nullable=False, server_default="creation"),
        sa.Column("type_contrat_cible", sa.String(16), nullable=False, server_default="CDI"),
        sa.Column("nb_postes", sa.Integer, nullable=False, server_default="1"),
        sa.Column("departement", sa.String(120), nullable=False, server_default=""),
        sa.Column("lieu", sa.String(120), nullable=False, server_default=""),
        sa.Column("statut", sa.String(16), nullable=False, server_default="ouverte"),
        sa.Column("priorite", sa.String(8), nullable=False, server_default="moyenne"),
        sa.Column("date_ouverture", sa.Date, nullable=False),
        sa.Column("date_cible", sa.Date, nullable=True),
        sa.Column("manager_demandeur", sa.String(120), nullable=True),
        sa.Column("budget_xaf", sa.Numeric(18, 2), nullable=True),
        sa.Column("country", sa.String(2), nullable=False, server_default="cg"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_store_vacancies_tenant_id", "store_vacancies", ["tenant_id"])

    op.create_table(
        "store_candidates",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("nom", sa.String(120), nullable=False),
        sa.Column("prenom", sa.String(120), nullable=False, server_default=""),
        sa.Column("email", sa.String(200), nullable=True),
        sa.Column("telephone", sa.String(40), nullable=True),
        sa.Column("source", sa.String(20), nullable=False, server_default="spontanee"),
        sa.Column("cv_uri", sa.String(400), nullable=True),
        sa.Column("statut_vivier", sa.String(12), nullable=False, server_default="actif"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_store_candidates_tenant_id", "store_candidates", ["tenant_id"])

    op.create_table(
        "store_applications",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("candidate_id", sa.String(36), nullable=False),
        sa.Column("code_vacance", sa.String(32), nullable=False),
        sa.Column("etape", sa.String(16), nullable=False, server_default="reçue"),
        sa.Column("date_candidature", sa.Date, nullable=False),
        sa.Column("date_etape", sa.Date, nullable=True),
        sa.Column("note_globale", sa.Integer, nullable=True),
        sa.Column("decision", sa.String(120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_store_applications_tenant_id", "store_applications", ["tenant_id"])
    op.create_index("ix_store_applications_cand", "store_applications", ["candidate_id"])
    op.create_index("ix_store_applications_vac", "store_applications", ["code_vacance"])

    op.create_table(
        "store_interviews",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("application_id", sa.String(36), nullable=False),
        sa.Column("date_prevue", sa.Date, nullable=True),
        sa.Column("type", sa.String(16), nullable=False, server_default="RH"),
        sa.Column("grille", sa.JSON, nullable=False),
        sa.Column("score_global", sa.Integer, nullable=True),
        sa.Column("recommandation", sa.String(20), nullable=True),
        sa.Column("statut", sa.String(12), nullable=False, server_default="planifie"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_store_interviews_tenant_id", "store_interviews", ["tenant_id"])
    op.create_index("ix_store_interviews_app", "store_interviews", ["application_id"])


def downgrade() -> None:
    for ix, tbl in [
        ("ix_store_interviews_app", "store_interviews"),
        ("ix_store_interviews_tenant_id", "store_interviews"),
    ]:
        op.drop_index(ix, table_name=tbl)
    op.drop_table("store_interviews")
    for ix in ("ix_store_applications_vac", "ix_store_applications_cand", "ix_store_applications_tenant_id"):
        op.drop_index(ix, table_name="store_applications")
    op.drop_table("store_applications")
    op.drop_index("ix_store_candidates_tenant_id", table_name="store_candidates")
    op.drop_table("store_candidates")
    op.drop_index("ix_store_vacancies_tenant_id", table_name="store_vacancies")
    op.drop_table("store_vacancies")
