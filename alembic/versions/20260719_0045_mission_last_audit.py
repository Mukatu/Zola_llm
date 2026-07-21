"""missions.last_audit : dernier audit exécuté (findings d'overlay Polaris)

Revision ID: 20260719_0045
Revises: 20260719_0044
Create Date: 2026-07-19

Cockpit cabinet T3 — exécution des missions. Le résultat d'un audit (synthèse +
findings structurés) est persisté ici, pour alimenter la génération du rapport
.docx sans ré-invoquer le LLM.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "20260719_0045"
down_revision: str | None = "20260719_0044"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "missions",
        sa.Column("last_audit", JSONB, nullable=True),
        schema="core",
    )


def downgrade() -> None:
    op.drop_column("missions", "last_audit", schema="core")
