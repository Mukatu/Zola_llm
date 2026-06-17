"""Tests du framework d'évaluation lui-même (pas des agents).

Vérifie :
- chargement YAML + validation Pydantic
- métriques par cas (passed/refused/keywords/citations)
- agrégation DatasetReport
- runner end-to-end avec un agent mocké (pas d'appel LLM réel ici)

Pour les vraies évaluations d'agents contre LLM réel, voir tests/eval/test_*_eval.py
(marker `eval`, à créer une fois les corpus RAG ingérés).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path

import pytest

from zolaos.agents.rag_agent import (
    Citation,
    InsufficientContextError,
    RAGAgent,
    RAGAgentResponse,
)
from zolaos.eval.dataset import EvalCase, EvalDataset, ExpectedCitation
from zolaos.eval.metrics import DatasetReport, evaluate_case
from zolaos.eval.runner import run_dataset
from zolaos.rag.retrieval import Match

DATASET_PATH = Path(__file__).parent / "datasets" / "dummy" / "legal_ohada.yaml"


# ----------------------------------------------------------------------------
# Mocks
# ----------------------------------------------------------------------------

@dataclass
class _FakeAgent(RAGAgent):
    """Agent factice qui retourne une réponse prédéterminée pour chaque cas."""

    # On bypass complètement RAGAgent.__init__ (pas besoin de client LLM réel)
    name = "legal.ohada"
    rag_schema = "rag_legal"
    prompt_file = "legal/ohada.md"
    default_tags = ("country:cg", "module:ohada")

    canned_responses: dict[str, RAGAgentResponse | type[InsufficientContextError]] | None = None

    def __init__(self, canned: dict) -> None:  # type: ignore[no-untyped-def]
        # NB : on ne call PAS super().__init__ pour éviter le besoin de LLMClient/Settings
        self.canned_responses = canned

    async def answer(self, query: str, *, extra_tags=None, k=None) -> RAGAgentResponse:  # type: ignore[no-untyped-def]
        canned = (self.canned_responses or {}).get(query)
        if canned is None:
            raise InsufficientContextError(f"pas de canned pour: {query}")
        if isinstance(canned, type) and issubclass(canned, Exception):
            raise canned("simulated refusal")
        return canned


def _fake_match(source_id: str, content: str = "") -> Match:
    return Match(
        content=content,
        score=0.1,
        source_uri=f"/fake/{source_id}.txt",
        source_id=source_id,
        chunk_index=0,
        tags=["country:cg"],
        extra_metadata={},
    )


# ----------------------------------------------------------------------------
# Tests : loader + validation
# ----------------------------------------------------------------------------

def test_dataset_yaml_loads_and_validates() -> None:
    ds = EvalDataset.from_yaml(DATASET_PATH)
    assert ds.dataset.agent == "legal.ohada"
    assert ds.dataset.module == "ohada"
    assert len(ds.cases) == 3
    case_001 = ds.cases[0]
    assert case_001.id == "ohada_dummy_001"
    assert case_001.severity == "high"
    assert "1 000 000" in case_001.expected_keywords


# ----------------------------------------------------------------------------
# Tests : métriques par cas
# ----------------------------------------------------------------------------

def test_evaluate_case_pass_with_keywords_and_citations() -> None:
    case = EvalCase(
        id="t1",
        question="?",
        expected_keywords=["paris", "france"],
        expected_citations=[ExpectedCitation(source_id="SRC1"), ExpectedCitation(article="Art. 5")],
    )
    response = RAGAgentResponse(
        agent="x",
        content="La capitale est Paris en France, voir Art. 5.",
        citations=[Citation(index=1, source_uri="/x", source_id="SRC1", chunk_index=0, similarity=0.9)],
        matches=[_fake_match("SRC1")],
    )
    report = evaluate_case(case, response, latency_seconds=0.1)
    assert report.passed is True
    assert report.expected_kw_hit_rate == 1.0
    assert report.citation_recall == 1.0


def test_evaluate_case_fails_on_missing_keyword() -> None:
    case = EvalCase(id="t2", question="?", expected_keywords=["obligatoire"])
    response = RAGAgentResponse(agent="x", content="autre chose", citations=[], matches=[])
    report = evaluate_case(case, response, latency_seconds=0.1)
    assert report.passed is False
    assert any("obligatoire" in r.lower() for r in report.failure_reasons)


def test_evaluate_case_fails_on_forbidden_keyword() -> None:
    case = EvalCase(id="t3", question="?", forbidden_keywords=["€"])
    response = RAGAgentResponse(agent="x", content="prix 100 €", citations=[], matches=[])
    report = evaluate_case(case, response, latency_seconds=0.1)
    assert report.passed is False
    assert report.forbidden_kw_hit is True


def test_evaluate_case_must_refuse_with_refusal() -> None:
    case = EvalCase(id="t4", question="?", must_refuse=True)
    report = evaluate_case(case, response=None, refused=True, latency_seconds=0.1)
    assert report.passed is True
    assert report.refusal_correct is True


def test_evaluate_case_must_refuse_but_answered_fails() -> None:
    case = EvalCase(id="t5", question="?", must_refuse=True)
    response = RAGAgentResponse(agent="x", content="Voici la réponse", citations=[], matches=[])
    report = evaluate_case(case, response, refused=False, latency_seconds=0.1)
    assert report.passed is False


def test_evaluate_case_must_answer_but_refused_fails() -> None:
    case = EvalCase(id="t6", question="?", expected_keywords=["x"])
    report = evaluate_case(case, response=None, refused=True, latency_seconds=0.1)
    assert report.passed is False


# ----------------------------------------------------------------------------
# Tests : agrégation
# ----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_dataset_end_to_end_with_fake_agent() -> None:
    canned: dict = {
        "Quel est le capital social minimum d'une SARL OHADA ?": RAGAgentResponse(
            agent="legal.ohada",
            content="Le capital social minimum d'une SARL OHADA est de 1 000 000 FCFA (Art. 311 AUSCGIE).",
            citations=[Citation(index=1, source_uri="/x", source_id="AUSCGIE", chunk_index=0, similarity=0.9)],
            matches=[_fake_match("AUSCGIE", "Art. 311 ...")],
        ),
        "Comment dissoudre une coopérative agricole OHADA ?": RAGAgentResponse(
            agent="legal.ohada",
            content="La dissolution se prononce en assemblée générale extraordinaire.",
            citations=[],
            matches=[_fake_match("AUSCOOP")],
        ),
        "Quelle est la couleur de la voiture du DG ?": InsufficientContextError,
    }
    agent = _FakeAgent(canned)
    report = await run_dataset(DATASET_PATH, agent)

    assert isinstance(report, DatasetReport)
    assert report.total == 3
    # 001 doit passer (keywords + citation OK), 002 doit passer (keywords seuls), 003 doit passer (refus attendu et obtenu)
    assert report.passed == 3, report.render()
    assert report.pass_rate == 1.0
