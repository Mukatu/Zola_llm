"""core.license_grants : entitlements de modules émis par Polaris (cockpit cortex)

Revision ID: 20260729_0061
Revises: 20260728_0060
Create Date: 2026-07-29

Persiste les licences (entitlements) signées émises depuis le cockpit cortex :
métadonnées (tenant, tier, options, fenêtre de validité) + le jeton JWT signé
(livrable). La table vit UNIQUEMENT côté cortex/cabinet — une box ne la voit
jamais, elle ne reçoit que le jeton (fichier ou tunnel) qu'elle vérifie avec la
clé publique. Le cycle de vie (active/expired/revoked) est dérivé à la lecture.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "20260729_0061"
down_revision: str | None = "20260728_0060"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "license_grants",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tenant_id",
            UUID(as_uuid=True),
            sa.ForeignKey("core.tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("license_id", sa.String(64), nullable=False),
        sa.Column("tier", sa.String(20), nullable=False),
        sa.Column("modules", sa.ARRAY(sa.String), nullable=False, server_default="{}"),
        sa.Column("token", sa.Text, nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "issued_by_user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("core.users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint("expires_at > issued_at", name="ck_license_grants_window"),
        sa.UniqueConstraint("license_id", name="uq_license_grants_license_id"),
        schema="core",
    )
    op.create_index(
        "ix_license_grants_tenant",
        "license_grants",
        ["tenant_id", "revoked_at"],
        schema="core",
    )


def downgrade() -> None:
    op.drop_index("ix_license_grants_tenant", table_name="license_grants", schema="core")
    op.drop_table("license_grants", schema="core")
