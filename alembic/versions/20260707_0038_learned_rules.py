"""Commons — learned_rules déterministe (mappings appris, multi-métier)

Revision ID: 20260707_0038
Revises: 20260707_0037
Create Date: 2026-07-07
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260707_0038"
down_revision: str | None = "20260707_0037"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "store_learned_rules",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("domaine", sa.String(64), nullable=False),
        sa.Column("cle", sa.String(300), nullable=False),
        sa.Column("valeur", sa.String(120), nullable=False),
        sa.Column("meta", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("occurrences", sa.Integer, nullable=False, server_default="1"),
        sa.Column("validated_by", sa.String(120), nullable=True),
        sa.Column(
            "promoted_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("domaine", "cle", name="uq_learned_domaine_cle"),
    )
    op.create_index("ix_store_learned_rules_domaine", "store_learned_rules", ["domaine"])


def downgrade() -> None:
    op.drop_index("ix_store_learned_rules_domaine", table_name="store_learned_rules")
    op.drop_table("store_learned_rules")
