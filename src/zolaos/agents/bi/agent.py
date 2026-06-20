"""Agent BI / Pilotage — couche IA (addendum §3.1, BI-2).

Généralise le pattern de l'agent Finance à tous les domaines : KPIs
**déterministes** (BI-1) puis **interprétation par LLM** :
- `synthesize()` : synthèse narrative (insights + recommandations) ;
- `answer()` : Q&A en langage naturel **sur le set de KPIs calculés**.

Le LLM **ne calcule jamais** : il reçoit les KPIs déjà calculés et les
narre/explique. Pas de text-to-SQL (accès libre aux données écarté), pas de
forecasting (brique dédiée hors MVP). Disponible profils box et cortex.
"""

from __future__ import annotations

import time
from datetime import date

from zolaos.agents._prompts import load_prompt
from zolaos.agents.bi.kpi import KpiValue, compute_kpis
from zolaos.connectors.base import BaseConnector, Capability
from zolaos.core.logging import get_logger
from zolaos.core.metrics import AGENT_INVOCATIONS_TOTAL
from zolaos.core.settings import Settings
from zolaos.llm.base import GenerationOptions, LLMClient, Message

_log = get_logger("zolaos.agents.bi.agent")


class BIAgent:
    """Agent de pilotage : KPIs déterministes + interprétation LLM."""

    name = "bi.pilotage"
    prompt_file = "bi/pilotage.md"

    def __init__(
        self,
        client: LLMClient,
        settings: Settings,
        *,
        connector: BaseConnector | None = None,
    ) -> None:
        self._client = client
        self._settings = settings
        self._connector = connector

    # ---------------------------------------------------- KPIs (déterministe)

    def compute(self, *, periode: str | None = None, **data) -> list[KpiValue]:  # type: ignore[no-untyped-def]
        """Délègue au moteur déterministe (invoices/transactions/employees)."""
        return compute_kpis(periode=periode, **data)

    async def compute_from_connector(self, *, periode: str | None = None) -> list[KpiValue]:
        """Récupère les données via le connecteur (selon ses capacités) puis calcule."""
        if self._connector is None:
            raise ValueError("BIAgent : aucun connecteur fourni.")
        c = self._connector
        invoices = await c.list_invoices() if c.supports(Capability.LIST_INVOICES) else None
        transactions = (
            await c.list_bank_transactions()
            if c.supports(Capability.LIST_BANK_TRANSACTIONS) else None
        )
        employees = await c.list_employees() if c.supports(Capability.LIST_EMPLOYEES) else None
        return compute_kpis(
            invoices=invoices, transactions=transactions, employees=employees,
            periode=periode or date.today().isoformat(),
        )

    # ---------------------------------------------------- formatage

    @staticmethod
    def _format_kpis(kpis: list[KpiValue]) -> str:
        if not kpis:
            return "(aucun KPI calculé)"
        lines = ["--- KPIs calculés (déterministes) ---"]
        for k in kpis:
            per = f" [{k.periode}]" if k.periode else ""
            lines.append(f"- {k.libelle} ({k.domaine}){per} : {k.valeur} {k.unite}")
        return "\n".join(lines)

    # ---------------------------------------------------- couche IA (LLM)

    async def _generate(self, user_msg: str, op: str) -> str:
        start = time.perf_counter()
        outcome = "error"
        try:
            result = await self._client.generate(
                [
                    Message(role="system", content=load_prompt("bi", "pilotage.md")),
                    Message(role="user", content=user_msg),
                ],
                model=self._settings.LLM_MODEL_BRIGADE,
                options=GenerationOptions(temperature=0.2, max_tokens=1200),
            )
            outcome = "ok"
            _log.info("bi_agent." + op, duration_seconds=time.perf_counter() - start)
            return result.content
        finally:
            AGENT_INVOCATIONS_TOTAL.labels(agent=self.name, outcome=outcome).inc()

    async def synthesize(self, kpis: list[KpiValue], *, periode: str | None = None) -> str:
        """Synthèse de pilotage narrative à partir des KPIs (le LLM ne recalcule pas)."""
        user_msg = (
            f"--- Tableau de bord{f' ({periode})' if periode else ''} — chiffres déjà calculés ---\n"
            f"{self._format_kpis(kpis)}\n\n"
            "Rédige une synthèse de pilotage à partir de CES KPIs uniquement : situation, "
            "points d'attention, recommandations d'action. N'invente aucun chiffre."
        )
        return await self._generate(user_msg, "synthesize")

    async def answer(self, question: str, kpis: list[KpiValue]) -> str:
        """Répond à une question en langage naturel **sur les KPIs fournis**."""
        user_msg = (
            f"{self._format_kpis(kpis)}\n\n"
            f"--- Question ---\n{question}\n\n"
            "Réponds **uniquement** à partir des KPIs ci-dessus. Si la réponse n'y figure "
            "pas, dis-le explicitement (ne calcule pas, n'invente pas)."
        )
        return await self._generate(user_msg, "answer")
