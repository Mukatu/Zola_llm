"""Exécution des jeux golden VÉRIFIÉS contre les vrais agents (intégration).

Marqué `integration` : exige le LLM (Ollama/llama-server) ET le corpus ingéré.
Skippé proprement si le serveur LLM n'est pas joignable. Lance :

    docker exec zolaos-app python -m pytest tests/eval/test_golden.py -m integration -o addopts="" -q

Ce que ça vérifie, pour chaque cas d'un dataset `tests/eval/datasets/verified/` :
mots-clés attendus présents, mots-clés interdits absents, citations attendues
couvertes, et surtout **absence de contamination** (aucune source interdite citée
— ex. coopératives sur une SARL, fintech sur du fiscal). Les cas `severity:
critical` DOIVENT passer ; les autres sont rapportés sans bloquer.
"""

from __future__ import annotations

import glob
from pathlib import Path

import httpx
import pytest

from zolaos.core.settings import get_settings
from zolaos.eval.runner import resolve_agent_class, run_dataset
from zolaos.llm.factory import make_router_client

pytestmark = pytest.mark.integration

_VERIFIED_DIR = Path(__file__).parent / "datasets" / "verified"


def _llm_reachable() -> bool:
    host = get_settings().LLM_HOST_ROUTER
    for path in ("/health", "/api/tags", "/v1/models"):
        try:
            if httpx.get(f"{host}{path}", timeout=3.0).status_code == 200:
                return True
        except httpx.HTTPError:
            continue
    return False


def _datasets() -> list[str]:
    return sorted(glob.glob(str(_VERIFIED_DIR / "*.yaml")))


@pytest.mark.asyncio
async def test_golden_datasets() -> None:
    """Exécute TOUS les jeux golden dans UNE seule boucle d'événements.

    Un seul test (pas de paramétrage) : le pool asyncpg est lié à la boucle
    courante ; des tests async séparés en créent plusieurs et provoquent
    « Future attached to a different loop ». On boucle donc les datasets ici.
    """
    if not _llm_reachable():
        pytest.skip("LLM non joignable — test d'intégration ignoré")

    from zolaos.eval.dataset import EvalDataset

    settings = get_settings()
    client = make_router_client(settings)

    critiques_ko: list[str] = []
    for dataset_path in _datasets():
        agent = resolve_agent_class(EvalDataset.from_yaml(dataset_path).dataset.agent)(
            client=client, settings=settings
        )
        report = await run_dataset(dataset_path, agent)
        print(f"\n=== {Path(dataset_path).stem} ===")
        for c in report.cases:
            print(" ", c.summary)
            if c.severity == "critical" and not c.passed:
                critiques_ko.append(f"{c.case_id} → {c.failure_reasons}")

    # Les cas critiques ne doivent JAMAIS échouer (régression de sûreté).
    assert not critiques_ko, "cas critiques en échec: " + "; ".join(critiques_ko)
