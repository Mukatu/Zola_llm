"""Éval TRADUCTION langues africaines complète (L2.4) contre un vrai LLM.

Marqué `eval` (comme `tests/eval/test_engine_eval_live.py` et
`tests/eval/test_golden.py`) : nécessite un serveur LLM joignable. Traduit
réellement `source_fr` -> langue cible pour chaque cas du dataset, puis
calcule chrF contre la référence sourcée (`datasets/african/udhr_pairs.yaml`).

SKIP par défaut (comme `ZOLAOS_RUN_ENGINE_EVAL`) : opt-in explicite —

    ZOLAOS_RUN_AFRICAN_EVAL=1 .venv_test/Scripts/python.exe -m pytest \
        tests/eval/test_african_eval_live.py -m eval -q --no-cov

Sert de RÉFÉRENCE ("avant") : ce même harnais, pointé plus tard vers un
modèle Llama-3 adapté (L2.3), doit produire un `chrf_global`/`by_lang`
supérieur pour prouver l'amélioration — c'est tout l'intérêt de construire
l'éval avant l'entraînement (éval-driven).
"""

from __future__ import annotations

import os

import httpx
import pytest

from tests.eval.eval_african import DEFAULT_DATASET_PATH, AfricanEvalDataset, run_african_eval
from zolaos.core.settings import Settings
from zolaos.llm.factory import make_router_client

pytestmark = pytest.mark.eval


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
    return Settings(LLM_HOST_ROUTER=os.environ.get("LLM_HOST_ROUTER", "http://localhost:11434"))


@pytest.fixture
async def llm(settings: Settings):  # type: ignore[no-untyped-def]
    if not os.environ.get("ZOLAOS_RUN_AFRICAN_EVAL"):
        pytest.skip("Éval africaine coûteuse : activer avec ZOLAOS_RUN_AFRICAN_EVAL=1")
    if not _llm_reachable(settings.LLM_HOST_ROUTER):
        pytest.skip(f"Serveur LLM indisponible sur {settings.LLM_HOST_ROUTER}")
    client = make_router_client(settings)
    try:
        yield client
    finally:
        await client.aclose()  # type: ignore[attr-defined]


async def test_african_eval_dataset_against_real_llm(llm, settings: Settings) -> None:  # type: ignore[no-untyped-def]
    """Passe complète : traduction réelle + chrF sur `datasets/african/udhr_pairs.yaml`.

    Ne fixe volontairement PAS de seuil de qualité strict pour cette
    première version du harnais (aucune baseline mesurée n'existe encore) :
    imprime le rapport détaillé pour servir de référence "avant
    entraînement" (cf. L2.3) plutôt que de faire échouer la CI.
    """
    ds = AfricanEvalDataset.from_yaml(DEFAULT_DATASET_PATH)
    model = os.environ.get("LLM_MODEL_ROUTER", "llama3:8b")
    report = await run_african_eval(ds.cases, llm=llm, model=model)

    print(f"\n{report.render()}")

    assert report.result["n"] == len(ds.cases)
    # Garde-fou minimal : au moins une traduction a produit un score mesurable
    # (pas 100% d'erreurs silencieuses côté LLM).
    assert report.result["chrf_global"] >= 0.0
