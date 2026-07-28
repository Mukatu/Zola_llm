"""Harnais d'évaluation TRADUCTION langues africaines (L2.4) — mètre-étalon.

Objectif : disposer d'une mesure AVANT l'entraînement (éval-driven), pour
pouvoir prouver plus tard qu'un Llama-3 adapté (L2.3) traduit mieux vers les
langues africaines cibles (français, swahili, lingala, wolof, haoussa,
amharique) que la base. Sans ce harnais, "meilleur localement" resterait une
affirmation invérifiable.

Réutilise le patron déjà en place dans `tests/eval/eval_engine.py` (L1.6) :

  - Dataset **Pydantic** (`AfricanEvalCase`/`AfricanEvalDataset`) chargé
    depuis YAML — cf. `datasets/african/udhr_pairs.yaml` pour la source
    réelle utilisée et ses limitations documentées.
  - `score_translations()` **PUR** : calcule chrF sur des paires
    (hypothèse, référence) déjà obtenues, sans appeler ni LLM ni réseau.
    Testable à 100% sans réseau (cf. `tests/eval/test_eval_african.py`).
  - `run_african_eval()` **COÛTEUX** : appelle réellement un `LLMClient` pour
    traduire `source_fr` vers chaque langue cible, puis délègue le calcul à
    `score_translations()`. Nécessite un serveur LLM joignable. Gaté dans les
    tests par la variable d'env `ZOLAOS_RUN_AFRICAN_EVAL=1` (même pattern que
    `ZOLAOS_RUN_ENGINE_EVAL` dans `tests/eval/test_engine_eval_live.py`) —
    jamais appelée par défaut.

Métrique : **chrF** (character n-gram F-score, Popović 2015) — préféré à
BLEU pour les langues morphologiquement riches/peu dotées (agglutination
bantoue, mutations consonantiques wolof, etc. — cf.
`docs/sourcing/african_languages.md` §4.3 sur la fragmentation tokenizer).
Utilise `sacrebleu.corpus_chrf` si le paquet est installé ; repli sur une
implémentation maison sinon (`_chrf_score_pure`, testée directement). Dans
cet environnement (`.venv_test`), `sacrebleu` n'est PAS installé — le repli
maison est donc systématiquement celui exercé, pas une branche morte.

Lancer l'éval africaine complète (LLM réel requis) :

    ZOLAOS_RUN_AFRICAN_EVAL=1 .venv_test/Scripts/python.exe -m pytest \
        tests/eval/test_african_eval_live.py -m eval -q --no-cov

Lancer uniquement les tests du HARNAIS (aucun LLM, aucun réseau — CI par défaut) :

    .venv_test/Scripts/python.exe -m pytest tests/eval/test_eval_african.py -q --no-cov
"""

from __future__ import annotations

import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, NamedTuple

import yaml
from pydantic import BaseModel, Field

from zolaos.core.logging import get_logger

_log = get_logger("zolaos.eval.african")

DEFAULT_DATASET_PATH = Path(__file__).parent / "datasets" / "african" / "udhr_pairs.yaml"

# Noms français des langues cibles — utilisés pour construire le prompt de
# traduction dans `run_african_eval`. Codes alignés sur
# `docs/sourcing/african_languages.md` (`lang:{fr|ln|mkw|ktu|sw|wo|ha|am}`).
LANGUAGE_NAMES_FR: dict[str, str] = {
    "sw": "swahili",
    "ln": "lingala",
    "wo": "wolof",
    "ha": "haoussa",
    "am": "amharique",
}


# ----------------------------------------------------------------------------
# Dataset : cas {lang, source_fr, reference}
# ----------------------------------------------------------------------------


class AfricanEvalCase(BaseModel):
    """Un cas vérité-terrain traduction : phrase française source + référence
    traduite dans la langue cible, sourcée (cf. `notes` et l'en-tête du
    fichier YAML pour la provenance exacte de chaque paire)."""

    id: str
    lang: str
    source_fr: str
    reference: str
    notes: str | None = None


class AfricanEvalDataset(BaseModel):
    """Jeu de paires français/langue chargé depuis YAML
    (cf. `datasets/african/udhr_pairs.yaml`)."""

    version: str = "1.0"
    source: str | None = None
    notes: str | None = None
    cases: list[AfricanEvalCase] = Field(min_length=1)

    @classmethod
    def from_yaml(cls, path: str | Path = DEFAULT_DATASET_PATH) -> AfricanEvalDataset:
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(p)
        raw = yaml.safe_load(p.read_text(encoding="utf-8"))
        ds = cls.model_validate(raw)
        _log.info("eval.african.dataset_loaded", path=str(p), cases=len(ds.cases))
        return ds

    @property
    def languages(self) -> set[str]:
        return {c.lang for c in self.cases}


# ----------------------------------------------------------------------------
# Métrique chrF — sacrebleu si dispo, sinon implémentation maison (PURE)
# ----------------------------------------------------------------------------

try:
    import sacrebleu as _sacrebleu

    HAS_SACREBLEU = True
except ImportError:  # pragma: no cover - dépend de l'environnement d'exécution
    _sacrebleu = None
    HAS_SACREBLEU = False


def _char_ngram_counts(s: str, n: int) -> Counter[str]:
    if len(s) < n:
        return Counter()
    return Counter(s[i : i + n] for i in range(len(s) - n + 1))


def _chrf_score_pure(
    hypothesis: str, reference: str, *, n_max: int = 6, beta: float = 2.0
) -> float:
    """Implémentation maison de chrF (Popović 2015), sur [0, 100].

    Précision/rappel calculés par n-gramme de caractères (n=1..n_max, espaces
    retirés au préalable — patron chrF standard), puis moyennés arithmétiquement
    sur les tailles de n-gramme observées avant de combiner en F-bêta
    (bêta=2 par défaut, comme sacrebleu). Ne vise PAS une parité bit-à-bit
    avec `sacrebleu.corpus_chrf` — vise un signal relatif cohérent et
    déterministe (identité -> 100, divergence -> score plus bas), suffisant
    pour comparer base vs modèle adapté (L2.3).
    """
    hyp = "".join(hypothesis.split())
    ref = "".join(reference.split())
    if not hyp and not ref:
        return 100.0
    if not hyp or not ref:
        return 0.0

    precisions: list[float] = []
    recalls: list[float] = []
    for n in range(1, n_max + 1):
        hyp_ngrams = _char_ngram_counts(hyp, n)
        ref_ngrams = _char_ngram_counts(ref, n)
        if not hyp_ngrams and not ref_ngrams:
            continue
        matched = sum((hyp_ngrams & ref_ngrams).values())
        hyp_total = sum(hyp_ngrams.values())
        ref_total = sum(ref_ngrams.values())
        precisions.append(matched / hyp_total if hyp_total else 0.0)
        recalls.append(matched / ref_total if ref_total else 0.0)

    if not precisions:
        # Chaînes plus courtes que n_max des deux côtés : aucun n-gramme
        # commun mesurable -> score nul plutôt qu'une division par zéro.
        return 0.0

    avg_p = sum(precisions) / len(precisions)
    avg_r = sum(recalls) / len(recalls)
    if avg_p == 0.0 and avg_r == 0.0:
        return 0.0

    beta2 = beta * beta
    f_beta = (1 + beta2) * avg_p * avg_r / (beta2 * avg_p + avg_r)
    return f_beta * 100.0


def chrf_score(hypothesis: str, reference: str, *, n_max: int = 6, beta: float = 2.0) -> float:
    """chrF d'une paire (hypothèse, référence), sur [0, 100]. PURE.

    Délègue à `sacrebleu.corpus_chrf` si installé, sinon à `_chrf_score_pure`.
    Les deux cas limites (chaînes vides) sont traités identiquement avant
    délégation pour un comportement homogène quel que soit le backend.
    """
    hyp_stripped = hypothesis.strip()
    ref_stripped = reference.strip()
    if not hyp_stripped and not ref_stripped:
        return 100.0
    if not hyp_stripped or not ref_stripped:
        return 0.0
    if HAS_SACREBLEU:  # pragma: no cover - sacrebleu absent de .venv_test
        result = _sacrebleu.corpus_chrf(
            [hypothesis], [[reference]], char_order=n_max, beta=int(beta)
        )
        return float(result.score)
    return _chrf_score_pure(hypothesis, reference, n_max=n_max, beta=beta)


# ----------------------------------------------------------------------------
# Agrégation PURE — aucun appel réseau/LLM ici
# ----------------------------------------------------------------------------


class TranslationPair(NamedTuple):
    """Une hypothèse à comparer à une référence, pour une langue donnée.

    Produite soit à la main (tests), soit par `run_african_eval` après un
    appel LLM réel.
    """

    case_id: str
    lang: str
    hypothesis: str
    reference: str


def score_translations(pairs: list[TranslationPair]) -> dict[str, Any]:
    """Calcule chrF par paire puis agrège par langue + global. PURE :
    ne fait aucun appel réseau/LLM, se contente de scorer des (hypothèse,
    référence) déjà obtenues par l'appelant (cf. `run_african_eval`).

    Retourne :
        {
            "n": nombre total de paires,
            "chrf_global": chrF moyen toutes langues confondues,
            "by_lang": {lang: {"chrf_mean": ..., "n": ...}},
            "per_case": [{"case_id", "lang", "chrf"}, ...],
        }
    """
    if not pairs:
        return {"n": 0, "chrf_global": 0.0, "by_lang": {}, "per_case": []}

    per_case: list[dict[str, Any]] = []
    scores_by_lang: dict[str, list[float]] = {}
    all_scores: list[float] = []

    for pair in pairs:
        s = chrf_score(pair.hypothesis, pair.reference)
        all_scores.append(s)
        scores_by_lang.setdefault(pair.lang, []).append(s)
        per_case.append({"case_id": pair.case_id, "lang": pair.lang, "chrf": s})

    by_lang = {
        lang: {"chrf_mean": sum(scores) / len(scores), "n": len(scores)}
        for lang, scores in scores_by_lang.items()
    }

    return {
        "n": len(all_scores),
        "chrf_global": sum(all_scores) / len(all_scores),
        "by_lang": by_lang,
        "per_case": per_case,
    }


# ----------------------------------------------------------------------------
# Runner COÛTEUX (appelle réellement un LLMClient.generate)
# ----------------------------------------------------------------------------


@dataclass
class AfricanEvalReport:
    """Résultat d'une passe d'éval africaine complète (traduction + score)."""

    dataset_name: str
    result: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    def render(self) -> str:
        lines = [f"=== Éval africaine: {self.dataset_name} ===", ""]
        for row in self.result.get("per_case", []):
            lines.append(f"{row['case_id']} [{row['lang']}]: chrF={row['chrf']:.1f}")
        lines.append("")
        for lang, agg in sorted(self.result.get("by_lang", {}).items()):
            lines.append(f"  chrF moyen [{lang}] : {agg['chrf_mean']:.1f} (n={agg['n']})")
        lines.append(f"chrF global   : {self.result.get('chrf_global', 0.0):.1f}")
        if self.errors:
            lines.append(f"Erreurs       : {len(self.errors)}")
            for err in self.errors:
                lines.append(f"  - {err}")
        return "\n".join(lines)


def _translation_prompt(source_fr: str, lang: str) -> str:
    name = LANGUAGE_NAMES_FR.get(lang, lang)
    return (
        f"Traduis la phrase suivante du français vers le {name}. "
        "Réponds uniquement avec la traduction, sans aucune explication ni "
        f"guillemets.\n\nPhrase : {source_fr}"
    )


async def run_african_eval(
    cases: list[AfricanEvalCase],
    *,
    llm: object,
    model: str,
    dataset_name: str = DEFAULT_DATASET_PATH.stem,
) -> AfricanEvalReport:
    """Traduit `source_fr` -> `lang` via un vrai `LLMClient.generate(...)`
    pour chaque cas, puis délègue le score à `score_translations()` (PURE).

    `llm` doit exposer `async generate(messages, *, model, options=None) ->
    GenerationResult` (contrat `zolaos.llm.base.LLMClient`) — typé `object`
    ici pour ne pas imposer l'import du module LLM aux tests purs qui
    n'appellent jamais cette fonction.

    COÛTEUX : nécessite un serveur LLM joignable. Jamais appelée par défaut
    dans la suite de tests standard — voir `tests/eval/test_african_eval_live.py`
    (gated `ZOLAOS_RUN_AFRICAN_EVAL`).
    """
    from zolaos.llm.base import Message  # import local : évite la dépendance pour les tests purs

    pairs: list[TranslationPair] = []
    errors: list[str] = []
    for case in cases:
        t0 = time.perf_counter()
        hypothesis = ""
        try:
            result = await llm.generate(  # type: ignore[attr-defined]
                [Message(role="user", content=_translation_prompt(case.source_fr, case.lang))],
                model=model,
            )
            hypothesis = result.content.strip()
        except Exception as exc:  # on continue la passe, on rapporte l'erreur
            err = f"{case.id}: {type(exc).__name__}: {exc}"
            errors.append(err)
            _log.warning("eval.african.case_error", case_id=case.id, error=err)
        latency = time.perf_counter() - t0
        _log.info(
            "eval.african.case_translated",
            case_id=case.id,
            lang=case.lang,
            latency_seconds=round(latency, 2),
        )
        pairs.append(
            TranslationPair(
                case_id=case.id, lang=case.lang, hypothesis=hypothesis, reference=case.reference
            )
        )

    result = score_translations(pairs)
    return AfricanEvalReport(dataset_name=dataset_name, result=result, errors=errors)


__all__ = [
    "DEFAULT_DATASET_PATH",
    "LANGUAGE_NAMES_FR",
    "HAS_SACREBLEU",
    "AfricanEvalCase",
    "AfricanEvalDataset",
    "AfricanEvalReport",
    "TranslationPair",
    "chrf_score",
    "score_translations",
    "run_african_eval",
]
