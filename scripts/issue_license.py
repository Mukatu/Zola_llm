"""Émet une licence (entitlement) signée pour un tenant — côté POLARIS uniquement.

Construit un `Entitlement` (tier + options à la carte), le signe en RS256 avec
la clé PRIVÉE de Polaris (cf. `scripts/gen_entitlement_keys.py`) et imprime le
jeton JWT résultant. Ce jeton est ce qui se dépose sur la Zolabox du client,
soit inline (variable d'environnement ``ENTITLEMENT_LICENSE_JWT``), soit comme
fichier (chemin pointé par ``ENTITLEMENT_LICENSE_FILE``).

La clé PRIVÉE ne doit JAMAIS quitter le poste/service d'émission Polaris (elle
n'a rien à faire sur une box — cf. `src/zolaos/licensing/entitlement.py`).

Usage ::

    python scripts/issue_license.py \
        --tenant-id acme-sarl \
        --tier business \
        --module cyber \
        --days 365 \
        --private-key-file polaris_entitlement_private.pem

    # Tier + plusieurs options à la carte, avec un identifiant de licence choisi :
    python scripts/issue_license.py \
        --tenant-id acme-sarl --tier starter \
        --module fintech --module grc \
        --days 30 --license-id lic-acme-2026-07 \
        --private-key-file polaris_entitlement_private.pem
"""

from __future__ import annotations

import argparse
import sys
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

from zolaos.licensing import TIERS, Entitlement, sign_entitlement


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Émet (signe) une licence d'entitlement de modules pour un tenant.",
    )
    parser.add_argument("--tenant-id", required=True, help="Identifiant du tenant/client.")
    parser.add_argument(
        "--tier",
        required=True,
        choices=sorted(TIERS),
        help=f"Bundle de base ({' | '.join(sorted(TIERS))}).",
    )
    parser.add_argument(
        "--module",
        action="append",
        dest="modules",
        default=[],
        metavar="MODULE",
        help="Module optionnel à la carte, EN PLUS du tier (répétable).",
    )
    parser.add_argument("--days", type=int, required=True, help="Durée de validité en jours.")
    parser.add_argument(
        "--license-id",
        default=None,
        help="Identifiant de licence (défaut : uuid4 généré).",
    )
    parser.add_argument(
        "--private-key-file",
        required=True,
        help="Fichier PEM de la clé PRIVÉE Polaris (jamais sur une box).",
    )
    args = parser.parse_args()

    if args.days <= 0:
        sys.exit("Refusé : --days doit être strictement positif.")

    try:
        private_key_pem = Path(args.private_key_file).read_text(encoding="utf-8")
    except OSError as exc:
        sys.exit(f"Refusé : clé privée illisible ({args.private_key_file}) : {exc}")

    now = datetime.now(UTC)
    entitlement = Entitlement(
        tenant_id=args.tenant_id,
        tier=args.tier,
        modules=args.modules,
        license_id=args.license_id or str(uuid.uuid4()),
        issued_at=now,
        expires_at=now + timedelta(days=args.days),
    )

    token = sign_entitlement(entitlement, private_key_pem=private_key_pem)
    effective = sorted(entitlement.effective_modules())

    print(f"Licence émise pour tenant={entitlement.tenant_id!r}")
    print(f"  license_id  : {entitlement.license_id}")
    print(f"  tier        : {entitlement.tier}")
    print(f"  options     : {args.modules or '(aucune)'}")
    print(f"  effective_modules : {effective}")
    print(f"  issued_at   : {entitlement.issued_at.isoformat()}")
    print(f"  expires_at  : {entitlement.expires_at.isoformat()}")
    print()
    print("--- JWT (ENTITLEMENT_LICENSE_JWT ou contenu du fichier ENTITLEMENT_LICENSE_FILE) ---")
    print(token)


if __name__ == "__main__":
    main()
