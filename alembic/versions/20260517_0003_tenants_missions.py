"""tenancy 2 niveaux: core.tenants + core.missions (Polaris-6 + Polaris-7)

Revision ID: 20260517_0003
Revises: 20260517_0002
Create Date: 2026-05-17

- core.tenants : entités logiques (cabinet OU client), avec parent_tenant_id
  permettant de lier un client à son cabinet de référence (Polaris).
- core.missions : missions d'audit lancées par un consultant cabinet sur un
  tenant client. Génère un JWT mission scopé pour la connexion éphémère
  Zolacortex → Zolabox.

Préservation : la colonne `tenant_id String(64)` existante sur core.users
reste en place (legacy tag). On ajoute `tenant_uuid` UUID FK nullable qui
remplacera progressivement le champ string.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "20260517_0003"
down_revision: str | None = "20260517_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ---- core.tenants -------------------------------------------------------
    op.create_table(
        "tenants",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("tenant_type", sa.String(16), nullable=False),  # 'cabinet' | 'client'
        sa.Column(
            "parent_tenant_id",
            UUID(as_uuid=True),
            sa.ForeignKey("core.tenants.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("country", sa.String(2), nullable=False, server_default="cg"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "tenant_type IN ('cabinet', 'client')",
            name="ck_tenants_type",
        ),
        sa.CheckConstraint("char_length(country) = 2", name="ck_tenants_country_iso2"),
        sa.UniqueConstraint("name", "tenant_type", name="uq_tenants_name_type"),
        schema="core",
    )
    op.create_index(
        "ix_tenants_parent",
        "tenants",
        ["parent_tenant_id"],
        schema="core",
    )
    op.create_index(
        "ix_tenants_type",
        "tenants",
        ["tenant_type"],
        schema="core",
    )

    # ---- core.users : ajout tenant_uuid (FK vers core.tenants) -------------
    # Le tenant_id String(64) existant reste comme legacy tag (pas supprimé).
    op.add_column(
        "users",
        sa.Column(
            "tenant_uuid",
            UUID(as_uuid=True),
            sa.ForeignKey("core.tenants.id", ondelete="SET NULL"),
            nullable=True,
        ),
        schema="core",
    )
    op.create_index(
        "ix_users_tenant_uuid",
        "users",
        ["tenant_uuid"],
        schema="core",
    )

    # ---- core.missions -----------------------------------------------------
    op.create_table(
        "missions",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "cabinet_tenant_id",
            UUID(as_uuid=True),
            sa.ForeignKey("core.tenants.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "client_tenant_id",
            UUID(as_uuid=True),
            sa.ForeignKey("core.tenants.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("offre", sa.String(64), nullable=False),  # 'conformite_rh', 'fiscal_ohada', ...
        sa.Column(
            "consultant_user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("core.users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column("scope_tags", sa.ARRAY(sa.Text), nullable=False, server_default="{}"),
        sa.CheckConstraint(
            "status IN ('active', 'expired', 'revoked', 'completed')",
            name="ck_missions_status",
        ),
        sa.CheckConstraint(
            "cabinet_tenant_id != client_tenant_id",
            name="ck_missions_distinct_tenants",
        ),
        sa.CheckConstraint(
            "expires_at > started_at",
            name="ck_missions_valid_window",
        ),
        schema="core",
    )
    op.create_index(
        "ix_missions_cabinet",
        "missions",
        ["cabinet_tenant_id", "status"],
        schema="core",
    )
    op.create_index(
        "ix_missions_client",
        "missions",
        ["client_tenant_id", "status"],
        schema="core",
    )
    op.create_index(
        "ix_missions_consultant",
        "missions",
        ["consultant_user_id"],
        schema="core",
    )
    op.create_index(
        "ix_missions_active_expiry",
        "missions",
        ["expires_at"],
        schema="core",
        postgresql_where=sa.text("status = 'active'"),
    )


def downgrade() -> None:
    op.drop_index("ix_missions_active_expiry", table_name="missions", schema="core")
    op.drop_index("ix_missions_consultant", table_name="missions", schema="core")
    op.drop_index("ix_missions_client", table_name="missions", schema="core")
    op.drop_index("ix_missions_cabinet", table_name="missions", schema="core")
    op.drop_table("missions", schema="core")

    op.drop_index("ix_users_tenant_uuid", table_name="users", schema="core")
    op.drop_column("users", "tenant_uuid", schema="core")

    op.drop_index("ix_tenants_type", table_name="tenants", schema="core")
    op.drop_index("ix_tenants_parent", table_name="tenants", schema="core")
    op.drop_table("tenants", schema="core")
