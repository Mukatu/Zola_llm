"""GED : core.deliverable_templates + core.deliverables

Revision ID: 20260731_0069
Revises: 20260731_0068
Create Date: 2026-07-31

Bibliothèque de modèles de livrables (squelettes de sections) + les livrables
produits par mission (contenu markdown, statut draft→review→final, version). Un
livrable peut être instancié d'un modèle (qui sème le squelette).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "20260731_0069"
down_revision: str | None = "20260731_0068"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "deliverable_templates",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("offre", sa.String(64), nullable=True),
        sa.Column("description", sa.Text, nullable=False, server_default=""),
        sa.Column("sections", JSONB, nullable=False, server_default="[]"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column(
            "created_by_user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("core.users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        schema="core",
    )

    op.create_table(
        "deliverables",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column(
            "mission_id",
            UUID(as_uuid=True),
            sa.ForeignKey("core.missions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "template_id",
            UUID(as_uuid=True),
            sa.ForeignKey("core.deliverable_templates.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("content", sa.Text, nullable=False, server_default=""),
        sa.Column("status", sa.String(16), nullable=False, server_default="draft"),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column(
            "created_by_user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("core.users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("status IN ('draft', 'review', 'final')", name="ck_deliverables_status"),
        schema="core",
    )
    op.create_index("ix_deliverables_mission", "deliverables", ["mission_id"], schema="core")


def downgrade() -> None:
    op.drop_index("ix_deliverables_mission", table_name="deliverables", schema="core")
    op.drop_table("deliverables", schema="core")
    op.drop_table("deliverable_templates", schema="core")
