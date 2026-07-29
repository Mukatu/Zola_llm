"""audit.log : GRANT SELECT à zolaos_app (consultation du journal côté cortex)

Revision ID: 20260729_0062
Revises: 20260729_0061
Create Date: 2026-07-29

Le journal d'audit canonique `audit.log` (chaîne de hachage + triggers
d'immuabilité, cf. `infra/postgres/02_audit_log.sql`) n'accordait à `zolaos_app`
que l'INSERT (append-only) ; la lecture était réservée à `zolaos_audit_reader`.
Le cockpit cabinet (Zolacortex, `GET /v1/cortex/audit`) a besoin de CONSULTER ce
journal via la connexion applicative. On accorde donc SELECT à `zolaos_app`.

Sûreté : l'immuabilité n'est PAS assurée par le refus de lecture mais par les
triggers `forbid_mutation` (UPDATE/DELETE interdits quel que soit le rôle) et
l'absence de tout grant UPDATE/DELETE à `zolaos_app`. Lire le journal ne permet
donc aucune altération — on réutilise la source de vérité au lieu d'en dupliquer.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260729_0062"
down_revision: str | None = "20260729_0061"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("GRANT SELECT ON audit.log TO zolaos_app")


def downgrade() -> None:
    op.execute("REVOKE SELECT ON audit.log FROM zolaos_app")
