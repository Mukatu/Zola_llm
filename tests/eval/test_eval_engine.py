"""Tests du harnais d'éval MOTEUR (L1.6) — aucun LLM, aucun réseau.

Vérifie le calcul des métriques (`evaluate_case`, `EngineEvalReport`) sur des
résultats FACTICES (pole_obtenu/grounding_obtenu fournis à la main) : prouve
que l'agrégation est correcte, indépendamment de tout appel réel au routeur ou
à l'orchestrateur.

Pour la passe complète contre le moteur réel (LLM + éventuellement corpus RAG),
voir `tests/eval/test_engine_eval_live.py` (gated `ZOLAOS_RUN_ENGINE_EVAL=1`).
"""

from __future__ import annotations

from pathlib import Path

from tests.eval.eval_engine import (
    DEFAULT_DATASET_PATH,
    EngineEvalCase,
    EngineEvalDataset,
    EngineEvalReport,
    evaluate_case,
)

# ----------------------------------------------------------------------------
# Chargement du dataset réel (parsing seul — aucun LLM)
# ----------------------------------------------------------------------------


def test_engine_dataset_loads_and_validates() -> None:
    ds = EngineEvalDataset.from_yaml(DEFAULT_DATASET_PATH)
    assert len(ds.cases) >= 15
    assert len(ds.cases) <= 25
    ids = [c.id for c in ds.cases]
    assert len(ids) == len(set(ids)), "les ids de cas doivent être uniques"

    poles_attendus = {c.pole_attendu for c in ds.cases}
    # Les 8 pôles métier doivent tous être couverts par au moins un cas de routage.
    assert poles_attendus == {
        "health",
        "legal",
        "erp",
        "grc",
        "fintech",
        "cyber",
        "engineering",
        "general",
    }

    # Au moins un cas d'abstention et un cas d'ancrage sourced attendus.
    groundings = [c.grounding_attendu for c in ds.cases]
    assert "abstained" in groundings
    assert "sourced" in groundings


def test_engine_dataset_missing_file_raises(tmp_path: Path) -> None:
    missing = tmp_path / "does_not_exist.yaml"
    try:
        EngineEvalDataset.from_yaml(missing)
    except FileNotFoundError:
        pass
    else:
        raise AssertionError("devrait lever FileNotFoundError")


# ----------------------------------------------------------------------------
# evaluate_case : cas unitaires
# ----------------------------------------------------------------------------


def _case(
    pole_attendu: str = "legal",
    grounding_attendu: str | None = None,
) -> EngineEvalCase:
    return EngineEvalCase(
        id="t1",
        query="peu importe",
        pole_attendu=pole_attendu,
        grounding_attendu=grounding_attendu,  # type: ignore[arg-type]
    )


def test_evaluate_case_routing_correct() -> None:
    result = evaluate_case(_case(pole_attendu="legal"), pole_obtenu="legal")
    assert result.routing_correct is True
    assert result.grounding_correct is None  # non vérifié (grounding_attendu=None)


def test_evaluate_case_routing_incorrect() -> None:
    result = evaluate_case(_case(pole_attendu="legal"), pole_obtenu="fintech")
    assert result.routing_correct is False


def test_evaluate_case_routing_unmeasured_on_error() -> None:
    result = evaluate_case(_case(), pole_obtenu=None, error="TimeoutError: boom")
    assert result.routing_correct is None
    assert result.error is not None


def test_evaluate_case_grounding_abstained_correct() -> None:
    result = evaluate_case(
        _case(grounding_attendu="abstained"),
        pole_obtenu="legal",
        grounding_obtenu="abstained",
    )
    assert result.grounding_correct is True


def test_evaluate_case_grounding_abstained_incorrect_when_sourced_instead() -> None:
    """Régression cible du harnais : le moteur a répondu avec une source alors
    qu'il aurait dû s'abstenir (corpus muet) — doit ressortir comme un échec."""
    result = evaluate_case(
        _case(grounding_attendu="abstained"),
        pole_obtenu="legal",
        grounding_obtenu="sourced",
    )
    assert result.grounding_correct is False


def test_evaluate_case_grounding_sourced_correct() -> None:
    result = evaluate_case(
        _case(grounding_attendu="sourced"),
        pole_obtenu="legal",
        grounding_obtenu="sourced",
    )
    assert result.grounding_correct is True


# ----------------------------------------------------------------------------
# EngineEvalReport : agrégation
# ----------------------------------------------------------------------------


def _make_report_10_cases(n_routing_ok: int) -> EngineEvalReport:
    """10 cas de ROUTAGE seul (grounding_attendu=None) : `n_routing_ok` corrects."""
    results = []
    for i in range(10):
        case = _case(pole_attendu="legal")
        ok = i < n_routing_ok
        results.append(evaluate_case(case, pole_obtenu="legal" if ok else "fintech"))
    return EngineEvalReport(dataset_name="fake", results=results)


def test_routing_accuracy_aggregates_correctly() -> None:
    # Données in : 10 cas, 8 bien routés → routing_accuracy == 0.8 (cf. consigne L1.6).
    report = _make_report_10_cases(n_routing_ok=8)
    assert report.total == 10
    assert len(report.routing_evaluated) == 10
    assert report.routing_accuracy == 0.8


def test_routing_accuracy_all_correct() -> None:
    report = _make_report_10_cases(n_routing_ok=10)
    assert report.routing_accuracy == 1.0


def test_routing_accuracy_all_wrong() -> None:
    report = _make_report_10_cases(n_routing_ok=0)
    assert report.routing_accuracy == 0.0


def test_routing_accuracy_empty_report_is_zero_not_crash() -> None:
    report = EngineEvalReport(dataset_name="empty", results=[])
    assert report.routing_accuracy == 0.0
    assert report.overall_grounding_accuracy == 0.0
    assert report.abstention_accuracy == 0.0
    assert report.sourced_accuracy == 0.0


def test_abstention_accuracy_restricted_to_abstained_expected_cases() -> None:
    """8 cas 'abstained' dont 6 correctement abstenus + 2 cas 'sourced' (ignorés
    du calcul d'abstention) → abstention_accuracy == 6/8 == 0.75."""
    results = []
    for i in range(8):
        case = _case(grounding_attendu="abstained")
        ok = i < 6
        results.append(
            evaluate_case(
                case,
                pole_obtenu="legal",
                grounding_obtenu="abstained" if ok else "sourced",
            )
        )
    # 2 cas hors-scope abstention : ne doivent PAS peser dans abstention_accuracy.
    for _ in range(2):
        case = _case(grounding_attendu="sourced")
        results.append(evaluate_case(case, pole_obtenu="legal", grounding_obtenu="sourced"))

    report = EngineEvalReport(dataset_name="fake", results=results)
    assert report.total == 10
    assert report.abstention_accuracy == 0.75
    assert report.sourced_accuracy == 1.0


def test_sourced_accuracy_aggregates_correctly() -> None:
    """5 cas 'sourced' dont 3 correctement ancrés → sourced_accuracy == 0.6."""
    results = []
    for i in range(5):
        case = _case(grounding_attendu="sourced")
        ok = i < 3
        results.append(
            evaluate_case(
                case,
                pole_obtenu="legal",
                grounding_obtenu="sourced" if ok else "unsourced",
            )
        )
    report = EngineEvalReport(dataset_name="fake", results=results)
    assert report.sourced_accuracy == 0.6


def test_overall_grounding_accuracy_mixes_all_expected_grounding_cases() -> None:
    results = [
        evaluate_case(
            _case(grounding_attendu="abstained"), pole_obtenu="legal", grounding_obtenu="abstained"
        ),
        evaluate_case(
            _case(grounding_attendu="abstained"), pole_obtenu="legal", grounding_obtenu="sourced"
        ),
        evaluate_case(
            _case(grounding_attendu="sourced"), pole_obtenu="legal", grounding_obtenu="sourced"
        ),
        evaluate_case(
            _case(grounding_attendu="sourced"), pole_obtenu="legal", grounding_obtenu="sourced"
        ),
    ]
    # 3/4 corrects (le 2e cas attendait abstained, a obtenu sourced → faux).
    report = EngineEvalReport(dataset_name="fake", results=results)
    assert report.overall_grounding_accuracy == 0.75
    # Les cas sans grounding_attendu (routage seul) ne polluent pas ce calcul.
    routing_only = evaluate_case(_case(grounding_attendu=None), pole_obtenu="legal")
    report2 = EngineEvalReport(dataset_name="fake", results=[*results, routing_only])
    assert report2.overall_grounding_accuracy == 0.75
    assert len(report2.grounding_evaluated) == 4


def test_errors_property_collects_failed_cases() -> None:
    results = [
        evaluate_case(_case(), pole_obtenu="legal"),
        evaluate_case(_case(), pole_obtenu=None, error="RuntimeError: llm down"),
    ]
    report = EngineEvalReport(dataset_name="fake", results=results)
    assert len(report.errors) == 1
    assert "RuntimeError" in report.errors[0].error  # type: ignore[operator]


def test_render_does_not_crash_and_contains_key_metrics() -> None:
    report = _make_report_10_cases(n_routing_ok=8)
    text = report.render()
    assert "Routage" in text
    assert "80%" in text or "0.8" in text or "80" in text
