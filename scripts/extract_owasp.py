#!/usr/bin/env python
"""Extrait OWASP Top 10 (2021), Cheat Sheets et ASVS 5.0.0 en texte brut ingérable.

Top 10 et Cheat Sheets n'existent pas en PDF officiel compilé (cf.
`ingest_manifest.yml`, entrées `owasp_top10` / `owasp_cheatsheets`,
`status: pending`) : le Top 10 2021 est diffusé en ~10 fichiers markdown sur
github.com/OWASP/Top10 (2021/docs/en/), les Cheat Sheets en ~120 fichiers
markdown sur github.com/OWASP/CheatSheetSeries (cheatsheets/*.md). L'ASVS 5.0.0,
lui, a bien un PDF compilé (entrée `owasp_asvs_5_0`, déjà `status: ready`), mais
son extraction pypdf est CASSÉE (espaces perdus entre les mots : « Application
SecurityVerification Standard Version5.0.0 ») — on repart donc, comme pour les
deux autres, de sa source markdown (github.com/OWASP/ASVS, tag `v5.0.0_release`,
`5.0/en/0x*.md`, 27 chapitres : frontispice, chapitres V1-V17, annexes).

Ce script télécharge les tarballs GitHub (ou lit une archive locale déjà
téléchargée via `--top10-archive`/`--cheatsheets-archive`/`--asvs-archive`),
concatène les fichiers pertinents dans l'ordre, nettoie le markdown en texte
lisible, et produit des .txt au même format que `data/fintech/ocr/*.txt` (UTF-8,
texte brut structuré par titres) — ingérables tels quels par :

    python scripts/ingest_pdf.py --file data/cyber/owasp_top10_2021.txt \
        --source-uri https://owasp.org/Top10/ --schema rag_cyber \
        --source-id owasp_top10 --tags framework:owasp,scope:international,...

Ne PAS passer `--chunker legal_article` sur ces corpus : ce ne sont pas des
articles de loi, le chunker par défaut (fenêtre glissante) s'applique.

Licence des sources : CC BY-SA 4.0 — © OWASP Foundation. Toute réutilisation
externe de ces .txt doit conserver l'attribution OWASP (cf. NOTICE /
THIRD_PARTY_LICENSES.md).

Idempotent : ré-exécuter régénère les mêmes fichiers depuis les mêmes sources
(pas d'accumulation, écrasement simple).

Par défaut (aucun flag `--top10`/`--cheatsheets`/`--asvs`), seuls Top 10 et
Cheat Sheets sont générés (comportement historique inchangé) : `--asvs` est
opt-in, à demander explicitement.

Exemples :
    python scripts/extract_owasp.py
    python scripts/extract_owasp.py --top10-archive /tmp/top10.tar.gz
    python scripts/extract_owasp.py --asvs --asvs-archive /tmp/asvs.tar.gz
"""

from __future__ import annotations

import argparse
import io
import re
import tarfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT_DIR = ROOT / "data" / "cyber"

TOP10_TARBALL_URL = "https://github.com/OWASP/Top10/archive/refs/heads/master.tar.gz"
CHEATSHEETS_TARBALL_URL = (
    "https://github.com/OWASP/CheatSheetSeries/archive/refs/heads/master.tar.gz"
)
# ATTENTION : le tag Git n'est PAS "v5.0.0" (qui n'existe pas) mais
# "v5.0.0_release" (constaté via l'API GitHub `/repos/OWASP/ASVS/tags`).
ASVS_TARBALL_URL = "https://github.com/OWASP/ASVS/archive/refs/tags/v5.0.0_release.tar.gz"

# Chemin (relatif à la racine du tarball) des 10 catégories 2021, en anglais,
# dans l'ordre officiel A01 → A10 (A11 "Next Steps" exclu : ce n'est pas une
# catégorie de risque, cf. github.com/OWASP/Top10/tree/master/2021/docs/en).
TOP10_CATEGORIES: list[tuple[str, str]] = [
    ("A01_2021-Broken_Access_Control.md", "A01:2021 — Broken Access Control"),
    ("A02_2021-Cryptographic_Failures.md", "A02:2021 — Cryptographic Failures"),
    ("A03_2021-Injection.md", "A03:2021 — Injection"),
    ("A04_2021-Insecure_Design.md", "A04:2021 — Insecure Design"),
    ("A05_2021-Security_Misconfiguration.md", "A05:2021 — Security Misconfiguration"),
    (
        "A06_2021-Vulnerable_and_Outdated_Components.md",
        "A06:2021 — Vulnerable and Outdated Components",
    ),
    (
        "A07_2021-Identification_and_Authentication_Failures.md",
        "A07:2021 — Identification and Authentication Failures",
    ),
    (
        "A08_2021-Software_and_Data_Integrity_Failures.md",
        "A08:2021 — Software and Data Integrity Failures",
    ),
    (
        "A09_2021-Security_Logging_and_Monitoring_Failures.md",
        "A09:2021 — Security Logging and Monitoring Failures",
    ),
    (
        "A10_2021-Server-Side_Request_Forgery_(SSRF).md",
        "A10:2021 — Server-Side Request Forgery (SSRF)",
    ),
]
TOP10_PREFIX = "2021/docs/en/"

# Chapitres ASVS 5.0.0 (anglais) : frontispice/préface (0x01-0x05), chapitres
# d'exigences V1-V17 (0x10-0x26), annexes (0x90-0x94). Les noms de fichiers,
# zéro-paddés en hexadécimal, se trient déjà dans l'ordre du document — pas
# besoin d'une liste explicite comme pour Top10 (cf. `extraire_asvs`).
ASVS_PREFIX = "5.0/en/"

_UA = "Mozilla/5.0 (ZolaOS extraction bot)"

ATTRIBUTION_TOP10 = (
    "Source : OWASP Top 10:2021 (github.com/OWASP/Top10, 2021/docs/en/).\n"
    "Licence CC BY-SA 4.0 — (c) OWASP Foundation. Attribution requise en cas de\n"
    "réutilisation externe (cf. NOTICE / THIRD_PARTY_LICENSES.md)."
)
ATTRIBUTION_CHEATSHEETS = (
    "Source : OWASP Cheat Sheet Series (github.com/OWASP/CheatSheetSeries,\n"
    "cheatsheets/*.md). Licence CC BY-SA 4.0 — (c) OWASP Foundation. Attribution\n"
    "requise en cas de réutilisation externe (cf. NOTICE / THIRD_PARTY_LICENSES.md)."
)
ATTRIBUTION_ASVS = (
    "Source : OWASP Application Security Verification Standard 5.0.0\n"
    "(github.com/OWASP/ASVS, tag v5.0.0_release, 5.0/en/). Licence CC BY-SA 4.0\n"
    "— (c) OWASP Foundation. Attribution requise en cas de réutilisation externe\n"
    "(cf. NOTICE / THIRD_PARTY_LICENSES.md). Extrait depuis le markdown source\n"
    "(pas le PDF officiel : son extraction pypdf perd les espaces entre les mots)."
)

_SEPARATEUR = "=" * 80

# --------------------------------------------------------------------------
# Conversion markdown → texte brut lisible.
#
# Règles volontairement simples (pas de dépendance à un parseur markdown
# complet — ni `markdown`, ni `mistune` ne sont installés dans ce dépôt) :
# suffisant pour du markdown GitHub standard (titres, listes, gras/italique,
# liens, code), qui est tout ce qu'utilisent le Top 10 et les Cheat Sheets.
# --------------------------------------------------------------------------
_RE_HEADER = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
_RE_BOLD = re.compile(r"\*\*(.+?)\*\*|__(.+?)__")
_RE_ITALIC = re.compile(r"(?<!\*)\*([^*\n]+?)\*(?!\*)|(?<!_)_([^_\n]+?)_(?!_)")
_RE_INLINE_CODE = re.compile(r"`([^`]+)`")
_RE_IMAGE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
_RE_LINK = re.compile(r"\[([^\]]*)\]\(([^)]+)\)")
_RE_ATTR_LIST = re.compile(r"\{:[^}]*\}")
_RE_HR = re.compile(r"^\s*(-{3,}|\*{3,}|_{3,})\s*$")
_RE_BULLET = re.compile(r"^(\s*)[-*+]\s+(.*)$")
_RE_NUM_LIST = re.compile(r"^(\s*)\d+[.)]\s+(.*)$")
_RE_TABLE_ROW = re.compile(r"^\s*\|.*\|\s*$")
_RE_TABLE_SEP = re.compile(r"^\s*\|?[\s:|-]+\|?\s*$")


def _nettoyer_inline(texte: str) -> str:
    """Retire les marqueurs markdown inline (gras, italique, code, liens, images)."""
    texte = _RE_ATTR_LIST.sub("", texte)
    texte = _RE_IMAGE.sub("", texte)
    texte = _RE_LINK.sub(
        lambda m: f"{m.group(1)} ({m.group(2)})" if m.group(1) else m.group(2), texte
    )
    texte = _RE_INLINE_CODE.sub(r"\1", texte)
    texte = _RE_BOLD.sub(lambda m: m.group(1) or m.group(2), texte)
    texte = _RE_ITALIC.sub(lambda m: m.group(1) or m.group(2), texte)
    return texte.strip()


def _nettoyer_ligne_table(ligne: str) -> str:
    """Convertit une ligne de tableau markdown (`| a | b |`) en texte espacé."""
    cellules = [c.strip() for c in ligne.strip().strip("|").split("|")]
    return " — ".join(_nettoyer_inline(c) for c in cellules if c.strip())


def markdown_vers_texte(md: str) -> str:
    """Convertit un texte markdown en texte brut lisible.

    - Titres ``#``..``######`` → ligne de texte soulignée (``=`` niveau 1,
      ``-`` niveaux suivants), dièses retirés.
    - Emphases (``**gras**``, ``*italique*``, `` `code` ``) → texte nu.
    - Liens ``[texte](url)`` → ``texte (url)`` ; images ``![alt](url)`` → retirées
      (pas de valeur en RAG texte).
    - Blocs de code (```` ``` ````, avec ou sans langage) → contenu conservé,
      indenté de 4 espaces, marqueurs de clôture retirés.
    - Listes ``-``/``*``/``1.`` → puce ``-`` uniforme.
    - Tableaux → une ligne par rangée, cellules jointes par ``—``, ligne de
      séparation (``|---|---|``) retirée.
    - Lignes de séparation ``---`` et badges image (``[![...]``) → retirés.
    """
    lignes_source = md.replace("\r\n", "\n").split("\n")
    sortie: list[str] = []
    dans_code = False
    for ligne in lignes_source:
        brute = ligne.rstrip()

        if brute.strip().startswith("```"):
            dans_code = not dans_code
            continue
        if dans_code:
            sortie.append(f"    {brute}")
            continue

        if _RE_HR.match(brute) or brute.strip().startswith("[!["):
            continue

        if _RE_TABLE_SEP.match(brute) and "|" in brute:
            continue
        if _RE_TABLE_ROW.match(brute):
            ligne_table = _nettoyer_ligne_table(brute)
            if ligne_table:
                sortie.append(ligne_table)
            continue

        m = _RE_HEADER.match(brute)
        if m:
            niveau = len(m.group(1))
            texte = _nettoyer_inline(m.group(2))
            sortie.append("")
            sortie.append(texte)
            sortie.append(("=" if niveau == 1 else "-") * max(len(texte), 3))
            sortie.append("")
            continue

        m = _RE_BULLET.match(brute) or _RE_NUM_LIST.match(brute)
        if m:
            indent, contenu = m.groups()
            sortie.append(f"{indent}- {_nettoyer_inline(contenu)}")
            continue

        sortie.append(_nettoyer_inline(brute))

    texte = "\n".join(sortie)
    texte = re.sub(r"\n{3,}", "\n\n", texte)
    return texte.strip() + "\n"


def _retirer_h1_initial(md: str) -> str:
    """Retire le premier titre de niveau 1 (redondant : `formater_section` en
    fournit un déjà, propre, dans le bandeau de section)."""
    lignes = md.replace("\r\n", "\n").split("\n")
    i = 0
    while i < len(lignes) and lignes[i].strip() == "":
        i += 1
    if i < len(lignes) and re.match(r"^#\s+", lignes[i].strip()):
        return "\n".join(lignes[i + 1 :])
    return md


def formater_section(titre: str, corps_md: str) -> str:
    """Encadre une section (catégorie Top 10 ou cheat sheet) avec un titre clair."""
    corps = markdown_vers_texte(_retirer_h1_initial(corps_md))
    return f"{_SEPARATEUR}\n{titre}\n{_SEPARATEUR}\n\n{corps}\n"


def _titre_depuis_markdown(md: str) -> str | None:
    for ligne in md.splitlines():
        m = re.match(r"^#\s+(.+)$", ligne.strip())
        if m:
            return _nettoyer_inline(m.group(1))
    return None


def _titre_depuis_nom_fichier(chemin: str) -> str:
    return Path(chemin).stem.replace("_", " ")


_RE_ASVS_REQ_ID = re.compile(r"\*\*(\d+\.\d+\.\d+)\*\*")


def _prefixer_exigences_asvs(md: str) -> str:
    """Préfixe les identifiants d'exigence des tableaux ASVS par ``V``.

    Le markdown source numérote chaque ligne d'exigence en gras dans une forme
    courte (``**1.2.3**``, à l'intérieur du chapitre ``V1``) ; la désignation
    complète et citable telle qu'utilisée partout ailleurs dans le document
    (biblio, mappings CWE, texte de ce standard) est ``V1.2.3``. Le chunker
    générique (fenêtre glissante) ne préserve pas forcément le titre de
    chapitre dans le même chunk qu'une ligne d'exigence : sans ce préfixe, un
    chunk isolé contenant juste ``1.2.3 — Verify that…`` redevient ambigu
    (quel chapitre ?). Sans effet en dehors des tableaux d'exigences (le motif
    ``**N.N.N**`` n'apparaît pas ailleurs dans les chapitres ASVS).
    """
    return _RE_ASVS_REQ_ID.sub(lambda m: f"**V{m.group(1)}**", md)


# --------------------------------------------------------------------------
# Récupération des sources (tarballs GitHub).
# --------------------------------------------------------------------------
def _telecharger(url: str, tentatives: int = 5) -> bytes:
    """Télécharge une URL en mémoire, avec réessais sur erreur réseau transitoire."""
    req = urllib.request.Request(url, headers={"User-Agent": _UA})  # noqa: S310
    dernier: OSError | None = None
    for essai in range(tentatives):
        try:
            with urllib.request.urlopen(  # noqa: S310 (URL officielle GitHub)
                req, timeout=120
            ) as r:
                return r.read()
        except OSError as e:
            dernier = e
            time.sleep(3 * (essai + 1))
    raise RuntimeError(f"Téléchargement échoué après {tentatives} tentatives : {url}") from dernier


def _ouvrir_tar(source: str) -> tarfile.TarFile:
    """Ouvre un tarball GitHub (`.tar.gz`), depuis une URL http(s) ou un fichier local."""
    if source.startswith("http://") or source.startswith("https://"):
        return tarfile.open(fileobj=io.BytesIO(_telecharger(source)), mode="r:gz")
    return tarfile.open(source, mode="r:gz")


def _repertoire_racine(tar: tarfile.TarFile) -> str:
    """Nom du dossier racine du tarball GitHub (ex. ``Top10-master``)."""
    return tar.getnames()[0].split("/", 1)[0]


def extraire_top10(tar: tarfile.TarFile) -> str:
    """Concatène les 10 catégories A01-A10 du Top 10:2021 (anglais) en un texte."""
    racine = _repertoire_racine(tar)
    sections = [
        "OWASP TOP 10:2021 — THE TEN MOST CRITICAL WEB APPLICATION SECURITY RISKS\n\n"
        f"{ATTRIBUTION_TOP10}\n"
    ]
    for nom_fichier, titre in TOP10_CATEGORIES:
        chemin = f"{racine}/{TOP10_PREFIX}{nom_fichier}"
        membre = tar.extractfile(chemin)
        if membre is None:
            raise FileNotFoundError(f"Fichier introuvable dans le tarball : {chemin}")
        md = membre.read().decode("utf-8")
        sections.append(formater_section(titre, md))
    return "\n".join(sections).rstrip() + "\n"


def extraire_cheatsheets(tar: tarfile.TarFile) -> str:
    """Concatène tous les fichiers `cheatsheets/*.md` de CheatSheetSeries."""
    racine = _repertoire_racine(tar)
    prefixe = f"{racine}/cheatsheets/"
    noms = sorted(
        n
        for n in tar.getnames()
        if n.startswith(prefixe) and n.endswith(".md") and "/" not in n[len(prefixe) :]
    )
    if not noms:
        raise RuntimeError("Aucun cheat sheet (cheatsheets/*.md) trouvé dans l'archive.")
    sections = [
        "OWASP CHEAT SHEET SERIES\n\n"
        f"{ATTRIBUTION_CHEATSHEETS}\n\nSommaire : {len(noms)} fiches, ordre alphabétique.\n"
    ]
    for nom in noms:
        membre = tar.extractfile(nom)
        if membre is None:
            continue
        md = membre.read().decode("utf-8")
        titre = _titre_depuis_markdown(md) or _titre_depuis_nom_fichier(nom)
        sections.append(formater_section(titre, md))
    return "\n".join(sections).rstrip() + "\n"


def extraire_asvs(tar: tarfile.TarFile) -> str:
    """Concatène les 27 chapitres markdown de l'ASVS 5.0.0 (anglais) en un texte."""
    racine = _repertoire_racine(tar)
    prefixe = f"{racine}/{ASVS_PREFIX}"
    noms = sorted(
        n
        for n in tar.getnames()
        if n.startswith(prefixe) and n.endswith(".md") and "/" not in n[len(prefixe) :]
    )
    if not noms:
        raise RuntimeError(f"Aucun chapitre ASVS (*.md) trouvé sous {prefixe} dans l'archive.")
    sections = [
        "OWASP APPLICATION SECURITY VERIFICATION STANDARD (ASVS) 5.0.0\n\n"
        f"{ATTRIBUTION_ASVS}\n\nSommaire : {len(noms)} chapitres (frontispice, "
        "chapitres d'exigences V1-V17, annexes), ordre du document.\n"
    ]
    for nom in noms:
        membre = tar.extractfile(nom)
        if membre is None:
            continue
        md = _prefixer_exigences_asvs(membre.read().decode("utf-8"))
        titre = _titre_depuis_markdown(md) or _titre_depuis_nom_fichier(nom)
        sections.append(formater_section(titre, md))
    return "\n".join(sections).rstrip() + "\n"


def main() -> int:
    p = argparse.ArgumentParser(
        description="Extrait OWASP Top 10 (2021) et OWASP Cheat Sheets en .txt ingérables",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--top10", action="store_true", help="génère owasp_top10_2021.txt")
    p.add_argument("--cheatsheets", action="store_true", help="génère owasp_cheatsheets.txt")
    p.add_argument(
        "--asvs",
        action="store_true",
        help="génère owasp_asvs_5_0.txt (opt-in : absent du défaut sans flag, "
        "pour ne pas changer le comportement historique Top10+Cheatsheets)",
    )
    p.add_argument(
        "--top10-archive",
        default=None,
        help="tarball local du dépôt OWASP/Top10 (.tar.gz) ; sinon téléchargé depuis GitHub",
    )
    p.add_argument(
        "--cheatsheets-archive",
        default=None,
        help="tarball local du dépôt OWASP/CheatSheetSeries (.tar.gz) ; sinon téléchargé",
    )
    p.add_argument(
        "--asvs-archive",
        default=None,
        help="tarball local du dépôt OWASP/ASVS tag v5.0.0_release (.tar.gz) ; sinon téléchargé",
    )
    p.add_argument(
        "--out-dir",
        default=str(DEFAULT_OUT_DIR),
        help="répertoire de sortie (défaut : data/cyber)",
    )
    args = p.parse_args()

    if not (args.top10 or args.cheatsheets or args.asvs):
        args.top10 = args.cheatsheets = (
            True  # défaut inchangé : Top10 + Cheatsheets (ASVS = opt-in)
        )

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.top10:
        print("OWASP Top 10:2021...")
        with _ouvrir_tar(args.top10_archive or TOP10_TARBALL_URL) as tar:
            texte = extraire_top10(tar)
        chemin = out_dir / "owasp_top10_2021.txt"
        chemin.write_text(texte, encoding="utf-8")
        print(f"  {len(texte)} caracteres -> {chemin}")

    if args.cheatsheets:
        print("OWASP Cheat Sheet Series...")
        with _ouvrir_tar(args.cheatsheets_archive or CHEATSHEETS_TARBALL_URL) as tar:
            texte = extraire_cheatsheets(tar)
        chemin = out_dir / "owasp_cheatsheets.txt"
        chemin.write_text(texte, encoding="utf-8")
        print(f"  {len(texte)} caracteres -> {chemin}")

    if args.asvs:
        print("OWASP ASVS 5.0.0...")
        with _ouvrir_tar(args.asvs_archive or ASVS_TARBALL_URL) as tar:
            texte = extraire_asvs(tar)
        chemin = out_dir / "owasp_asvs_5_0.txt"
        chemin.write_text(texte, encoding="utf-8")
        print(f"  {len(texte)} caracteres -> {chemin}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
