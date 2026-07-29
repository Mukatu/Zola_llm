"""Génère la paire de clés RS256 de l'entitlement (licence commerciale Polaris).

La clé **PRIVÉE** signe les licences (`scripts/issue_license.py`) et reste
**uniquement chez Polaris** (poste d'émission / futur cockpit cortex) — elle
ne doit JAMAIS être copiée sur une Zolabox. La clé **PUBLIQUE** est déployée
sur chaque box (variable d'environnement `ENTITLEMENT_PUBLIC_KEY`) : elle ne
permet que de VÉRIFIER une licence, jamais d'en forger une (RS256 asymétrique,
cf. `src/zolaos/licensing/entitlement.py`).

Usage ::

    python scripts/gen_entitlement_keys.py \
        --out-private polaris_entitlement_private.pem \
        --out-public  polaris_entitlement_public.pem

Sans ``--out-private``/``--out-public``, les PEM sont imprimés sur stdout
(clé privée d'abord, puis publique), séparés par une ligne de marqueur —
pratique pour un pipe direct vers un coffre-fort de secrets, mais à éviter en
usage interactif (la clé privée resterait dans l'historique du terminal).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

_DEFAULT_KEY_SIZE = 2048


def generate_keypair(*, key_size: int = _DEFAULT_KEY_SIZE) -> tuple[str, str]:
    """Génère une paire RSA et retourne (pem_private, pem_public)."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=key_size)
    pem_private = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")
    pem_public = (
        private_key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode("utf-8")
    )
    return pem_private, pem_public


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Génère la paire de clés RS256 de l'entitlement Polaris.",
    )
    parser.add_argument(
        "--key-size",
        type=int,
        default=_DEFAULT_KEY_SIZE,
        help=f"Taille de la clé RSA en bits (défaut {_DEFAULT_KEY_SIZE}, minimum 2048).",
    )
    parser.add_argument(
        "--out-private",
        default=None,
        help="Fichier de sortie pour la clé PRIVÉE (défaut : stdout). Reste chez Polaris.",
    )
    parser.add_argument(
        "--out-public",
        default=None,
        help="Fichier de sortie pour la clé PUBLIQUE (défaut : stdout). À déployer sur la box.",
    )
    args = parser.parse_args()

    if args.key_size < 2048:
        sys.exit("Refusé : la clé RSA doit faire au moins 2048 bits.")

    pem_private, pem_public = generate_keypair(key_size=args.key_size)

    if args.out_private:
        Path(args.out_private).write_text(pem_private, encoding="utf-8")
        print(f"Clé privée écrite dans {args.out_private} — à garder chez Polaris uniquement.")
    else:
        print("--- CLÉ PRIVÉE (Polaris — émission des licences, jamais sur une box) ---")
        print(pem_private)

    if args.out_public:
        Path(args.out_public).write_text(pem_public, encoding="utf-8")
        print(
            f"Clé publique écrite dans {args.out_public} — à déployer sur la box (ENTITLEMENT_PUBLIC_KEY)."
        )
    else:
        print("--- CLÉ PUBLIQUE (box — vérification, ENTITLEMENT_PUBLIC_KEY) ---")
        print(pem_public)


if __name__ == "__main__":
    main()
