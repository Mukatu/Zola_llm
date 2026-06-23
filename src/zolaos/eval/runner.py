"""Runner : exécute un dataset contre un agent et produit un DatasetReport.

Usage programmatique :

    from zolaos.eval.runner import run_dataset
    report = await run_dataset(dataset_path, agent_instance)
    print(report.render())

Usage CLI (minimal) :
    python -m zolaos.eval.runner tests/eval/datasets/dummy/legal_ohada.yaml
"""

from __future__ import annotations

import argparse
import asyncio
import importlib
import time
from pathlib import Path

from zolaos.agents.rag_agent import InsufficientContextError, RAGAgent
from zolaos.core.logging import get_logger
from zolaos.eval.dataset import EvalDataset
from zolaos.eval.metrics import CaseReport, DatasetReport, evaluate_case

_log = get_logger("zolaos.eval.runner")


# Map nom d'agent → chemin import (utile pour CLI / charge dynamique).
_AGENT_REGISTRY = {
    "health.pharmacology": "zolaos.agents.health.pharmacology:PharmacologyAgent",
    "legal.ohada": "zolaos.agents.legal.ohada:OhadaAgent",
    "legal.travail_cg": "zolaos.agents.legal.travail_cg:TravailCgAgent",
    "legal.fiscal_cg": "zolaos.agents.legal.fiscal_cg:FiscalCgAgent",
}


def resolve_agent_class(name: str) -> type[RAGAgent]:
    if name not in _AGENT_REGISTRY:
        raise ValueError(f"Agent inconnu: {name!r}. Connus: {list(_AGENT_REGISTRY)}")
    module_path, class_name = _AGENT_REGISTRY[name].split(":")
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


async def run_dataset(
    dataset_path: str | Path,
    agent: RAGAgent,
) -> DatasetReport:
    """Charge un dataset YAML, exécute chaque cas contre l'agent, agrège."""
    ds = EvalDataset.from_yaml(dataset_path)
    reports: list[CaseReport] = []

    for case in ds.cases:
        t0 = time.perf_counter()
        response = None
        refused = False
        try:
            response = await agent.answer(
                case.question,
                extra_tags=case.extra_tags or None,
            )
        except InsufficientContextError:
            refused = True
        except Exception as exc:
            _log.exception("eval.case_error", case_id=case.id, error=str(exc))
            # Une erreur autre que le refus contrôlé = échec dur, mais on continue.
            reports.append(
                CaseReport(
                    case_id=case.id,
                    severity=case.severity,
                    passed=False,
                    latency_seconds=time.perf_counter() - t0,
                    failure_reasons=[f"exception inattendue: {type(exc).__name__}: {exc}"],
                )
            )
            continue
        latency = time.perf_counter() - t0
        reports.append(evaluate_case(case, response, refused=refused, latency_seconds=latency))

    return DatasetReport(dataset_name=str(Path(dataset_path).name), cases=reports)


# ---------------- CLI minimal ----------------


def _build_agent_from_name(name: str) -> RAGAgent:
    from zolaos.core.settings import get_settings
    from zolaos.llm.factory import make_router_client

    settings = get_settings()
    client = make_router_client(settings)
    cls = resolve_agent_class(name)
    return cls(client=client, settings=settings)


def _main() -> None:
    parser = argparse.ArgumentParser(description="Runner d'évaluation ZolaOS")
    parser.add_argument("dataset", help="chemin du dataset YAML")
    parser.add_argument(
        "--agent",
        help="nom de l'agent (sinon lu depuis dataset.agent du YAML)",
        default=None,
    )
    args = parser.parse_args()

    ds = EvalDataset.from_yaml(args.dataset)
    agent_name = args.agent or ds.dataset.agent
    agent = _build_agent_from_name(agent_name)

    report = asyncio.run(run_dataset(args.dataset, agent))
    print(report.render())


if __name__ == "__main__":
    _main()
