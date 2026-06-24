"""SIRH-3a : formation (catalogue, sessions, inscriptions, évaluations)

Revision ID: 20260624_0011
Revises: 20260623_0010
Create Date: 2026-06-24
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260624_0011"
down_revision: str | None = "20260623_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "store_trainings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column("intitule", sa.String(200), nullable=False),
        sa.Column("competences_visees", sa.JSON, nullable=False),
        sa.Column("modalite", sa.String(20), nullable=False, server_default="presentiel"),
        sa.Column("duree_heures", sa.Numeric(8, 2), nullable=False, server_default="0"),
        sa.Column("cout_xaf", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_store_trainings_tenant_id", "store_trainings", ["tenant_id"])

    op.create_table(
        "store_training_sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("training_code", sa.String(32), nullable=False),
        sa.Column("date_debut", sa.Date, nullable=False),
        sa.Column("date_fin", sa.Date, nullable=True),
        sa.Column("lieu", sa.String(120), nullable=False, server_default=""),
        sa.Column("formateur", sa.String(120), nullable=False, server_default=""),
        sa.Column("places", sa.Integer, nullable=False, server_default="0"),
        sa.Column("statut", sa.String(12), nullable=False, server_default="planifiee"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_store_training_sessions_tenant_id", "store_training_sessions", ["tenant_id"])

    op.create_table(
        "store_training_enrollments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("session_id", sa.String(36), nullable=False),
        sa.Column("employee_matricule", sa.String(32), nullable=False),
        sa.Column("statut", sa.String(12), nullable=False, server_default="inscrit"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_store_training_enrollments_tenant_id", "store_training_enrollments", ["tenant_id"])

    op.create_table(
        "store_training_evaluations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("enrollment_id", sa.String(36), nullable=False),
        sa.Column("type", sa.String(8), nullable=False, server_default="chaud"),
        sa.Column("satisfaction", sa.Integer, nullable=True),
        sa.Column("acquis", sa.Integer, nullable=True),
        sa.Column("date_eval", sa.Date, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_store_training_evaluations_tenant_id", "store_training_evaluations", ["tenant_id"])


def downgrade() -> None:
    for ix, tbl in [
        ("ix_store_training_evaluations_tenant_id", "store_training_evaluations"),
        ("ix_store_training_enrollments_tenant_id", "store_training_enrollments"),
        ("ix_store_training_sessions_tenant_id", "store_training_sessions"),
        ("ix_store_trainings_tenant_id", "store_trainings"),
    ]:
        op.drop_index(ix, table_name=tbl)
    op.drop_table("store_training_evaluations")
    op.drop_table("store_training_enrollments")
    op.drop_table("store_training_sessions")
    op.drop_table("store_trainings")
