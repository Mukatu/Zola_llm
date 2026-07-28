"""Tests du calcul de fertility / chars-par-token (`scripts/analyze_tokenizer.py`).

Aucun réseau, aucun modèle lourd : tout tourne sur du texte factice avec des
fonctions de comptage déterministes (repli whitespace, ou fausses fonctions de
comptage pour isoler `analyze()` de tout tokenizer réel). Le seul test qui
touche `transformers` monkeypatche `AutoTokenizer.from_pretrained` — jamais
d'appel réseau.
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest
from scripts.analyze_tokenizer import (
    LangMetrics,
    _whitespace_tokenize,
    analyze,
    build_parser,
    count_words,
    format_table,
    load_samples,
    load_tokenizer,
    main,
)

# --------------------------------------------------------------- count_words


def test_count_words_simple_whitespace() -> None:
    assert count_words("ana banana") == 2
    assert count_words("cat dog mouse") == 3


def test_count_words_ignores_lone_punctuation() -> None:
    # "here!" -> 1 mot ("here"), la ponctuation seule n'est pas un mot.
    assert count_words("go now.") == 2
    assert count_words("it's here!") == 2


def test_count_words_keeps_internal_apostrophe_as_one_word() -> None:
    # "aujourd'hui" doit compter pour 1 mot, pas 2.
    assert count_words("Il fait beau aujourd'hui.") == 4


def test_count_words_empty_string() -> None:
    assert count_words("") == 0


# ---------------------------------------------------------- whitespace tokenizer


def test_whitespace_tokenize_matches_str_split() -> None:
    assert _whitespace_tokenize("ana banana") == ["ana", "banana"]
    assert _whitespace_tokenize("") == []


# --------------------------------------------------------------------- analyze


def test_analyze_fertility_and_chars_per_token_are_exact_with_char_counter() -> None:
    # Compteur de tokens synthétique et déterministe : 1 token par caractère.
    # Isole la logique d'agrégation de `analyze()` de tout vrai tokenizer.
    samples = {
        "testlang": ["ana banana", "cat dog"],  # 10 + 7 = 17 caractères, 2+2 = 4 mots
    }

    def count_chars_as_tokens(text: str) -> int:
        return len(text)

    results = analyze(samples, count_chars_as_tokens)

    assert set(results) == {"testlang"}
    m = results["testlang"]
    assert isinstance(m, LangMetrics)
    assert m.n_samples == 2
    assert m.n_words == 4
    assert m.n_chars == 17  # len("ana banana") + len("cat dog") = 10 + 7
    assert m.n_tokens == 17  # même compteur (1 token/caractère)
    assert m.fertility == pytest.approx(17 / 4)
    assert m.chars_per_token == pytest.approx(1.0)


def test_analyze_with_whitespace_fallback_fertility_is_one() -> None:
    # Repli whitespace sur du texte sans ponctuation collée : 1 mot = 1 token.
    samples = {"testlang": ["ana banana", "cat dog mouse"]}

    def count_ws_tokens(text: str) -> int:
        return len(_whitespace_tokenize(text))

    results = analyze(samples, count_ws_tokens)
    m = results["testlang"]
    assert m.n_words == 5  # 2 + 3
    assert m.n_tokens == 5
    assert m.fertility == pytest.approx(1.0)
    assert m.n_chars == len("ana banana") + len("cat dog mouse")
    assert m.chars_per_token == pytest.approx(m.n_chars / 5)


def test_analyze_multiple_languages_are_independent() -> None:
    samples = {
        "a": ["ab cd"],  # 2 mots, 5 caractères
        "b": ["x"],  # 1 mot, 1 caractère
    }

    def count_double(text: str) -> int:
        return 2 * len(_whitespace_tokenize(text))

    results = analyze(samples, count_double)
    assert results["a"].n_tokens == 4
    assert results["a"].fertility == pytest.approx(2.0)
    assert results["b"].n_tokens == 2
    assert results["b"].fertility == pytest.approx(2.0)


def test_lang_metrics_fertility_nan_when_no_words() -> None:
    m = LangMetrics(lang="x", n_samples=0, n_words=0, n_chars=0, n_tokens=0)
    assert math.isnan(m.fertility)
    assert math.isnan(m.chars_per_token)


# ---------------------------------------------------------------- load_tokenizer


def test_load_tokenizer_none_is_fallback() -> None:
    label, count_tokens, is_fallback = load_tokenizer(None)
    assert is_fallback is True
    assert "repli" in label
    assert count_tokens("ana banana") == 2


def test_load_tokenizer_explicit_whitespace_is_fallback() -> None:
    label, count_tokens, is_fallback = load_tokenizer("whitespace")
    assert is_fallback is True
    assert count_tokens("cat dog mouse") == 3


def test_load_tokenizer_import_error_falls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    """Si `transformers` n'est pas importable, le repli whitespace doit s'activer."""
    import builtins

    real_import = builtins.__import__

    def _fake_import(name: str, *args: object, **kwargs: object) -> object:
        if name == "transformers":
            raise ImportError("transformers non installé (simulé)")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _fake_import)

    label, count_tokens, is_fallback = load_tokenizer("un/depot-quelconque")
    assert is_fallback is True
    assert "repli" in label
    assert count_tokens("ana banana") == 2


def test_load_tokenizer_hf_load_failure_falls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    """Si `AutoTokenizer.from_pretrained` échoue (offline/gated), repli whitespace."""
    transformers = pytest.importorskip("transformers")

    def _raise(*args: object, **kwargs: object) -> None:
        raise OSError("dépôt gated ou réseau indisponible (simulé)")

    monkeypatch.setattr(transformers.AutoTokenizer, "from_pretrained", _raise)

    label, count_tokens, is_fallback = load_tokenizer("meta-llama/Meta-Llama-3-8B")
    assert is_fallback is True
    assert "repli" in label
    assert count_tokens("ana banana") == 2


def test_load_tokenizer_hf_success_uses_real_encode(monkeypatch: pytest.MonkeyPatch) -> None:
    """Chemin de succès : le comptage délègue à `tokenizer.encode(...)`."""
    transformers = pytest.importorskip("transformers")

    class _FakeTokenizer:
        def encode(self, text: str, add_special_tokens: bool = False) -> list[int]:
            # Faux tokenizer déterministe : 1 token par caractère non-espace.
            return [0 for ch in text if not ch.isspace()]

    monkeypatch.setattr(
        transformers.AutoTokenizer, "from_pretrained", lambda *a, **k: _FakeTokenizer()
    )

    label, count_tokens, is_fallback = load_tokenizer("un/tokenizer-factice")
    assert is_fallback is False
    assert label == "un/tokenizer-factice"
    assert count_tokens("ab cd") == 4  # "abcd" -> 4 caractères non-espace


# ----------------------------------------------------------------- load_samples


def test_load_samples_from_directory(tmp_path: Path) -> None:
    (tmp_path / "fr.txt").write_text("# commentaire ignoré\nBonjour.\nMerci.\n\n", encoding="utf-8")
    (tmp_path / "sw.txt").write_text("Habari yako?\n", encoding="utf-8")

    samples = load_samples(tmp_path)

    assert samples == {
        "fr": ["Bonjour.", "Merci."],
        "sw": ["Habari yako?"],
    }


def test_load_samples_from_tabbed_file(tmp_path: Path) -> None:
    f = tmp_path / "samples.tsv"
    f.write_text(
        "# commentaire\nfr\tBonjour.\nfr\tMerci.\nsw\tHabari yako?\n",
        encoding="utf-8",
    )

    samples = load_samples(f)

    assert samples == {
        "fr": ["Bonjour.", "Merci."],
        "sw": ["Habari yako?"],
    }


def test_load_samples_falls_back_to_builtin_when_empty_dir(tmp_path: Path) -> None:
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()

    samples = load_samples(empty_dir)

    assert "fr" in samples
    assert len(samples["fr"]) >= 1


# ------------------------------------------------------------------- format_table


def test_format_table_contains_expected_columns() -> None:
    metrics = {
        "fr": LangMetrics(lang="fr", n_samples=2, n_words=4, n_chars=17, n_tokens=4),
    }
    table = format_table("whitespace (repli explicite)", metrics)
    assert "Tokenizer : whitespace (repli explicite)" in table
    assert "Fertility (tok/mot)" in table
    assert "Français (fr)" in table
    assert "1.00" in table  # fertility = 4/4 = 1.00


# ------------------------------------------------------------------------- CLI


def test_build_parser_help_does_not_raise() -> None:
    parser = build_parser()
    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args(["--help"])
    assert exc_info.value.code == 0


def test_main_runs_end_to_end_with_whitespace_fallback(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "fr.txt").write_text("Bonjour le monde.\n", encoding="utf-8")

    exit_code = main(["--samples", str(tmp_path)])

    assert exit_code == 0
    out = capsys.readouterr().out
    assert "Tokenizer : whitespace" in out
    assert "Français (fr)" in out


def test_main_writes_json_output(tmp_path: Path) -> None:
    (tmp_path / "fr.txt").write_text("Bonjour le monde.\n", encoding="utf-8")
    output_path = tmp_path / "resultats.json"

    exit_code = main(["--samples", str(tmp_path), "--output", str(output_path)])

    assert exit_code == 0
    assert output_path.exists()
    import json

    data = json.loads(output_path.read_text(encoding="utf-8"))
    label = next(iter(data))
    assert "fr" in data[label]
    assert data[label]["fr"]["n_words"] == 3  # "Bonjour", "le", "monde"
