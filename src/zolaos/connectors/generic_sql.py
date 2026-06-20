"""Connecteur SQL générique en lecture (V2.2 §2.4, §4.4 — livré en standard).

Accès direct à une base de données via SQLAlchemy (n'importe quel dialecte
installé : SQLite, PostgreSQL, MySQL…). **Lecture seule** : uniquement des
requêtes SELECT paramétrées fournies par configuration (pas d'écriture, pas de
SQL dynamique côté ZolaOS → surface d'injection nulle).

Config attendue :
    {
      "dsn": "postgresql+psycopg://user:pwd@host/db",   # ou sqlite:///fichier.db
      "queries": {
        "employees": "SELECT id AS id_externe, nom_complet, poste FROM rh.employes",
        "invoices": "SELECT ... FROM compta.factures",
        "invoice_by_id": "SELECT ... FROM compta.factures WHERE id = :id",
        "bank_transactions": "SELECT ... FROM banque.mvts"
      }
    }
"""

from __future__ import annotations

import asyncio
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from zolaos.connectors.base import (
    ConnectorConfigError,
    ConnectorConnectionError,
    FinanceConnector,
    HRConnector,
    InvoiceConnector,
)
from zolaos.connectors.models import BankTransaction, Employee, Invoice
from zolaos.core.logging import get_logger

_log = get_logger("zolaos.connectors.generic_sql")


class GenericSqlConnector(HRConnector, InvoiceConnector, FinanceConnector):
    """Connecteur SQL en lecture seule, piloté par requêtes configurées."""

    name = "generic_sql"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._engine: Engine | None = None

    async def connect(self) -> None:
        await self.auth.prepare()
        dsn = self.config.get("dsn")
        if not dsn:
            raise ConnectorConfigError("config['dsn'] obligatoire.")
        self._engine = await asyncio.to_thread(create_engine, dsn, pool_pre_ping=True)

    async def close(self) -> None:
        if self._engine is not None:
            await asyncio.to_thread(self._engine.dispose)
            self._engine = None

    async def healthcheck(self) -> bool:
        if self._engine is None:
            return False
        try:
            await asyncio.to_thread(self._exec_sync, "SELECT 1", {})
            return True
        except Exception:  # noqa: BLE001
            return False

    # -- exécution ------------------------------------------------------------

    def _exec_sync(self, sql: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        assert self._engine is not None
        with self._engine.connect() as conn:
            result = conn.execute(text(sql), params)
            return [dict(row) for row in result.mappings().all()]

    async def _run(self, query_key: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        if self._engine is None:
            raise ConnectorConfigError("Connecteur non connecté (appeler connect()).")
        sql = self.config.get("queries", {}).get(query_key)
        if not sql:
            raise ConnectorConfigError(f"requête {query_key!r} non configurée.")
        try:
            return await asyncio.to_thread(self._exec_sync, sql, params or {})
        except ConnectorConfigError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise ConnectorConnectionError(f"Requête {query_key!r} échec: {exc}") from exc

    def _canon(self, row: dict[str, Any]) -> dict[str, Any]:
        return self.mapping.apply(row) if self.mapping is not None else dict(row)

    # -- interface unique -----------------------------------------------------

    async def list_employees(self, **filters: Any) -> list[Employee]:
        async with self._instrument("list_employees"):
            return [Employee(**self._canon(r)) for r in await self._run("employees")]

    async def list_invoices(self, **filters: Any) -> list[Invoice]:
        async with self._instrument("list_invoices"):
            return [Invoice(**self._canon(r)) for r in await self._run("invoices")]

    async def read_invoice(self, invoice_id: str) -> Invoice:
        async with self._instrument("read_invoice"):
            rows = await self._run("invoice_by_id", {"id": invoice_id})
            if not rows:
                raise ConnectorConfigError(f"Facture {invoice_id!r} introuvable.")
            return Invoice(**self._canon(rows[0]))

    async def list_bank_transactions(self, **filters: Any) -> list[BankTransaction]:
        async with self._instrument("list_bank_transactions"):
            return [BankTransaction(**self._canon(r)) for r in await self._run("bank_transactions")]
