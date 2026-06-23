"""SIRH référentiels : RME / RMC / profil requis / matrice + code_emploi employé

Revision ID: 20260623_0008
Revises: 20260623_0007
Create Date: 2026-06-23

Socle Référentiels & GPEC : emplois (RME), compétences (RMC), profil requis par
emploi, matrice de compétences. Ajoute `code_emploi` aux employés (chaînon RME).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260623_0008"
down_revision: str | None = "20260623_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("store_employees", sa.Column("code_emploi", sa.String(32), nullable=True))

    op.create_table(
        "store_job_roles",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("code_emploi", sa.String(32), nullable=False),
        sa.Column("famille_professionnelle", sa.String(120), nullable=False, server_default=""),
        sa.Column("intitule", sa.String(200), nullable=False),
        sa.Column("mission_principale", sa.String(1000), nullable=False, server_default=""),
        sa.Column("activites", sa.JSON, nullable=False),
        sa.Column("kpis", sa.JSON, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_store_job_roles_tenant_id", "store_job_roles", ["tenant_id"])

    op.create_table(
        "store_skills",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("code_competence", sa.String(32), nullable=False),
        sa.Column("domaine", sa.String(20), nullable=False, server_default="technique"),
        sa.Column("intitule", sa.String(200), nullable=False),
        sa.Column("niveau_1", sa.String(500), nullable=False, server_default=""),
        sa.Column("niveau_2", sa.String(500), nullable=False, server_default=""),
        sa.Column("niveau_3", sa.String(500), nullable=False, server_default=""),
        sa.Column("niveau_4", sa.String(500), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_store_skills_tenant_id", "store_skills", ["tenant_id"])

    op.create_table(
        "store_role_skills",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("code_emploi", sa.String(32), nullable=False),
        sa.Column("code_competence", sa.String(32), nullable=False),
        sa.Column("niveau_requis", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_store_role_skills_tenant_id", "store_role_skills", ["tenant_id"])

    op.create_table(
        "store_employee_skills",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("employee_matricule", sa.String(32), nullable=False),
        sa.Column("code_competence", sa.String(32), nullable=False),
        sa.Column("note", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_store_employee_skills_tenant_id", "store_employee_skills", ["tenant_id"])
    op.create_index("ix_store_employee_skills_emp", "store_employee_skills", ["employee_matricule"])


def downgrade() -> None:
    op.drop_index("ix_store_employee_skills_emp", table_name="store_employee_skills")
    op.drop_index("ix_store_employee_skills_tenant_id", table_name="store_employee_skills")
    op.drop_table("store_employee_skills")
    op.drop_index("ix_store_role_skills_tenant_id", table_name="store_role_skills")
    op.drop_table("store_role_skills")
    op.drop_index("ix_store_skills_tenant_id", table_name="store_skills")
    op.drop_table("store_skills")
    op.drop_index("ix_store_job_roles_tenant_id", table_name="store_job_roles")
    op.drop_table("store_job_roles")
    op.drop_column("store_employees", "code_emploi")
