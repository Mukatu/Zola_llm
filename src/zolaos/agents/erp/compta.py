"""Comptabilité & Fiscalité SYSCOHADA — pôle ERP (V2.2 §4.3), moteur HYBRIDE.

Deux briques nettement séparées (cf. `docs/DATA_KNOWLEDGE_ROADMAP.md` §3bis.1) :

1. **Déterministe (source de vérité)** : le **plan de comptes SYSCOHADA** est une
   ressource `ref` structurée (`ref/syscohada_accounts.json`). La **validation
   d'écritures** (`JournalValidator`) est du code pur — équilibre, existence des
   comptes, cohérence — **jamais** du LLM. L'agent ne *devine* pas un compte : il
   le *lit* dans le plan.

2. **Interprétation (RAG)** : `ComptaAgent` n'utilise le RAG (AUDCIF + CGI) que
   pour **interpréter / justifier** (traitement fiscal TVA/IS/IRPP, conformité),
   avec citations — pas pour calculer.

`rag_schema="rag_legal"` : placeholder tant que `rag_erp` n'existe pas (même
pattern que les autres sous-agents Phase 4).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from zolaos.agents.rag_agent import RAGAgent
from zolaos.connectors.models import JournalEntry

_REF_DIR = Path(__file__).parent / "ref"
_ZERO = Decimal("0")

SensNormal = Literal["debit", "credit", "mixte"]


# =============================================================================
# Plan de comptes (déterministe, source de vérité)
# =============================================================================


class Account(BaseModel):
    numero: str
    libelle: str
    classe: int = Field(..., ge=1, le=9)
    sens_normal: SensNormal = "mixte"


class ChartOfAccounts:
    """Plan de comptes SYSCOHADA chargé depuis la ressource `ref`."""

    def __init__(
        self, accounts: list[Account], *, validated: bool = False, version: str = ""
    ) -> None:
        self._by_numero = {a.numero: a for a in accounts}
        self.validated = validated
        self.version = version

    @classmethod
    def load(cls, country: str = "cg") -> ChartOfAccounts:
        path = _REF_DIR / (
            "syscohada_accounts.json" if country == "cg" else f"syscohada_accounts_{country}.json"
        )
        if not path.is_file():
            raise FileNotFoundError(f"Plan de comptes introuvable : {path}")
        data = json.loads(path.read_text(encoding="utf-8"))
        accounts = [Account.model_validate(a) for a in data.get("accounts", [])]
        return cls(
            accounts, validated=data.get("validated", False), version=data.get("version", "")
        )

    def get(self, numero: str) -> Account | None:
        """Compte exact."""
        return self._by_numero.get(numero)

    def resolve(self, numero: str) -> Account | None:
        """Compte exact, sinon compte parent (préfixe le plus long). Gère les sous-comptes."""
        exact = self._by_numero.get(numero)
        if exact is not None:
            return exact
        candidates = [a for n, a in self._by_numero.items() if numero.startswith(n)]
        return max(candidates, key=lambda a: len(a.numero)) if candidates else None


# =============================================================================
# Validation d'écritures (déterministe — aucun LLM)
# =============================================================================


@dataclass(frozen=True)
class ValidationReport:
    ok: bool
    total_debit_xaf: Decimal
    total_credit_xaf: Decimal
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class JournalValidator:
    """Valide une écriture comptable contre le plan de comptes. 100% déterministe."""

    def __init__(self, chart: ChartOfAccounts) -> None:
        self._chart = chart

    def validate(self, entry: JournalEntry) -> ValidationReport:
        errors: list[str] = []
        warnings: list[str] = []

        total_debit = sum((l.debit_xaf for l in entry.lignes), _ZERO)
        total_credit = sum((l.credit_xaf for l in entry.lignes), _ZERO)

        if len(entry.lignes) < 2:
            errors.append("Une écriture doit comporter au moins 2 lignes (partie double).")

        # Équilibre débit = crédit
        if total_debit != total_credit:
            errors.append(
                f"Écriture déséquilibrée : débit {total_debit} ≠ crédit {total_credit} XAF."
            )

        # Au moins un débit et un crédit non nuls
        if total_debit == _ZERO or total_credit == _ZERO:
            errors.append("Une écriture doit avoir au moins une ligne au débit ET une au crédit.")

        for li in entry.lignes:
            acc = self._chart.resolve(li.compte)
            if acc is None:
                errors.append(f"Compte inconnu au plan SYSCOHADA : {li.compte!r} ({li.libelle}).")
                continue
            if li.debit_xaf > 0 and li.credit_xaf > 0:
                errors.append(f"Ligne {li.compte} : débit ET crédit non nuls simultanément.")
            # Cohérence de sens (avertissement, pas blocage : contre-passations légitimes)
            if acc.sens_normal == "credit" and li.debit_xaf > 0 and li.credit_xaf == 0:
                warnings.append(
                    f"Mouvement inhabituel : débit sur compte {acc.numero} ({acc.libelle}), normalement créditeur."
                )
            if acc.sens_normal == "debit" and li.credit_xaf > 0 and li.debit_xaf == 0:
                warnings.append(
                    f"Mouvement inhabituel : crédit sur compte {acc.numero} ({acc.libelle}), normalement débiteur."
                )

        return ValidationReport(
            ok=not errors,
            total_debit_xaf=total_debit,
            total_credit_xaf=total_credit,
            errors=errors,
            warnings=warnings,
        )


# =============================================================================
# Agent Compta (RAG — interprétation fiscale uniquement)
# =============================================================================


class ComptaAgent(RAGAgent):
    name = "erp.compta"
    rag_schema = "rag_legal"  # placeholder — rag_erp (AUDCIF/CGI) futur
    prompt_file = "erp/compta.md"
    default_tags = ("country:cg", "module:compta")
    requires_citation = True
    min_confidence = 0.50
    top_k = 6
    max_tokens = 1400
    temperature = 0.10

    _chart: ChartOfAccounts | None = None

    def chart(self) -> ChartOfAccounts:
        """Plan de comptes (chargé paresseusement, partagé)."""
        chart = type(self)._chart
        if chart is None:
            chart = ChartOfAccounts.load("cg")
            type(self)._chart = chart
        return chart

    def validate_entry(self, entry: JournalEntry) -> ValidationReport:
        """Validation déterministe d'une écriture (sans LLM)."""
        return JournalValidator(self.chart()).validate(entry)
