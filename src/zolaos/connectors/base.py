"""Connector Framework — interface abstraite (V2.2 §2.4).

Couche d'abstraction unique pour brancher ZolaOS à n'importe quel système
externe (ERP, compta, banque, paie, maison). Principe : **interface unique**
(`list_employees`, `read_invoice`, `push_journal_entry`, …), capacités
déclarées par héritage de mixins, auth pluggable, mapping déclaratif.

Un connecteur concret hérite des mixins de capacité qu'il supporte :

    class MonErp(HRConnector, AccountingConnector):
        name = "mon_erp"
        async def list_employees(self, **f): ...
        async def read_invoice(self, invoice_id): ...
        async def list_invoices(self, **f): ...
        async def push_journal_entry(self, entry): ...

Les capacités sont alors dérivées automatiquement (`MonErp.capabilities()`).

Disponible dans les deux profils (`box` ET `cortex`) : les connecteurs vivent
là où sont les données (généralement la Box client).
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from enum import Enum
from typing import Any, ClassVar

from zolaos.connectors.auth import AuthStrategy, NoAuth
from zolaos.connectors.mapping import FieldMapping
from zolaos.connectors.models import (
    BankTransaction,
    Employee,
    Invoice,
    JournalEntry,
)
from zolaos.core.logging import get_logger

_log = get_logger("zolaos.connectors.base")


# =============================================================================
# Erreurs
# =============================================================================

class ConnectorError(RuntimeError):
    """Erreur générique d'un connecteur."""


class ConnectorConfigError(ConnectorError):
    """Configuration invalide ou dépendance optionnelle manquante."""


class ConnectorAuthError(ConnectorError):
    """Échec d'authentification vers le système distant."""


class ConnectorConnectionError(ConnectorError):
    """Système distant injoignable (réseau, timeout, 5xx)."""


class CapabilityNotSupported(ConnectorError):
    """Le connecteur ne déclare pas la capacité demandée."""


# =============================================================================
# Capacités
# =============================================================================

class Capability(str, Enum):
    LIST_EMPLOYEES = "list_employees"
    READ_INVOICE = "read_invoice"
    LIST_INVOICES = "list_invoices"
    PUSH_JOURNAL_ENTRY = "push_journal_entry"
    LIST_BANK_TRANSACTIONS = "list_bank_transactions"


# =============================================================================
# Connecteur de base
# =============================================================================

class BaseConnector(ABC):
    """Base de tous les connecteurs : cycle de vie, capacités, instrumentation."""

    name: ClassVar[str] = "base"
    #: capacités fournies par CETTE classe (les mixins la renseignent).
    PROVIDES: ClassVar[frozenset[Capability]] = frozenset()

    def __init__(
        self,
        *,
        config: dict[str, Any] | None = None,
        auth: AuthStrategy | None = None,
        mapping: FieldMapping | None = None,
    ) -> None:
        self.config: dict[str, Any] = config or {}
        self.auth: AuthStrategy = auth or NoAuth()
        self.mapping: FieldMapping | None = mapping

    # -- capacités ------------------------------------------------------------

    @classmethod
    def capabilities(cls) -> frozenset[Capability]:
        """Union des capacités déclarées par toute la hiérarchie (mixins)."""
        caps: set[Capability] = set()
        for klass in cls.__mro__:
            caps |= getattr(klass, "PROVIDES", frozenset())
        return frozenset(caps)

    def supports(self, cap: Capability) -> bool:
        return cap in self.capabilities()

    def _ensure(self, cap: Capability) -> None:
        if not self.supports(cap):
            raise CapabilityNotSupported(
                f"Connecteur {self.name!r} ne supporte pas {cap.value!r} "
                f"(capacités: {sorted(c.value for c in self.capabilities())})"
            )

    # -- cycle de vie ---------------------------------------------------------

    async def connect(self) -> None:
        """Établit la connexion / prépare l'auth. Surcharge optionnelle."""
        await self.auth.prepare()

    async def healthcheck(self) -> bool:
        """Vérifie que le système distant répond. Par défaut True."""
        return True

    async def close(self) -> None:
        """Libère les ressources. Surcharge optionnelle."""
        return None

    async def __aenter__(self) -> BaseConnector:
        await self.connect()
        return self

    async def __aexit__(self, *_exc: object) -> None:
        await self.close()

    # -- instrumentation (métriques branchées au Jalon E) ---------------------

    @asynccontextmanager
    async def _instrument(self, op: str) -> AsyncIterator[None]:
        """Mesure durée + issue d'une opération connecteur (logs + métriques)."""
        start = time.perf_counter()
        outcome = "error"
        try:
            yield
            outcome = "ok"
        finally:
            duration = time.perf_counter() - start
            _log.info(
                "connector.call",
                connector=self.name,
                operation=op,
                outcome=outcome,
                duration_seconds=duration,
            )
            # Hook métriques Prometheus (Jalon E) :
            try:
                from zolaos.core.metrics import (
                    CONNECTOR_CALL_DURATION_SECONDS,
                    CONNECTOR_CALLS_TOTAL,
                )

                CONNECTOR_CALLS_TOTAL.labels(
                    connector=self.name, operation=op, outcome=outcome
                ).inc()
                CONNECTOR_CALL_DURATION_SECONDS.labels(
                    connector=self.name, operation=op
                ).observe(duration)
            except Exception:  # noqa: BLE001  (métriques optionnelles, jamais bloquantes)
                pass


# =============================================================================
# Mixins de capacité (interface unique)
# =============================================================================

class HRConnector(BaseConnector):
    """Capacité RH : liste des salariés."""

    PROVIDES = frozenset({Capability.LIST_EMPLOYEES})

    @abstractmethod
    async def list_employees(self, **filters: Any) -> list[Employee]:
        """Retourne les salariés normalisés."""


class InvoiceConnector(BaseConnector):
    """Capacité comptable en LECTURE : factures."""

    PROVIDES = frozenset({Capability.READ_INVOICE, Capability.LIST_INVOICES})

    @abstractmethod
    async def read_invoice(self, invoice_id: str) -> Invoice:
        """Lit une facture par identifiant externe."""

    @abstractmethod
    async def list_invoices(self, **filters: Any) -> list[Invoice]:
        """Liste les factures normalisées."""


class JournalConnector(BaseConnector):
    """Capacité comptable en ÉCRITURE : écritures de journal."""

    PROVIDES = frozenset({Capability.PUSH_JOURNAL_ENTRY})

    @abstractmethod
    async def push_journal_entry(self, entry: JournalEntry) -> str:
        """Pousse une écriture comptable, retourne l'identifiant créé."""


class AccountingConnector(InvoiceConnector, JournalConnector):
    """Capacité comptable complète (lecture factures + écriture journal).

    Convenance pour les connecteurs qui font les deux (ERP type Odoo/ERPNext).
    Les capacités sont dérivées automatiquement des deux mixins parents.
    """


class FinanceConnector(BaseConnector):
    """Capacité finance : mouvements bancaires / Mobile Money."""

    PROVIDES = frozenset({Capability.LIST_BANK_TRANSACTIONS})

    @abstractmethod
    async def list_bank_transactions(self, **filters: Any) -> list[BankTransaction]:
        """Liste les mouvements normalisés."""
