"""Sous-agent Finance — pôle ERP, module finance (V2.2 §4.2).

Analyse de trésorerie **data-driven** (pas RAG) : branché sur le Connector
Framework pour récupérer les mouvements (banque / MoMo / Airtel) et les
factures, puis :

1. **Détection d'anomalies DÉTERMINISTE** (sans LLM) : doublons, dépassements
   (gros débits), échéances (factures en retard). Les chiffres sont calculés en
   code — jamais « interprétés » par le modèle.
2. **Synthèse GÉNÉRATIVE** (LLM) : le modèle **narre** l'analyse déterministe
   (rapport mensuel/trimestriel orienté DGID), sans inventer de montant.

Principe ERP (cf. `docs/ERP_AGENTS_ROADMAP.md`) : déterministe d'abord, LLM pour
la rédaction/interprétation uniquement. Disponible profils box et cortex.

Overlay Polaris correspondant : `Trésorerie` (déjà livré).
"""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Literal

from zolaos.agents._prompts import load_prompt
from zolaos.connectors.base import BaseConnector, Capability
from zolaos.connectors.models import BankTransaction, Invoice
from zolaos.core.logging import get_logger
from zolaos.core.metrics import AGENT_INVOCATIONS_TOTAL
from zolaos.core.settings import Settings
from zolaos.llm.base import GenerationOptions, LLMClient, Message

_log = get_logger("zolaos.agents.erp.finance")

FindingType = Literal["doublon", "depassement", "echeance"]
Severity = Literal["low", "medium", "high"]


@dataclass(frozen=True)
class FinanceFinding:
    type: FindingType
    severity: Severity
    libelle: str
    montant_xaf: Decimal
    references: list[str] = field(default_factory=list)  # id_externe concernés


@dataclass(frozen=True)
class FinanceAnalysis:
    n_transactions: int
    total_debit_xaf: Decimal
    total_credit_xaf: Decimal
    net_xaf: Decimal
    findings: list[FinanceFinding]


class FinanceAgent:
    """Agent Finance : analyse déterministe + synthèse générative."""

    name = "erp.finance"
    prompt_file = "erp/finance.md"

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

    # ====================================================== détecteurs (purs)

    @staticmethod
    def detect_duplicates(transactions: list[BankTransaction]) -> list[FinanceFinding]:
        """Mouvements identiques (date, sens, montant, libellé) apparaissant ≥ 2 fois."""
        groups: dict[tuple, list[BankTransaction]] = defaultdict(list)
        for t in transactions:
            key = (t.date_operation, t.sens, abs(t.montant_xaf), t.libelle.strip().lower())
            groups[key].append(t)
        findings: list[FinanceFinding] = []
        for (d, sens, montant, _libelle), grp in groups.items():
            if len(grp) > 1:
                findings.append(
                    FinanceFinding(
                        type="doublon",
                        severity="medium",
                        libelle=f"{len(grp)}× '{grp[0].libelle}' le {d} ({sens})",
                        montant_xaf=montant,
                        references=[t.id_externe for t in grp],
                    )
                )
        return findings

    @staticmethod
    def detect_large_outflows(
        transactions: list[BankTransaction], threshold_xaf: Decimal
    ) -> list[FinanceFinding]:
        """Débits dont le montant dépasse un seuil configuré."""
        findings: list[FinanceFinding] = []
        for t in transactions:
            if t.sens == "debit" and abs(t.montant_xaf) > threshold_xaf:
                sev: Severity = "high" if abs(t.montant_xaf) > threshold_xaf * 2 else "medium"
                findings.append(
                    FinanceFinding(
                        type="depassement",
                        severity=sev,
                        libelle=f"Débit important : {t.libelle} ({t.date_operation})",
                        montant_xaf=abs(t.montant_xaf),
                        references=[t.id_externe],
                    )
                )
        return findings

    @staticmethod
    def detect_overdue_invoices(invoices: list[Invoice], *, as_of: date) -> list[FinanceFinding]:
        """Factures non payées dont l'échéance est dépassée."""
        findings: list[FinanceFinding] = []
        for inv in invoices:
            if not inv.payee and inv.date_echeance is not None and inv.date_echeance < as_of:
                retard = (as_of - inv.date_echeance).days
                sev: Severity = "high" if retard > 30 else "medium"
                findings.append(
                    FinanceFinding(
                        type="echeance",
                        severity=sev,
                        libelle=f"Facture {inv.numero} ({inv.tiers}) en retard de {retard} j",
                        montant_xaf=inv.montant_ttc_xaf,
                        references=[inv.id_externe],
                    )
                )
        return findings

    # ====================================================== analyse (pure)

    def analyze(
        self,
        transactions: list[BankTransaction],
        *,
        invoices: list[Invoice] | None = None,
        large_threshold_xaf: Decimal = Decimal("1000000"),
        as_of: date | None = None,
    ) -> FinanceAnalysis:
        """Analyse 100% déterministe (aucun appel LLM)."""
        as_of = as_of or date.today()
        total_debit = sum(
            (abs(t.montant_xaf) for t in transactions if t.sens == "debit"), Decimal("0")
        )
        total_credit = sum(
            (abs(t.montant_xaf) for t in transactions if t.sens == "credit"), Decimal("0")
        )
        findings = (
            self.detect_duplicates(transactions)
            + self.detect_large_outflows(transactions, large_threshold_xaf)
            + self.detect_overdue_invoices(invoices or [], as_of=as_of)
        )
        return FinanceAnalysis(
            n_transactions=len(transactions),
            total_debit_xaf=total_debit,
            total_credit_xaf=total_credit,
            net_xaf=total_credit - total_debit,
            findings=findings,
        )

    async def analyze_from_connector(
        self, *, large_threshold_xaf: Decimal = Decimal("1000000"), as_of: date | None = None
    ) -> FinanceAnalysis:
        """Récupère mouvements (+ factures si supportées) via le connecteur, puis analyse."""
        if self._connector is None:
            raise ValueError("FinanceAgent : aucun connecteur fourni.")
        if not self._connector.supports(Capability.LIST_BANK_TRANSACTIONS):
            raise ValueError(
                f"Le connecteur {self._connector.name!r} ne fournit pas les mouvements bancaires."
            )
        transactions = await self._connector.list_bank_transactions()
        invoices: list[Invoice] = []
        if self._connector.supports(Capability.LIST_INVOICES):
            invoices = await self._connector.list_invoices()
        return self.analyze(
            transactions, invoices=invoices, large_threshold_xaf=large_threshold_xaf, as_of=as_of
        )

    # ====================================================== synthèse (LLM)

    def _format_analysis(self, analysis: FinanceAnalysis) -> str:
        lines = [
            f"Mouvements analysés : {analysis.n_transactions}",
            f"Total débits : {analysis.total_debit_xaf} XAF",
            f"Total crédits : {analysis.total_credit_xaf} XAF",
            f"Flux net : {analysis.net_xaf} XAF",
            f"Anomalies détectées : {len(analysis.findings)}",
        ]
        for f in analysis.findings:
            lines.append(
                f"- [{f.severity}] {f.type} : {f.libelle} — {f.montant_xaf} XAF (réf: {', '.join(f.references)})"
            )
        return "\n".join(lines)

    async def synthesize(self, analysis: FinanceAnalysis, *, period_label: str = "mensuel") -> str:
        """Rapport narratif (LLM) à partir de l'analyse déterministe. Ne recalcule rien."""
        start = time.perf_counter()
        outcome = "error"
        try:
            user_msg = (
                f"--- Analyse de trésorerie ({period_label}) — chiffres déjà calculés ---\n"
                f"{self._format_analysis(analysis)}\n\n"
                "Rédige une synthèse de trésorerie professionnelle à partir de CES chiffres "
                "uniquement. N'invente aucun montant. Structure : situation, anomalies à "
                "traiter (par sévérité), recommandations d'action."
            )
            opts = GenerationOptions(temperature=0.2, max_tokens=1200)
            result = await self._client.generate(
                [
                    Message(role="system", content=load_prompt("erp", "finance.md")),
                    Message(role="user", content=user_msg),
                ],
                model=self._settings.LLM_MODEL_BRIGADE,
                options=opts,
            )
            outcome = "ok"
            _log.info(
                "finance_agent.synthesize",
                findings=len(analysis.findings),
                duration_seconds=time.perf_counter() - start,
            )
            return result.content
        finally:
            AGENT_INVOCATIONS_TOTAL.labels(agent=self.name, outcome=outcome).inc()
