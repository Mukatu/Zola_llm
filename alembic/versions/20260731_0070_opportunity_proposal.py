"""CRM : opportunities.proposal (proposition commerciale)

Revision ID: 20260731_0070
Revises: 20260731_0069
Create Date: 2026-07-31

Ajoute le champ `proposal` (lettre de mission / proposition commerciale, markdown)
sur les opportunités : rédigé à la main ou par l'IA (ancrée corpus, citée, sans
chiffrage d'honoraires).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260731_0070"
down_revision: str | None = "20260731_0069"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "opportunities",
        sa.Column("proposal", sa.Text, nullable=False, server_default=""),
        schema="core",
    )


def downgrade() -> None:
    op.drop_column("opportunities", "proposal", schema="core")
