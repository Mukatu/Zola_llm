"""Ingestion du corpus réglementaire fintech (`rag_fintech`).

Traite les fichiers de ``data/fintech/`` (ou un chemin passé en argument) et les
ingère dans le schéma ``rag_fintech``. Corpus **public** (COBAC/GABAC/BEAC) →
``PIIRedactionPolicy.NONE``. Idempotent (contrainte unique (source_uri, chunk)).

    python scripts/ingest_fintech.py [chemin]

Cf. docs/sourcing/fintech_reglementaire.md pour les sources officielles à
récupérer et la convention de tags (`validated:true` réservé aux textes vérifiés).
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from zolaos.rag.ingest import ingest_file
from zolaos.security.pii import PIIRedactionPolicy

DEFAULT_DIR = Path(__file__).resolve().parent.parent / "data" / "fintech"
SUPPORTED = {".txt", ".md", ".pdf", ".html", ".htm", ".docx"}
BASE_TAGS = ["country:cg", "country:cemac", "module:orientation", "validated:false"]


async def main(target: Path) -> int:
    files = (
        [target]
        if target.is_file()
        else sorted(p for p in target.rglob("*") if p.suffix.lower() in SUPPORTED)
    )
    if not files:
        print(f"Aucun fichier à ingérer dans {target}")
        return 0
    total = 0
    for f in files:
        n = await ingest_file(
            path=f,
            schema="rag_fintech",
            tags=BASE_TAGS,
            pii_policy=PIIRedactionPolicy.NONE,
            source_id=f.stem,
        )
        total += n
        print(f"  {f.name}: {n} chunk(s)")
    print(f"Total ingéré : {total} chunk(s) dans rag_fintech.")
    return total


if __name__ == "__main__":
    arg = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DIR
    asyncio.run(main(arg))
