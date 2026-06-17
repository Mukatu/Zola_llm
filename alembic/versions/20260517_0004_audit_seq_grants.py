"""audit grants: USAGE/SELECT sur les séquences pour zolaos_app et audit_writer.

Revision ID: 20260517_0004
Revises: 20260517_0003
Create Date: 2026-05-17

Correctif : l'init script `01_init_schemas.sql` accorde INSERT sur les TABLES
du schema `audit` à zolaos_app et zolaos_audit_writer, mais oublie USAGE/SELECT
sur les SEQUENCES. Une table `audit.log` (BIGSERIAL) nécessite que l'utilisateur
qui INSERT ait aussi USAGE sur la séquence `audit.log_id_seq` — sinon :
`permission denied for sequence log_id_seq`.

On corrige sur l'existant ET on met à jour les ALTER DEFAULT PRIVILEGES pour
les futures séquences créées dans `audit`.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260517_0004"
down_revision: str | None = "20260517_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Grants explicites sur les TABLES existantes (audit.log notamment).
    op.execute(
        "GRANT INSERT ON ALL TABLES IN SCHEMA audit "
        "TO zolaos_app, zolaos_audit_writer"
    )
    op.execute(
        "GRANT SELECT ON ALL TABLES IN SCHEMA audit TO zolaos_audit_reader"
    )
    # Grants explicites sur les séquences existantes (audit.log_id_seq).
    op.execute(
        "GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA audit "
        "TO zolaos_app, zolaos_audit_writer"
    )
    # Default privileges pour les FUTURES tables + séquences créées par zolaos_migrator.
    op.execute(
        "ALTER DEFAULT PRIVILEGES FOR ROLE zolaos_migrator IN SCHEMA audit "
        "GRANT INSERT ON TABLES TO zolaos_app, zolaos_audit_writer"
    )
    op.execute(
        "ALTER DEFAULT PRIVILEGES FOR ROLE zolaos_migrator IN SCHEMA audit "
        "GRANT USAGE, SELECT ON SEQUENCES TO zolaos_app, zolaos_audit_writer"
    )

    # Trigger compute_hashes en SECURITY DEFINER : il fait `SELECT row_hash FROM
    # audit.log` pour calculer la chaîne. Sans SECURITY DEFINER il s'exécute avec
    # les droits de l'invocateur (zolaos_app qui n'a QUE INSERT) → "permission
    # denied for table log". On bascule en SECURITY DEFINER : le trigger
    # s'exécute avec les droits du propriétaire (zolaos_migrator) et préserve
    # le principe append-only côté app (zolaos_app garde uniquement INSERT).
    op.execute(
        "ALTER FUNCTION audit.compute_hashes() SECURITY DEFINER"
    )
    # Verrouille le search_path du SECURITY DEFINER pour éviter toute hijack
    # via un schéma malveillant.
    op.execute(
        "ALTER FUNCTION audit.compute_hashes() SET search_path = audit, public"
    )


def downgrade() -> None:
    op.execute(
        "ALTER FUNCTION audit.compute_hashes() RESET search_path"
    )
    op.execute(
        "ALTER FUNCTION audit.compute_hashes() SECURITY INVOKER"
    )
    op.execute(
        "REVOKE INSERT ON ALL TABLES IN SCHEMA audit "
        "FROM zolaos_app, zolaos_audit_writer"
    )
    op.execute(
        "REVOKE SELECT ON ALL TABLES IN SCHEMA audit FROM zolaos_audit_reader"
    )
    op.execute(
        "REVOKE USAGE, SELECT ON ALL SEQUENCES IN SCHEMA audit "
        "FROM zolaos_app, zolaos_audit_writer"
    )
    op.execute(
        "ALTER DEFAULT PRIVILEGES FOR ROLE zolaos_migrator IN SCHEMA audit "
        "REVOKE INSERT ON TABLES FROM zolaos_app, zolaos_audit_writer"
    )
    op.execute(
        "ALTER DEFAULT PRIVILEGES FOR ROLE zolaos_migrator IN SCHEMA audit "
        "REVOKE USAGE, SELECT ON SEQUENCES FROM zolaos_app, zolaos_audit_writer"
    )
