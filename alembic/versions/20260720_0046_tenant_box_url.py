"""tenants.box_url : adresse de la Zolabox pour le RAG distant Zero Trust (hybride)

Revision ID: 20260720_0046
Revises: 20260719_0045
Create Date: 2026-07-20

Déploiement hybride (P-A) : le Cortex tire les extraits du corpus privé du client
depuis SA Zolabox via ``MissionClient``. Cette colonne porte l'adresse à joindre.
NULL ⇒ pas de box enregistrée ⇒ l'audit retombe sur le retrieve local du Cortex.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260720_0046"
down_revision: str | None = "20260719_0045"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column("box_url", sa.String(500), nullable=True),
        schema="core",
    )


def downgrade() -> None:
    op.drop_column("tenants", "box_url", schema="core")
