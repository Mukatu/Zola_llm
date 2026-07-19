"""Test de non-régression du routeur, contre le jeu de vérité-terrain
`tests/agents/router/regression_v1.jsonl`.

Contexte : le routeur (llama3-8b local, prompt `agents/prompts/router.md`) a vu
plusieurs frontières corrigées au fil des versions (legal/erp, grc/fintech,
fiscal/fintech, sujet-vs-secteur — voir le `changelog` du front-matter du
prompt). Chaque correction a été validée manuellement mais aucune n'était
protégée par un test automatisé : une regression de prompt pouvait donc
réintroduire silencieusement une frontière déjà corrigée. Ce test comble ce
manque en rejouant, contre le routeur réel, les cas vérifiés.

Marqué `integration` : nécessite un serveur LLM joignable (le routeur tourne
sur `settings.LLM_HOST_ROUTER`, cf. `.env` / `LLM_HOST_ROUTER`). Skip
automatiquement si le serveur n'est pas joignable (même logique que
`tests/integration/test_orchestrator_e2e.py`).

Anti-flake — approche retenue :
    Le routeur appelle le LLM à température 0, mais un serveur d'inférence
    local peut malgré tout introduire un bruit résiduel (batching, kernels
    non-déterministes sur certains backends). Pour ne détecter qu'une VRAIE
    dérive de frontière (et non un flake isolé), chaque cas est rejoué
    `ATTEMPTS` fois (3) et on retient la décision MAJORITAIRE (mode) sur le
    pôle et sur le module :
      - le pôle doit être majoritaire égal à `expected_pole` (assertion dure) ;
      - si `expected_module` est renseigné, le module doit lui aussi être
        majoritaire égal à `expected_module` (assertion dure).
    Un flake isolé (1 réponse sur 3 qui diverge) ne fait donc pas échouer le
    test ; une dérive systématique (2 ou 3 réponses sur 3) le fait échouer,
    ce qui est le signal recherché — une vraie régression de frontière.
    `expected_module: null` désactive volontairement le contrôle de module
    pour les cas où seul le pôle est un signal fiable (ex. erp/rh vs
    erp/compta_syscohada, frontière encore floue et non garantie par le
    prompt).

Lancement :
    docker exec zolaos-app python -m pytest tests/test_router_regression.py \
        -m integration -o addopts="" -q
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest

from zolaos.agents.router import Router
from zolaos.core.settings import Settings
from zolaos.llm.factory import make_router_client

pytestmark = pytest.mark.integration

ATTEMPTS = 3

_DATASET_PATH = Path(__file__).parent / "agents" / "router" / "regression_v1.jsonl"


def _load_cases(path: Path) -> list[dict]:
    cases: list[dict] = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            cases.append(json.loads(line))
    return cases


_CASES = _load_cases(_DATASET_PATH)


def _server_reachable(host: str) -> bool:
    # llama.cpp expose /health, Ollama expose /api/tags (les deux backends
    # sont supportés par la factory selon LLM_BACKEND). On essaie les deux.
    for path in ("/health", "/api/tags"):
        try:
            r = httpx.get(f"{host}{path}", timeout=3.0)
            if r.status_code == 200:
                return True
        except httpx.HTTPError:
            continue
    return False


def _majority(values: list[str | None]) -> str | None:
    """Retourne la valeur la plus fréquente (mode) parmi `values`."""
    return Counter(values).most_common(1)[0][0]


@pytest.fixture(scope="module")
def settings() -> Settings:
    # Pas d'override d'hôte ici : on veut la config réelle telle que chargée
    # par l'environnement du conteneur (LLM_HOST_ROUTER pointe déjà vers le
    # bon hôte/port depuis .env / docker-compose).
    return Settings()


@pytest.fixture
async def router(settings: Settings) -> AsyncIterator[Router]:
    if not _server_reachable(settings.LLM_HOST_ROUTER):
        pytest.skip(f"Serveur LLM indisponible sur {settings.LLM_HOST_ROUTER}")
    client = make_router_client(settings)
    try:
        yield Router(client, settings)
    finally:
        await client.aclose()  # type: ignore[attr-defined]


@pytest.mark.parametrize(
    "case",
    _CASES,
    ids=[c["question"][:60] for c in _CASES],
)
async def test_router_regression_case(router: Router, case: dict) -> None:
    question = case["question"]
    expected_pole = case["expected_pole"]
    expected_module = case.get("expected_module")
    note = case.get("note", "")

    decisions = [await router.classify(question) for _ in range(ATTEMPTS)]

    poles = [d.pole.value for d in decisions]
    majority_pole = _majority(poles)
    assert majority_pole == expected_pole, (
        f"Régression de routage (pôle) sur {question!r} : réponses={poles}, "
        f"majorité={majority_pole!r}, attendu={expected_pole!r}. Note: {note}"
    )

    if expected_module is not None:
        modules = [d.module for d in decisions]
        majority_module = _majority(modules)
        assert majority_module == expected_module, (
            f"Régression de routage (module) sur {question!r} : réponses={modules}, "
            f"majorité={majority_module!r}, attendu={expected_module!r}. Note: {note}"
        )
