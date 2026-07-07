"""Commons niveau 3 — Phase A : consentement + quarantaine de contribution

Revision ID: 20260707_0035
Revises: 20260703_0034
Create Date: 2026-07-07

- store_contribution_optin : consentement local par locataire (désactivé par défaut).
- store_contrib_candidates : candidats anonymisés en quarantaine (SANS tenant_id).
- store_agent_feedback.contributed : marqueur local d'idempotence.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260707_0035"
down_revision: str | None = "20260703_0034"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "store_contribution_optin",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False, server_default="local"),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("scopes", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("updated_by", sa.String(120), nullable=True),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index(
        "ix_store_contribution_optin_tenant_id",
        "store_contribution_optin",
        ["tenant_id"],
        unique=True,
    )

    op.create_table(
        "store_contrib_candidates",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("type", sa.String(24), nullable=False),
        sa.Column("domaine", sa.String(64), nullable=False, server_default=""),
        sa.Column("payload", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("occurrences", sa.Integer, nullable=False, server_default="1"),
        sa.Column("status", sa.String(12), nullable=False, server_default="pending"),
        sa.Column("validated_by", sa.String(120), nullable=True),
        sa.Column("validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "first_seen", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "last_seen", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index(
        "ix_store_contrib_candidates_content_hash",
        "store_contrib_candidates",
        ["content_hash"],
        unique=True,
    )

    op.add_column(
        "store_agent_feedback",
        sa.Column("contributed", sa.Boolean, nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("store_agent_feedback", "contributed")
    op.drop_index(
        "ix_store_contrib_candidates_content_hash", table_name="store_contrib_candidates"
    )
    op.drop_table("store_contrib_candidates")
    op.drop_index(
        "ix_store_contribution_optin_tenant_id", table_name="store_contribution_optin"
    )
    op.drop_table("store_contribution_optin")
