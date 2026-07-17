#!/usr/bin/env python
"""OCR d'un PDF scanné vers un .txt, avec mesure de qualité.

Complément ponctuel à ``ingest_pdf.py`` pour les textes réglementaires diffusés
en scan image, ou — pire — porteurs d'une couche texte issue d'un mauvais OCR
d'origine (que ``_MIN_TEXTE`` ne détecte pas, cf. docs/sourcing/fintech_reglementaire.md).
On réocérise depuis les images de page, en ignorant la couche texte existante.

    python scripts/ocr_scan.py <url|fichier> <sortie.txt> [--dpi 300]

Affiche un **taux de mots français reconnus** : en dessous de ~25 %, le texte est
inexploitable. Un seuil réglementaire mal océrisé est pire qu'un corpus vide — il
a l'air sourcé. Toujours relire les chiffres avant `validated:true`.
"""

from __future__ import annotations

import argparse
import re
import sys
import tempfile
import unicodedata
import urllib.request
from pathlib import Path

# Un vrai texte réglementaire français en contient massivement.
_COMMUNS = set(
    """le la les de des du et en un une pour par dans sur est sont au aux ne pas
    plus ou son ses leur leurs cette ce avec toute tout qui que article etat etats
    personne personnes fonds client clients autorite autorites present reglement
    conformement alinea titre chapitre section paragraphe""".split()
)
_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0 Safari/537.36 ZolaOS-ingestion"
)


def _norm(mot: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", mot.lower()) if unicodedata.category(c) != "Mn"
    )


def taux_francais(texte: str) -> float:
    """Part de mots français courants — proxy de la qualité d'océrisation."""
    mots = [_norm(m) for m in re.findall(r"[A-Za-zÀ-ÿ']{2,}", texte)]
    if not mots:
        return 0.0
    return sum(1 for m in mots if m in _COMMUNS) / len(mots)


def _telecharger(url: str) -> Path:
    req = urllib.request.Request(url, headers={"User-Agent": _UA, "Referer": url})  # noqa: S310
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    with urllib.request.urlopen(req, timeout=120) as r:  # noqa: S310 (URL d'admin)
        tmp.write(r.read())
    tmp.close()
    return Path(tmp.name)


def main() -> int:
    p = argparse.ArgumentParser(description="OCR d'un PDF scanné vers .txt")
    p.add_argument("source", help="URL http(s) ou chemin local du PDF")
    p.add_argument("sortie", help="fichier .txt de sortie")
    p.add_argument("--dpi", type=int, default=300, help="résolution de rendu (défaut 300)")
    p.add_argument("--lang", default="fra", help="langue tesseract (défaut fra)")
    args = p.parse_args()

    import pytesseract
    from pdf2image import convert_from_path

    chemin = (
        _telecharger(args.source) if args.source.startswith("http") else Path(args.source)
    )
    print(f"Rendu des pages à {args.dpi} dpi…", flush=True)
    pages = convert_from_path(str(chemin), dpi=args.dpi)
    print(f"  {len(pages)} pages", flush=True)

    morceaux: list[str] = []
    for i, img in enumerate(pages):
        morceaux.append(pytesseract.image_to_string(img, lang=args.lang))
        if (i + 1) % 10 == 0:
            print(f"  OCR {i + 1}/{len(pages)}", flush=True)
    texte = "\n\n".join(morceaux)

    Path(args.sortie).write_text(texte, encoding="utf-8")
    t = taux_francais(texte)
    print(f"\n{len(texte)} caractères → {args.sortie}")
    print(f"Mots français reconnus : {t:.0%}")
    if t < 0.25:
        print("⚠  INEXPLOITABLE — ne pas ingérer.")
        return 1
    print("Relire les SEUILS CHIFFRÉS avant de passer validated:true.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
