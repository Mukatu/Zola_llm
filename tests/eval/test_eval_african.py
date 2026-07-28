"""Tests du harnais d'éval TRADUCTION langues africaines (L2.4) — aucun LLM,
aucun réseau.

Vérifie :
  - le calcul chrF (`chrf_score`/`_chrf_score_pure`) sur des hypothèses/
    références FACTICES : déterminisme, identité -> 100, divergence -> plus
    bas, cas limites (chaînes vides) sans crash ;
  - l'agrégation par langue + globale (`score_translations`) ;
  - le chargement + la validation du dataset réel
    (`datasets/african/udhr_pairs.yaml`).

Pour la passe complète contre un vrai LLM (traduction réelle), voir
`tests/eval/test_african_eval_live.py` (gated `ZOLAOS_RUN_AFRICAN_EVAL=1`).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.eval.eval_african import (
    DEFAULT_DATASET_PATH,
    AfricanEvalCase,
    AfricanEvalDataset,
    TranslationPair,
    _chrf_score_pure,
    chrf_score,
    score_translations,
)

# ----------------------------------------------------------------------------
# chrF : cas unitaires déterministes
# ----------------------------------------------------------------------------


def test_chrf_identity_is_100() -> None:
    text = "Watu wote wamezaliwa huru, hadhi na haki zao ni sawa."
    assert chrf_score(text, text) == pytest.approx(100.0)


def test_chrf_pure_identity_is_100() -> None:
    """Force explicitement le repli maison (indépendamment de la dispo sacrebleu)."""
    text = "Bato nyonso na mbotama bazali nzomi pe bakokani na limemya pe makoki."
    assert _chrf_score_pure(text, text) == pytest.approx(100.0)


def test_chrf_is_deterministic() -> None:
    hyp = "Doomi aadama yépp dañuy juddu."
    ref = "Doomi aadama yépp dañuy juddu, yam ci tawfeex."
    s1 = chrf_score(hyp, ref)
    s2 = chrf_score(hyp, ref)
    assert s1 == s2


def test_chrf_divergence_scores_lower_than_identity() -> None:
    reference = "Su dai yan-adam, ana haifuwarsu ne duka yantattu."
    identical_score = chrf_score(reference, reference)
    completely_different = chrf_score("Un texte totalement sans rapport en français.", reference)
    assert completely_different < identical_score
    assert identical_score == pytest.approx(100.0)


def test_chrf_partial_overlap_is_between_zero_and_identity() -> None:
    reference = "Watu wote wamezaliwa huru, hadhi na haki zao ni sawa."
    # Hypothèse partiellement correcte (mêmes premiers mots, fin différente).
    partial = "Watu wote wamezaliwa huru, lakini kitu kingine kabisa hapa."
    score = chrf_score(partial, reference)
    assert 0.0 < score < 100.0


def test_chrf_symmetry_not_assumed_but_both_directions_are_sane() -> None:
    """chrF n'est pas symétrique en général (précision vs rappel selon le
    sens hyp/ref) — on vérifie seulement que les deux sens restent dans
    [0, 100] et ne plantent pas."""
    a = "Bonjour le monde"
    b = "Bonjour le monde entier aujourd'hui"
    assert 0.0 <= chrf_score(a, b) <= 100.0
    assert 0.0 <= chrf_score(b, a) <= 100.0


def test_chrf_empty_hypothesis_and_reference_is_100() -> None:
    assert chrf_score("", "") == 100.0
    assert chrf_score("   ", "\n") == 100.0


def test_chrf_empty_hypothesis_nonempty_reference_is_zero() -> None:
    assert chrf_score("", "quelque chose") == 0.0


def test_chrf_empty_reference_nonempty_hypothesis_is_zero() -> None:
    assert chrf_score("quelque chose", "") == 0.0


def test_chrf_pure_handles_strings_shorter_than_n_max_without_crash() -> None:
    # Chaînes plus courtes que n_max=6 caractères : ne doit pas lever de
    # ZeroDivisionError, doit rester dans [0, 100].
    assert 0.0 <= _chrf_score_pure("ab", "ab") <= 100.0
    assert _chrf_score_pure("ab", "ab") == pytest.approx(100.0)
    assert 0.0 <= _chrf_score_pure("ab", "cd") <= 100.0


def test_chrf_score_bounded_in_0_100_on_arbitrary_pairs() -> None:
    pairs = [
        ("Tous les êtres humains naissent libres.", "Watu wote wamezaliwa huru."),
        ("", "Wote wamejaliwa akili na dhamiri."),
        ("Bato nyonso na mbotama.", "Bato nyonso na mbotama."),
    ]
    for hyp, ref in pairs:
        score = chrf_score(hyp, ref)
        assert 0.0 <= score <= 100.0


# ----------------------------------------------------------------------------
# score_translations : agrégation PURE par langue + globale
# ----------------------------------------------------------------------------


def test_score_translations_empty_pairs_returns_zeroed_dict() -> None:
    result = score_translations([])
    assert result == {"n": 0, "chrf_global": 0.0, "by_lang": {}, "per_case": []}


def test_score_translations_single_language_perfect_match() -> None:
    ref = "Watu wote wamezaliwa huru, hadhi na haki zao ni sawa."
    pairs = [
        TranslationPair(case_id="c1", lang="sw", hypothesis=ref, reference=ref),
        TranslationPair(case_id="c2", lang="sw", hypothesis=ref, reference=ref),
    ]
    result = score_translations(pairs)
    assert result["n"] == 2
    assert result["chrf_global"] == pytest.approx(100.0)
    assert result["by_lang"]["sw"]["chrf_mean"] == pytest.approx(100.0)
    assert result["by_lang"]["sw"]["n"] == 2


def test_score_translations_aggregates_multiple_languages_independently() -> None:
    sw_ref = "Watu wote wamezaliwa huru."
    ln_ref = "Bato nyonso na mbotama bazali nzomi."
    pairs = [
        # swahili : parfait
        TranslationPair(case_id="sw1", lang="sw", hypothesis=sw_ref, reference=sw_ref),
        # lingala : complètement faux
        TranslationPair(
            case_id="ln1",
            lang="ln",
            hypothesis="Un texte français sans aucun rapport.",
            reference=ln_ref,
        ),
    ]
    result = score_translations(pairs)
    assert result["n"] == 2
    assert set(result["by_lang"].keys()) == {"sw", "ln"}
    assert result["by_lang"]["sw"]["chrf_mean"] == pytest.approx(100.0)
    assert result["by_lang"]["ln"]["chrf_mean"] < result["by_lang"]["sw"]["chrf_mean"]
    # Le global doit être la moyenne des scores individuels (pas des moyennes
    # par langue, ici équivalent car 1 paire/langue).
    assert result["chrf_global"] == pytest.approx(
        (result["by_lang"]["sw"]["chrf_mean"] + result["by_lang"]["ln"]["chrf_mean"]) / 2
    )


def test_score_translations_per_case_entries_match_input_count() -> None:
    pairs = [
        TranslationPair(case_id=f"c{i}", lang="ha", hypothesis="x", reference="y") for i in range(4)
    ]
    result = score_translations(pairs)
    assert len(result["per_case"]) == 4
    assert {row["case_id"] for row in result["per_case"]} == {"c0", "c1", "c2", "c3"}


# ----------------------------------------------------------------------------
# Chargement du dataset réel (parsing + validation seule — aucun LLM)
# ----------------------------------------------------------------------------


def test_african_dataset_loads_and_validates() -> None:
    ds = AfricanEvalDataset.from_yaml(DEFAULT_DATASET_PATH)
    assert len(ds.cases) >= 10
    ids = [c.id for c in ds.cases]
    assert len(ids) == len(set(ids)), "les ids de cas doivent être uniques"

    # Langues cibles couvertes par ce jeu (cf. docs/sourcing/african_languages.md) :
    # au moins swahili + 2 autres, comme demandé par le lot L2.4.
    assert "sw" in ds.languages
    assert len(ds.languages) >= 3

    for case in ds.cases:
        assert case.source_fr.strip(), f"{case.id}: source_fr vide"
        assert case.reference.strip(), f"{case.id}: reference vide"


def test_african_dataset_missing_file_raises(tmp_path: Path) -> None:
    missing = tmp_path / "does_not_exist.yaml"
    with pytest.raises(FileNotFoundError):
        AfricanEvalDataset.from_yaml(missing)


def test_african_eval_case_model_validates_required_fields() -> None:
    case = AfricanEvalCase(
        id="t1",
        lang="sw",
        source_fr="Bonjour.",
        reference="Habari.",
    )
    assert case.lang == "sw"
    assert case.notes is None


def test_african_dataset_all_cases_have_known_language_code() -> None:
    """Garde-fou : détecte un code langue orphelin (typo) qui ne serait
    reconnu par aucun nom lisible dans `LANGUAGE_NAMES_FR` du harnais."""
    from tests.eval.eval_african import LANGUAGE_NAMES_FR

    ds = AfricanEvalDataset.from_yaml(DEFAULT_DATASET_PATH)
    unknown = ds.languages - set(LANGUAGE_NAMES_FR.keys())
    assert not unknown, f"langues non répertoriées dans LANGUAGE_NAMES_FR: {unknown}"
