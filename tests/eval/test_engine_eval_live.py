"""Éval MOTEUR complète (L1.6) contre le routeur/orchestrateur RÉELS.

Marqué `eval` (comme `tests/eval/test_golden.py`) : nécessite un serveur LLM
joignable ; pour la partie ancrage/abstention, un corpus RAG idéalement
ingéré (sinon tous les cas "sourced" attendus se retrouveront "abstained" —
ce qui reste un résultat rapporté, pas un crash).

SKIP par défaut (comme `ZOLAOS_RUN_LLM_E2E` pour
`tests/integration/test_orchestrator_e2e.py`) : le routage LLM est non
déterministe, et cette suite ne doit jamais bloquer la CI standard. Opt-in
explicite :

    ZOLAOS_RUN_ENGINE_EVAL=1 .venv_test/Scripts/python.exe -m pytest \
        tests/eval/test_engine_eval_live.py -m eval -q --no-cov

Seuils volontairement TOLÉRANTS (pas de 100% strict) : ce test surveille une
tendance de qualité à l'échelle, pas une régression unitaire — cf. `pass_rate`
critique déjà géré ailleurs (`test_golden.py`) pour les garanties dures.
"""

from __future__ import annotations

import os

import httpx
import pytest

from tests.eval.eval_engine import DEFAULT_DATASET_PATH, EngineEvalDataset, run_engine_eval
from zolaos.core.orchestrator import Orchestrator
from zolaos.core.settings import Settings
from zolaos.llm.factory import make_core_client, make_router_client

pytestmark = pytest.mark.eval

# Seuils plancher — à resserrer au fil des lots (L1.x suivants) une fois le
# corpus/routeur stabilisés. Volontairement prudents pour ne pas transformer
# une éval de surveillance en gate cassant.
_MIN_ROUTING_ACCURACY = 0.6
_MIN_ABSTENTION_ACCURACY = 0.5


def _llm_reachable(host: str) -> bool:
    for path in ("/health", "/api/tags", "/v1/models"):
        try:
            if httpx.get(f"{host}{path}", timeout=3.0).status_code == 200:
                return True
        except httpx.HTTPError:
            continue
    return False


@pytest.fixture
def settings() -> Settings:
    return Settings(
        LLM_HOST_ROUTER=os.environ.get("LLM_HOST_ROUTER", "http://localhost:11434"),
        LLM_HOST_CORE=os.environ.get("LLM_HOST_CORE", "http://localhost:11435"),
    )


@pytest.fixture
async def orchestrator(settings: Settings):  # type: ignore[no-untyped-def]
    if not os.environ.get("ZOLAOS_RUN_ENGINE_EVAL"):
        pytest.skip("Éval moteur non déterministe : activer avec ZOLAOS_RUN_ENGINE_EVAL=1")
    if not _llm_reachable(settings.LLM_HOST_ROUTER):
        pytest.skip(f"Serveur LLM indisponible sur {settings.LLM_HOST_ROUTER}")
    router_client = make_router_client(settings)
    core_client = make_core_client(settings)
    try:
        yield Orchestrator.from_clients(
            router_client=router_client,
            core_client=core_client,
            settings=settings,
        )
    finally:
        await router_client.aclose()  # type: ignore[attr-defined]
        if core_client is not router_client:
            await core_client.aclose()  # type: ignore[attr-defined]


async def test_engine_eval_dataset_against_real_orchestrator(orchestrator) -> None:  # type: ignore[no-untyped-def]
    """Passe complète : routage + ancrage/abstention sur `datasets/engine/engine_cases.yaml`.

    N'échoue pas au premier cas raté (comportement de surveillance, pas de
    garantie dure) : imprime le rapport détaillé puis vérifie des seuils
    globaux tolérants.
    """
    ds = EngineEvalDataset.from_yaml(DEFAULT_DATASET_PATH)
    report = await run_engine_eval(ds.cases, orchestrator=orchestrator)

    print(f"\n{report.render()}")

    assert report.routing_accuracy >= _MIN_ROUTING_ACCURACY, (
        f"routing_accuracy={report.routing_accuracy:.0%} < seuil {_MIN_ROUTING_ACCURACY:.0%}\n"
        f"{report.render()}"
    )
    assert report.abstention_accuracy >= _MIN_ABSTENTION_ACCURACY, (
        f"abstention_accuracy={report.abstention_accuracy:.0%} < seuil "
        f"{_MIN_ABSTENTION_ACCURACY:.0%} — le moteur invente possiblement des réponses "
        f"sur un corpus muet.\n{report.render()}"
    )
