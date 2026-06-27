"""MKT-1 : marketing (contacts + consentement, campagnes)

Revision ID: 20260626_0020
Revises: 20260626_0019
Create Date: 2026-06-27
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260626_0020"
down_revision: str | None = "20260626_0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "store_marketing_contacts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("id_externe", sa.String(64), nullable=False),
        sa.Column("nom", sa.String(200), nullable=False),
        sa.Column("email", sa.String(200), nullable=True),
        sa.Column("telephone", sa.String(40), nullable=True),
        sa.Column("secteur", sa.String(120), nullable=True),
        sa.Column("type", sa.String(12), nullable=False, server_default="prospect"),
        sa.Column("derniere_interaction", sa.Date, nullable=True),
        sa.Column("consentement_marketing", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("finalites", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("date_consentement", sa.Date, nullable=True),
        sa.Column("source", sa.String(60), nullable=True),
        sa.Column("country", sa.String(2), nullable=False, server_default="cg"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index(
        "ix_store_marketing_contacts_tenant_id", "store_marketing_contacts", ["tenant_id"]
    )

    op.create_table(
        "store_campaigns",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("nom", sa.String(120), nullable=False),
        sa.Column("canal", sa.String(8), nullable=False, server_default="email"),
        sa.Column("finalite", sa.String(60), nullable=False),
        sa.Column("segment", sa.String(60), nullable=True),
        sa.Column("objet", sa.String(200), nullable=True),
        sa.Column("statut", sa.String(12), nullable=False, server_default="brouillon"),
        sa.Column("date_creation", sa.Date, nullable=True),
        sa.Column("date_envoi", sa.Date, nullable=True),
        sa.Column("nb_cibles", sa.Integer, nullable=False, server_default="0"),
        sa.Column("nb_envois", sa.Integer, nullable=False, server_default="0"),
        sa.Column("nb_ouvertures", sa.Integer, nullable=False, server_default="0"),
        sa.Column("nb_clics", sa.Integer, nullable=False, server_default="0"),
        sa.Column("country", sa.String(2), nullable=False, server_default="cg"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_store_campaigns_tenant_id", "store_campaigns", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("ix_store_campaigns_tenant_id", table_name="store_campaigns")
    op.drop_table("store_campaigns")
    op.drop_index("ix_store_marketing_contacts_tenant_id", table_name="store_marketing_contacts")
    op.drop_table("store_marketing_contacts")
