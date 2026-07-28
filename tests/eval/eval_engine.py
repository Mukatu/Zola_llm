"""Harnais d'évaluation MOTEUR (L1.6) — routage, ancrage/citation, abstention.

Complète (ne remplace pas) le framework `zolaos.eval.*` + `tests/eval/test_eval_framework.py`
qui évalue un AGENT RAG précis (mots-clés attendus, citations exactes, contamination
inter-domaines). Ici l'unité évaluée est le MOTEUR dans son ensemble :

  - **justesse de routage** : `Router.classify(query).pole` == `pole_attendu` ?
  - **ancrage/abstention correcte** : le statut `grounding` produit par
    `Orchestrator.handle(...)` ("sourced" / "unsourced" / "abstained") == `grounding_attendu` ?

Séparation volontaire routage / génération (comme `zolaos.eval.metrics.evaluate_case`
sépare le calcul des métriques de l'appel réseau dans `zolaos.eval.runner.run_dataset`) :

  - `evaluate_case()` et `EngineEvalReport` sont **purs** : ils agrègent des résultats
    déjà obtenus (`pole_obtenu`, `grounding_obtenu`), sans appeler ni LLM ni DB.
    Testable à 100% sans réseau (cf. `tests/eval/test_eval_engine.py`).
  - `run_engine_eval()` est la partie COÛTEUSE : elle appelle réellement
    `Router.classify` (et, si un orchestrateur est fourni, `Orchestrator.handle`
    pour aussi mesurer l'ancrage). Nécessite un serveur LLM joignable, et pour
    l'ancrage un corpus RAG ingéré. Gatée dans les tests par la variable d'env
    `ZOLAOS_RUN_ENGINE_EVAL=1` (même pattern que `ZOLAOS_RUN_LLM_E2E` dans
    `tests/integration/test_orchestrator_e2e.py`) — jamais appelée par défaut.

Lancer l'éval moteur complète (LLM réel requis, corpus RAG idéalement ingéré) :

    ZOLAOS_RUN_ENGINE_EVAL=1 .venv_test/Scripts/python.exe -m pytest \
        tests/eval/test_engine_eval_live.py -m eval -q --no-cov

Lancer uniquement les tests du HARNAIS (aucun LLM, aucun réseau — CI par défaut) :

    .venv_test/Scripts/python.exe -m pytest tests/eval/test_eval_engine.py -q --no-cov
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field

from zolaos.core.logging import get_logger

_log = get_logger("zolaos.eval.engine")

DEFAULT_DATASET_PATH = Path(__file__).parent / "datasets" / "engine" / "engine_cases.yaml"

Grounding = Literal["sourced", "unsourced", "abstained"]


# ----------------------------------------------------------------------------
# Dataset : cas {query, pole_attendu, grounding_attendu}
# ----------------------------------------------------------------------------


class EngineEvalCase(BaseModel):
    """Un cas vérité-terrain moteur : requête, pôle attendu, ancrage attendu.

    `grounding_attendu = None` signifie « non vérifié pour ce cas » — le cas ne
    sert alors qu'à mesurer la justesse de routage, pas l'ancrage (utile pour
    des pôles sans corpus, ou quand l'état du corpus au moment du cas n'est pas
    garanti).
    """

    id: str
    query: str
    pole_attendu: str
    grounding_attendu: Grounding | None = None
    notes: str | None = None


class EngineEvalDataset(BaseModel):
    """Jeu de cas moteur chargé depuis YAML (cf. `datasets/engine/engine_cases.yaml`)."""

    version: str = "1.0"
    notes: str | None = None
    cases: list[EngineEvalCase] = Field(min_length=1)

    @classmethod
    def from_yaml(cls, path: str | Path = DEFAULT_DATASET_PATH) -> EngineEvalDataset:
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(p)
        raw = yaml.safe_load(p.read_text(encoding="utf-8"))
        ds = cls.model_validate(raw)
        _log.info("eval.engine.dataset_loaded", path=str(p), cases=len(ds.cases))
        return ds


# ----------------------------------------------------------------------------
# Résultat par cas + agrégation (PUR — aucun appel réseau/LLM ici)
# ----------------------------------------------------------------------------


@dataclass
class EngineCaseResult:
    """Résultat d'un cas : ce qui était attendu vs ce qui a été obtenu.

    `pole_obtenu`/`grounding_obtenu` à `None` signifie « non mesuré » (cas de
    routage seul, ou erreur avant d'obtenir la valeur) — à ne pas confondre
    avec une valeur mesurée qui ne correspond pas à l'attendu.
    """

    case_id: str
    query: str
    pole_attendu: str
    pole_obtenu: str | None
    grounding_attendu: Grounding | None
    grounding_obtenu: Grounding | None
    latency_seconds: float = 0.0
    error: str | None = None

    @property
    def routing_correct(self) -> bool | None:
        if self.pole_obtenu is None:
            return None
        return self.pole_obtenu == self.pole_attendu

    @property
    def grounding_correct(self) -> bool | None:
        if self.grounding_attendu is None or self.grounding_obtenu is None:
            return None
        return self.grounding_obtenu == self.grounding_attendu

    @property
    def summary(self) -> str:
        rc = self.routing_correct
        gc = self.grounding_correct
        rc_s = "?" if rc is None else ("✓" if rc else "✗")
        gc_s = "n/a" if gc is None else ("✓" if gc else "✗")
        status = (
            f"routage[{rc_s}] {self.pole_attendu}→{self.pole_obtenu or '?'} "
            f"ancrage[{gc_s}] {self.grounding_attendu or 'n/a'}→{self.grounding_obtenu or '?'}"
        )
        if self.error:
            status += f" ERREUR: {self.error}"
        return f"{self.case_id}: {status} ({self.latency_seconds:.2f}s)"


def evaluate_case(
    case: EngineEvalCase,
    pole_obtenu: str | None,
    grounding_obtenu: Grounding | None = None,
    *,
    latency_seconds: float = 0.0,
    error: str | None = None,
) -> EngineCaseResult:
    """Compare un cas attendu au résultat réel du routeur/orchestrateur.

    Fonction PURE : ne fait aucun appel LLM/DB, se contente de comparer des
    valeurs déjà obtenues par l'appelant (cf. `run_engine_eval` pour la partie
    qui appelle réellement le moteur).
    """
    return EngineCaseResult(
        case_id=case.id,
        query=case.query,
        pole_attendu=case.pole_attendu,
        pole_obtenu=pole_obtenu,
        grounding_attendu=case.grounding_attendu,
        grounding_obtenu=grounding_obtenu,
        latency_seconds=latency_seconds,
        error=error,
    )


@dataclass
class EngineEvalReport:
    """Agrégation des résultats d'une passe d'éval moteur.

    Métriques principales :
      - `routing_accuracy`            : % de cas correctement routés (parmi ceux mesurés)
      - `overall_grounding_accuracy`  : % de cas où le statut d'ancrage obtenu == attendu
      - `abstention_accuracy`        : idem, restreint aux cas `grounding_attendu == "abstained"`
      - `sourced_accuracy`           : idem, restreint aux cas `grounding_attendu == "sourced"`
    """

    dataset_name: str
    results: list[EngineCaseResult] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.results)

    # --- Routage ---

    @property
    def routing_evaluated(self) -> list[EngineCaseResult]:
        return [r for r in self.results if r.routing_correct is not None]

    @property
    def routing_accuracy(self) -> float:
        ev = self.routing_evaluated
        if not ev:
            return 0.0
        return sum(1 for r in ev if r.routing_correct) / len(ev)

    # --- Ancrage / abstention ---

    @property
    def grounding_evaluated(self) -> list[EngineCaseResult]:
        return [r for r in self.results if r.grounding_correct is not None]

    def _grounding_accuracy_for(self, expected: Grounding) -> float:
        subset = [r for r in self.grounding_evaluated if r.grounding_attendu == expected]
        if not subset:
            return 0.0
        return sum(1 for r in subset if r.grounding_correct) / len(subset)

    @property
    def abstention_accuracy(self) -> float:
        """Taux d'abstention CORRECTE : parmi les cas où on attendait `abstained`,
        fraction où l'orchestrateur s'est effectivement abstenu."""
        return self._grounding_accuracy_for("abstained")

    @property
    def sourced_accuracy(self) -> float:
        """Taux d'ancrage CORRECT : parmi les cas où on attendait `sourced`,
        fraction où l'orchestrateur a bien cité le corpus."""
        return self._grounding_accuracy_for("sourced")

    @property
    def unsourced_accuracy(self) -> float:
        return self._grounding_accuracy_for("unsourced")

    @property
    def overall_grounding_accuracy(self) -> float:
        ev = self.grounding_evaluated
        if not ev:
            return 0.0
        return sum(1 for r in ev if r.grounding_correct) / len(ev)

    @property
    def errors(self) -> list[EngineCaseResult]:
        return [r for r in self.results if r.error]

    def render(self) -> str:
        lines = [f"=== Éval moteur: {self.dataset_name} ===", ""]
        for r in self.results:
            lines.append(r.summary)
        lines.append("")
        lines.append(
            f"Routage       : {sum(1 for r in self.routing_evaluated if r.routing_correct)}"
            f"/{len(self.routing_evaluated)} ({self.routing_accuracy:.0%})"
        )
        lines.append(f"Ancrage global: {self.overall_grounding_accuracy:.0%}")
        lines.append(f"  · abstention attendue correcte : {self.abstention_accuracy:.0%}")
        lines.append(f"  · ancrage sourced correct       : {self.sourced_accuracy:.0%}")
        lines.append(f"  · ancrage unsourced correct     : {self.unsourced_accuracy:.0%}")
        if self.errors:
            lines.append(f"Erreurs       : {len(self.errors)}")
        return "\n".join(lines)


# ----------------------------------------------------------------------------
# Runner COÛTEUX (appelle réellement Router.classify / Orchestrator.handle)
# ----------------------------------------------------------------------------


async def run_engine_eval(
    cases: list[EngineEvalCase],
    *,
    router: object = None,
    orchestrator: object = None,
    tenant_id: str = "local",
) -> EngineEvalReport:
    """Exécute le jeu de cas contre le moteur réel.

    - Si `orchestrator` est fourni : appelle `orchestrator.handle(case.query, ...)`
      pour chaque cas — mesure à la fois `pole_obtenu` (via `decision.pole`) et
      `grounding_obtenu` (via `responses[0].grounding`). C'est le mode complet.
    - Sinon, si seul `router` est fourni : appelle `router.classify(case.query)` —
      mesure uniquement le routage (`grounding_obtenu` reste `None`). Utile pour
      isoler la justesse de routage d'un problème d'ancrage/RAG.

    Nécessite un vrai `LLMClient` (donc un serveur LLM joignable) dans `router`/
    `orchestrator` — jamais appelée par défaut dans la suite de tests standard,
    voir `tests/eval/test_engine_eval_live.py` (gated `ZOLAOS_RUN_ENGINE_EVAL`).
    """
    results: list[EngineCaseResult] = []
    for case in cases:
        t0 = time.perf_counter()
        pole_obtenu: str | None = None
        grounding_obtenu: Grounding | None = None
        error: str | None = None
        try:
            if orchestrator is not None:
                outcome = await orchestrator.handle(case.query, tenant_id=tenant_id)  # type: ignore[attr-defined]
                pole_obtenu = outcome.decision.pole.value
                if outcome.responses:
                    grounding_obtenu = outcome.responses[0].grounding
            elif router is not None:
                decision = await router.classify(case.query)  # type: ignore[attr-defined]
                pole_obtenu = decision.pole.value
            else:
                raise ValueError("run_engine_eval requiert `router` ou `orchestrator`")
        except Exception as exc:  # on continue la passe, on rapporte l'erreur dans le résultat
            error = f"{type(exc).__name__}: {exc}"
            _log.warning("eval.engine.case_error", case_id=case.id, error=error)
        latency = time.perf_counter() - t0
        results.append(
            evaluate_case(
                case,
                pole_obtenu,
                grounding_obtenu,
                latency_seconds=latency,
                error=error,
            )
        )
    return EngineEvalReport(dataset_name=DEFAULT_DATASET_PATH.stem, results=results)


__all__ = [
    "DEFAULT_DATASET_PATH",
    "EngineEvalCase",
    "EngineEvalDataset",
    "EngineCaseResult",
    "EngineEvalReport",
    "evaluate_case",
    "run_engine_eval",
]
