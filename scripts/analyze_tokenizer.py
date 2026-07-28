#!/usr/bin/env python
"""Analyse la fragmentation d'un tokenizer sur des échantillons de langues africaines.

Mesure, langue par langue, deux indicateurs standards pour quantifier le
« piège tokenizer bantou » (lot L2.2, `docs/CHAMPION_ROADMAP.md`) :

- **fertility** = nombre de tokens produits / nombre de mots (référence : un
  découpage naïf par espaces/ponctuation, indépendant du tokenizer testé).
  Plus la fertility est haute, plus la langue est sur-segmentée : coût
  d'inférence et de contexte accrus, qualité générative moindre.
- **chars/token** = nombre de caractères / nombre de tokens. Complémentaire :
  une fertility élevée avec un chars/token très bas confirme une
  sur-segmentation en sous-mots très courts (souvent proches du byte-fallback).

Le chargement d'un tokenizer HuggingFace (`transformers.AutoTokenizer`) est
**optionnel et gracieux** : si `transformers` n'est pas installé, si le dépôt
est gated/indisponible ou si le réseau est coupé (poste hors-ligne), le script
**bascule automatiquement sur un tokenizer de repli whitespace** et l'indique
clairement sur stderr. Le but premier de ce script est de prouver la MÉTHODE de
mesure (et de la garder exécutable sans les poids Llama-3) ; les résultats
obtenus avec un vrai tokenizer BPE (Llama-3, Qwen2.5...) sont ceux qui comptent
pour la décision documentée dans `docs/TOKENIZER_AFRICAN.md`.

Échantillons : `data/lang_samples/<code_langue>.txt` (un fichier par langue,
une phrase par ligne, `#` = commentaire). Un jeu de repli est intégré dans ce
script (`_BUILTIN_SAMPLES`) si ce répertoire est introuvable.

Exemples :
    python scripts/analyze_tokenizer.py --help
    python scripts/analyze_tokenizer.py --samples data/lang_samples
    python scripts/analyze_tokenizer.py --samples data/lang_samples \\
        --tokenizer meta-llama/Meta-Llama-3-8B --tokenizer Qwen/Qwen2.5-7B
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

# Mot = suite de caractères alphanumériques Unicode, avec apostrophe interne
# tolérée ("aujourd'hui" = 1 mot). Sert de dénominateur commun, indépendant du
# tokenizer évalué. Limite connue : un mot à trait d'union ("allez-vous") est
# compté comme deux mots — simplification documentée dans docs/TOKENIZER_AFRICAN.md.
_WORD_RE = re.compile(r"\w+(?:['’`]\w+)*", re.UNICODE)

_DEFAULT_SAMPLES_DIR = Path(__file__).resolve().parent.parent / "data" / "lang_samples"

# Repli embarqué, utilisé uniquement si --samples est absent ET que
# data/lang_samples/ est introuvable (ex. script copié isolément). Contenu
# identique en esprit aux fichiers data/lang_samples/*.txt — voir
# docs/TOKENIZER_AFRICAN.md pour les sources et le niveau de confiance par langue.
_BUILTIN_SAMPLES: dict[str, list[str]] = {
    "fr": [
        "Bonjour, comment allez-vous ?",
        "Je vais bien, merci beaucoup.",
        "Où se trouve la gare la plus proche ?",
        "Il fait très beau aujourd'hui à Brazzaville.",
        "Merci pour votre aide, à bientôt.",
    ],
    "ln": [
        "Mbote.",
        "Sango nini?",
        "Nazali malamu.",
        "Matondi mingi.",
    ],
    "mkw": [
        "Mbote.",
        "Matondo.",
    ],
    "sw": [
        "Habari yako?",
        "Njema sana, asante.",
        "Jina lako nani?",
        "Ninaitwa Zola.",
        "Asante sana kwa msaada wako.",
    ],
    "wo": [
        "Nanga def?",
        "Maa ngi fi rekk.",
        "Jërëjëf.",
    ],
}

LANG_NAMES: dict[str, str] = {
    "fr": "Français",
    "ln": "Lingala",
    "mkw": "Kituba / Munukutuba",
    "sw": "Swahili",
    "wo": "Wolof",
}


@dataclass(frozen=True)
class LangMetrics:
    """Compteurs agrégés pour une langue, sur l'ensemble de ses phrases échantillon."""

    lang: str
    n_samples: int
    n_words: int
    n_chars: int
    n_tokens: int

    @property
    def fertility(self) -> float:
        """Tokens par mot. `nan` si aucun mot (évite une ZeroDivisionError silencieuse)."""
        return self.n_tokens / self.n_words if self.n_words else float("nan")

    @property
    def chars_per_token(self) -> float:
        """Caractères par token. `nan` si aucun token."""
        return self.n_chars / self.n_tokens if self.n_tokens else float("nan")


def count_words(text: str) -> int:
    """Compte les « mots » d'un texte via `_WORD_RE` (référence indépendante du tokenizer)."""
    return len(_WORD_RE.findall(text))


def _whitespace_tokenize(text: str) -> list[str]:
    """Tokenizer de repli : découpe naïve sur les espaces.

    Avertissement méthodologique (voir docs/TOKENIZER_AFRICAN.md) : ce repli NE
    PROUVE PAS la sur-segmentation bantoue — par construction, un « mot »
    (séparé par un espace) y vaut presque toujours un « token », donc la
    fertility mesurée avec ce repli est proche de 1 quelle que soit la langue.
    Il prouve seulement que le pipeline de mesure (fertility, chars/token) est
    correct de bout en bout (cf. tests/test_analyze_tokenizer.py). Pour
    mesurer la vraie fragmentation, il faut un tokenizer BPE réel
    (`--tokenizer <repo_ou_chemin_HF>`).
    """
    return text.split()


def load_tokenizer(name: str | None) -> tuple[str, Callable[[str], int], bool]:
    """Charge un tokenizer par nom/chemin HuggingFace, avec repli whitespace gracieux.

    Args:
        name: nom de dépôt HF (ex. ``meta-llama/Meta-Llama-3-8B``), chemin local,
            ``"whitespace"`` pour forcer explicitement le repli, ou ``None``
            (repli par défaut, aucune tentative réseau).

    Returns:
        Un triplet ``(étiquette, fonction_de_comptage, est_repli)`` où
        ``fonction_de_comptage(texte) -> nombre_de_tokens``.
    """
    if name is None or name == "whitespace":
        return ("whitespace (repli explicite)", lambda t: len(_whitespace_tokenize(t)), True)

    try:
        from transformers import AutoTokenizer
    except ImportError as exc:
        print(
            f"[analyze_tokenizer] 'transformers' indisponible ({exc}) "
            f"— repli whitespace pour '{name}'.",
            file=sys.stderr,
        )
        return (
            f"{name} (repli whitespace — transformers absent)",
            lambda t: len(_whitespace_tokenize(t)),
            True,
        )

    try:
        tok = AutoTokenizer.from_pretrained(name)
    except Exception as exc:
        # Volontairement large : offline, dépôt gated, dépôt inexistant, quota
        # réseau... toute cause doit dégrader vers le repli, jamais planter le script.
        print(
            f"[analyze_tokenizer] échec de chargement du tokenizer '{name}' ({exc}) "
            f"— repli whitespace.",
            file=sys.stderr,
        )
        return (
            f"{name} (repli whitespace — chargement échoué)",
            lambda t: len(_whitespace_tokenize(t)),
            True,
        )

    def _count(text: str) -> int:
        return len(tok.encode(text, add_special_tokens=False))

    return (name, _count, False)


def load_samples(path: Path | None) -> dict[str, list[str]]:
    """Charge les échantillons de texte par langue.

    `path` peut être :
    - un répertoire : un fichier ``<code_langue>.txt`` par langue, une phrase
      par ligne (`#` en début de ligne = commentaire ignoré) ;
    - un fichier : lignes au format ``code_langue<TAB>phrase`` ;
    - `None` : utilise `data/lang_samples/` du dépôt, ou à défaut les
      échantillons intégrés (`_BUILTIN_SAMPLES`).
    """
    candidate = path or _DEFAULT_SAMPLES_DIR

    if candidate.is_dir():
        samples: dict[str, list[str]] = {}
        for txt_file in sorted(candidate.glob("*.txt")):
            lines = [
                line.strip()
                for line in txt_file.read_text(encoding="utf-8").splitlines()
                if line.strip() and not line.strip().startswith("#")
            ]
            if lines:
                samples[txt_file.stem] = lines
        if samples:
            return samples

    elif candidate.is_file():
        samples = {}
        for raw_line in candidate.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "\t" not in line:
                continue
            lang, text = line.split("\t", 1)
            samples.setdefault(lang.strip(), []).append(text.strip())
        if samples:
            return samples

    print(
        f"[analyze_tokenizer] aucun échantillon exploitable dans '{candidate}' "
        f"— utilisation des échantillons intégrés au script.",
        file=sys.stderr,
    )
    return {lang: list(sentences) for lang, sentences in _BUILTIN_SAMPLES.items()}


def analyze(
    samples: dict[str, list[str]], count_tokens: Callable[[str], int]
) -> dict[str, LangMetrics]:
    """Calcule les métriques par langue pour une fonction de comptage de tokens donnée."""
    results: dict[str, LangMetrics] = {}
    for lang, sentences in samples.items():
        n_words = n_chars = n_tokens = 0
        for sentence in sentences:
            n_words += count_words(sentence)
            n_chars += len(sentence)
            n_tokens += count_tokens(sentence)
        results[lang] = LangMetrics(
            lang=lang,
            n_samples=len(sentences),
            n_words=n_words,
            n_chars=n_chars,
            n_tokens=n_tokens,
        )
    return results


def format_table(tokenizer_label: str, metrics: dict[str, LangMetrics]) -> str:
    """Formate les métriques d'un tokenizer en tableau Markdown lisible en console."""
    header = [
        f"### Tokenizer : {tokenizer_label}",
        "",
        "| Langue | Phrases | Mots | Tokens | Fertility (tok/mot) | Chars/token |",
        "|---|---|---|---|---|---|",
    ]
    rows = []
    for lang in sorted(metrics):
        m = metrics[lang]
        name = LANG_NAMES.get(lang, lang)
        rows.append(
            f"| {name} ({lang}) | {m.n_samples} | {m.n_words} | {m.n_tokens} | "
            f"{m.fertility:.2f} | {m.chars_per_token:.2f} |"
        )
    return "\n".join(header + rows)


def build_parser() -> argparse.ArgumentParser:
    """Construit le parseur d'arguments en ligne de commande."""
    parser = argparse.ArgumentParser(
        description=(
            "Mesure la fertility (tokens/mot) et les chars/token d'un ou plusieurs "
            "tokenizers sur des échantillons de langues africaines (lot L2.2)."
        )
    )
    parser.add_argument(
        "--samples",
        type=Path,
        default=None,
        help=(
            "Répertoire (un .txt par langue) ou fichier (lignes 'lang<TAB>texte'). "
            "Défaut : data/lang_samples/ du dépôt, sinon échantillons intégrés."
        ),
    )
    parser.add_argument(
        "--tokenizer",
        action="append",
        default=None,
        metavar="NOM_OU_CHEMIN_HF",
        help=(
            "Nom de dépôt HuggingFace (ex. meta-llama/Meta-Llama-3-8B) ou chemin local "
            "d'un tokenizer à évaluer. Répétable pour comparer plusieurs tokenizers. "
            "Utiliser 'whitespace' pour forcer explicitement le repli. "
            "Défaut si omis : repli whitespace seul (aucune tentative réseau)."
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Écrit les résultats bruts (par tokenizer, par langue) en JSON dans ce fichier.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Point d'entrée CLI."""
    args = build_parser().parse_args(argv)
    samples = load_samples(args.samples)
    tokenizer_names = args.tokenizer or ["whitespace"]

    all_results: dict[str, dict[str, LangMetrics]] = {}
    for name in tokenizer_names:
        label, count_tokens, is_fallback = load_tokenizer(name)
        metrics = analyze(samples, count_tokens)
        all_results[label] = metrics
        print(format_table(label, metrics))
        print()
        if is_fallback:
            print(
                "  -> REPLI WHITESPACE actif : ces chiffres ne mesurent PAS la "
                "fragmentation BPE réelle (voir docs/TOKENIZER_AFRICAN.md).",
                file=sys.stderr,
            )

    if args.output is not None:
        serializable = {
            label: {
                lang: {
                    "n_samples": m.n_samples,
                    "n_words": m.n_words,
                    "n_chars": m.n_chars,
                    "n_tokens": m.n_tokens,
                    "fertility": m.fertility,
                    "chars_per_token": m.chars_per_token,
                }
                for lang, m in metrics.items()
            }
            for label, metrics in all_results.items()
        }
        args.output.write_text(
            json.dumps(serializable, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"Résultats écrits dans {args.output}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
