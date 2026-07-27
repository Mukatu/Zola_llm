"""Tests de la conversion markdown -> texte de `scripts/extract_owasp.py`.

Aucun réseau ici : on prouve la fonction de conversion sur une fixture markdown
en dur (2-3 sections factices), pas sur les vraies archives OWASP.
"""

from __future__ import annotations

import io
import sys
import tarfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from extract_owasp import (
    _prefixer_exigences_asvs,
    extraire_asvs,
    formater_section,
    markdown_vers_texte,
)

FIXTURE_MD = """# Fixture Cheat Sheet

## Introduction

This is a **critical** cheat sheet about *injection* attacks. See [OWASP](https://owasp.org) for details.

## Steps

- Validate input
- Use `parameterized` queries

```python
print("hello")
```

## References

- [Reference One](https://example.com/one)
"""


def test_headers_conserves_avec_soulignement() -> None:
    """Les titres # et ## sont conservés en texte, dièses retirés, soulignés."""
    texte = markdown_vers_texte(FIXTURE_MD)
    lignes = texte.splitlines()

    assert "Fixture Cheat Sheet" in lignes
    idx_h1 = lignes.index("Fixture Cheat Sheet")
    assert lignes[idx_h1 + 1] == "=" * len("Fixture Cheat Sheet")

    assert "Introduction" in lignes
    idx_h2 = lignes.index("Introduction")
    assert lignes[idx_h2 + 1] == "-" * len("Introduction")

    assert "#" not in texte


def test_emphases_et_code_inline_nettoyes() -> None:
    """Gras/italique/code inline perdent leurs marqueurs mais gardent le texte."""
    texte = markdown_vers_texte(FIXTURE_MD)

    assert "**" not in texte
    assert "critical" in texte
    assert "*injection*" not in texte
    assert "injection" in texte
    assert "`parameterized`" not in texte
    assert "parameterized" in texte


def test_liens_convertis_texte_plus_url() -> None:
    """[texte](url) devient "texte (url)", pas de crochets/parenthèses markdown."""
    texte = markdown_vers_texte(FIXTURE_MD)

    assert "[OWASP]" not in texte
    assert "OWASP (https://owasp.org)" in texte
    assert "[Reference One](https://example.com/one)" not in texte
    assert "Reference One (https://example.com/one)" in texte


def test_listes_uniformisees_avec_puce() -> None:
    """Les puces markdown (-, *, 1.) deviennent une puce '-' uniforme."""
    texte = markdown_vers_texte(FIXTURE_MD)

    assert "- Validate input" in texte
    assert "- Use parameterized queries" in texte


def test_bloc_code_conserve_sans_marqueurs() -> None:
    """Le contenu d'un bloc ```python ... ``` est conservé, indenté, sans les ```."""
    texte = markdown_vers_texte(FIXTURE_MD)

    assert "```" not in texte
    assert 'print("hello")' in texte


def test_formater_section_ajoute_bandeau_et_retire_h1_redondant() -> None:
    """formater_section encadre d'un titre explicite et retire le H1 du corps
    (déjà porté par le bandeau, pour ne pas le dupliquer)."""
    section = formater_section("A01:2021 -- Broken Access Control", FIXTURE_MD)
    lignes = section.splitlines()

    assert lignes[0] == "=" * 80
    assert lignes[1] == "A01:2021 -- Broken Access Control"
    assert lignes[2] == "=" * 80

    # Le H1 d'origine ("Fixture Cheat Sheet") ne doit plus apparaître : le
    # bandeau explicite en tient déjà lieu.
    assert "Fixture Cheat Sheet" not in section
    # Mais le reste du corps (H2 et contenu) est bien présent.
    assert "Introduction" in section
    assert "critical" in section


# --------------------------------------------------------------------------
# Mode ASVS (chapitres + préfixage des identifiants d'exigence).
# --------------------------------------------------------------------------
def _tar_en_memoire(fichiers: dict[str, str]) -> tarfile.TarFile:
    """Construit un tarball en mémoire (aucun disque, aucun réseau) pour tester
    `extraire_asvs` sur une fixture qui imite la forme d'un tarball GitHub
    (un dossier racine, ici `ASVS-5.0.0_release`)."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tar:
        for nom, contenu in fichiers.items():
            donnees = contenu.encode("utf-8")
            info = tarfile.TarInfo(name=nom)
            info.size = len(donnees)
            tar.addfile(info, io.BytesIO(donnees))
    buf.seek(0)
    return tarfile.open(fileobj=buf, mode="r")


def test_prefixer_exigences_asvs_ajoute_v() -> None:
    """`**1.2.3**` (forme courte du markdown source) devient `**V1.2.3**`
    (désignation complète, citable seule hors du contexte du titre de chapitre)."""
    md = "| # | Description | Level |\n| **1.2.3** | Verify something. | 1 |\n"

    resultat = _prefixer_exigences_asvs(md)

    assert "**V1.2.3**" in resultat
    assert "**1.2.3**" not in resultat


def test_extraire_asvs_concatene_chapitres_dans_ordre_et_garde_les_espaces() -> None:
    """Sur 2 chapitres factices, `extraire_asvs` les concatène dans l'ordre des
    noms de fichiers, garde les espaces entre les mots (contrairement au PDF
    ASVS, dont l'extraction pypdf est cassée) et rend l'exigence sous sa forme
    complète (`V1.1.1 — ...`)."""
    racine = "ASVS-5.0.0_release"
    fichiers = {
        f"{racine}/5.0/en/0x01-Frontispiece.md": "# Frontispiece\n\nIntro text, words well spaced.\n",
        f"{racine}/5.0/en/0x10-V1-Encoding-and-Sanitization.md": (
            "# V1 Encoding and Sanitization\n\n"
            "## V1.1 Encoding and Sanitization Architecture\n\n"
            "| # | Description | Level |\n"
            "| :---: | :--- | :---: |\n"
            "| **1.1.1** | Verify that spacing is kept intact. | 2 |\n"
        ),
    }
    tar = _tar_en_memoire(fichiers)
    try:
        texte = extraire_asvs(tar)
    finally:
        tar.close()

    assert texte.index("Frontispiece") < texte.index("V1 Encoding and Sanitization")
    assert "V1.1.1 — Verify that spacing is kept intact." in texte
    assert "Intro text, words well spaced." in texte
    assert "OWASP APPLICATION SECURITY VERIFICATION STANDARD" in texte
