#!/usr/bin/env python
"""Exécute le manifeste d'ingestion RAG (`ingest_manifest.yml`).

Parcourt les corpus déclarés et dispatche vers le bon script :
- ``method: hf_dataset`` → ``ingest_ohada.py`` (routage OHADA)
- ``method: pdf``        → ``ingest_pdf.py`` (URL officielle)

Par défaut, ne traite que les corpus ``status: ready``. Toujours commencer par
``--dry-run``. Nécessite bge-m3 baké (cf. docs/RAG_INGESTION.md).

Exemples :
    python scripts/ingest_from_manifest.py --dry-run
    python scripts/ingest_from_manifest.py --only sycebnl_acte,cgi_cg_tome1
    python scripts/ingest_from_manifest.py --status all --dry-run
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import yaml

SCRIPTS_DIR = Path(__file__).resolve().parent
DEFAULT_MANIFEST = SCRIPTS_DIR.parent / "ingest_manifest.yml"


def _construire_commande(c: dict, defaults: dict, dry_run: bool) -> list[str]:
    """Construit la commande d'ingestion pour un corpus."""
    method = c.get("method")
    if method == "hf_dataset":
        cmd = [sys.executable, str(SCRIPTS_DIR / "ingest_ohada.py")]
        if c.get("actes"):
            cmd += ["--actes", str(c["actes"])]
    elif method == "pdf":
        if not c.get("url"):
            raise ValueError(f"{c['id']} : method=pdf sans url")
        cmd = [
            sys.executable,
            str(SCRIPTS_DIR / "ingest_pdf.py"),
            "--schema",
            c["schema"],
            "--source-id",
            c["id"],
            "--tags",
            ",".join(c["tags"]),
            "--pii",
            str(c.get("pii", defaults.get("pii", "none"))),
        ]
        # `file` = texte déjà préparé localement (scan réocérisé par ocr_scan.py).
        # On l'ingère tel quel, mais la provenance déclarée reste l'URL officielle
        # pour que les citations remontent au texte de référence, pas à un fichier
        # du dépôt.
        if c.get("file"):
            cmd += ["--file", str(SCRIPTS_DIR.parent / c["file"]), "--source-uri", c["url"]]
        else:
            cmd += ["--url", c["url"]]
    else:
        raise ValueError(f"{c.get('id')} : method inconnue {method!r}")
    if dry_run:
        cmd.append("--dry-run")
    return cmd


def main() -> int:
    p = argparse.ArgumentParser(description="Exécute le manifeste d'ingestion RAG")
    p.add_argument("--manifest", default=str(DEFAULT_MANIFEST), help="chemin du manifeste YAML")
    p.add_argument("--dry-run", action="store_true", help="propage --dry-run à chaque ingestion")
    p.add_argument("--only", default="", help="ids séparés par des virgules (défaut : tous)")
    p.add_argument(
        "--status",
        default="ready",
        choices=["ready", "pending", "all"],
        help="filtrer par statut (défaut : ready)",
    )
    args = p.parse_args()

    data = yaml.safe_load(Path(args.manifest).read_text(encoding="utf-8"))
    defaults = data.get("defaults", {})
    corpora = data.get("corpora", [])
    only = {x.strip() for x in args.only.split(",") if x.strip()}

    selection = [
        c
        for c in corpora
        if (args.status == "all" or c.get("status") == args.status)
        and (not only or c.get("id") in only)
    ]
    print(
        f"Manifeste : {len(selection)} corpus sélectionnés (status={args.status}, dry_run={args.dry_run}).\n"
    )

    resultats: list[tuple[str, str]] = []
    for c in selection:
        cid = c.get("id", "?")
        if c.get("status") == "pending":
            print(f"⏸  {cid} : pending — {c.get('note', 'à cadrer')}")
            resultats.append((cid, "skipped(pending)"))
            continue
        if c.get("verify"):
            print(f"⚠  {cid} : URL à re-vérifier avant ingestion (flag verify).")
        cmd = _construire_commande(c, defaults, args.dry_run)
        print(f"▶  {cid} : {' '.join(cmd[1:])}")
        rc = subprocess.run(cmd, check=False).returncode  # noqa: S603 (cmd construite en interne)
        resultats.append((cid, "ok" if rc == 0 else f"échec(rc={rc})"))
        print()

    print("=== Récapitulatif ===")
    for cid, etat in resultats:
        print(f"  {cid}: {etat}")
    return 0 if all(e in ("ok", "skipped(pending)") for _, e in resultats) else 1


if __name__ == "__main__":
    raise SystemExit(main())
