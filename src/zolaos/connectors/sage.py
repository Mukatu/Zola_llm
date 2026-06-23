"""Connecteur Sage (V2.2 §2.4, §4.4).

Sage se décline en plusieurs produits/protocoles ; deux modes sont prévus :

- **mode "api"** : REST (fonctionnel via httpx, réutilise le pattern générique).
- **mode "odbc"** : accès ODBC via le paquet **optionnel** `pyodbc` (NON ajouté
  aux dépendances par défaut — décision documentée, jalon C). Sans `pyodbc`,
  lève `ConnectorConfigError` explicite.

Config attendue (mode odbc) :
    {"mode": "odbc", "odbc_dsn": "DSN=Sage;UID=..;PWD=..",
     "queries": {"employees": "SELECT ...", "invoices": "SELECT ..."}}

Config attendue (mode api) :
    {"mode": "api", "base_url": "https://sage.client.cg/api",
     "endpoints": {"employees": "/employees", "invoices": "/invoices"}}
"""

from __future__ import annotations

import asyncio
from typing import Any

from zolaos.connectors.base import (
    ConnectorConfigError,
    FinanceConnector,
    HRConnector,
    InvoiceConnector,
)
from zolaos.connectors.models import BankTransaction, Employee, Invoice
from zolaos.core.logging import get_logger

_log = get_logger("zolaos.connectors.sage")


def _require_pyodbc() -> Any:
    try:
        import pyodbc  # type: ignore
    except ImportError as exc:  # pragma: no cover - chemin sans dépendance
        raise ConnectorConfigError(
            "Connecteur Sage ODBC indisponible : le paquet optionnel 'pyodbc' n'est pas "
            "installé. Installer avec `pip install pyodbc` (+ driver ODBC Sage) ou utiliser "
            "le mode 'api'."
        ) from exc
    return pyodbc


class SageConnector(HRConnector, InvoiceConnector, FinanceConnector):
    """Connecteur Sage (mode ODBC optionnel, ou REST)."""

    name = "sage"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._conn: Any = None
        self._rest: Any = None

    async def connect(self) -> None:
        await self.auth.prepare()
        mode = self.config.get("mode", "odbc")
        if mode == "odbc":
            pyodbc = _require_pyodbc()
            dsn = self.config.get("odbc_dsn")
            if not dsn:
                raise ConnectorConfigError("config['odbc_dsn'] obligatoire en mode odbc.")
            self._conn = await asyncio.to_thread(pyodbc.connect, dsn)
        elif mode == "api":
            from zolaos.connectors.generic_rest import GenericRestConnector

            self._rest = GenericRestConnector(
                config=self.config, auth=self.auth, mapping=self.mapping
            )
            await self._rest.connect()
        else:
            raise ConnectorConfigError(f"mode Sage inconnu: {mode!r} (attendu 'odbc' ou 'api').")

    async def close(self) -> None:
        if self._conn is not None:
            await asyncio.to_thread(self._conn.close)
            self._conn = None
        if self._rest is not None:
            await self._rest.close()
            self._rest = None

    # -- ODBC -----------------------------------------------------------------

    def _query_sync(self, sql: str) -> list[dict[str, Any]]:
        cur = self._conn.cursor()
        cur.execute(sql)
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, row, strict=False)) for row in cur.fetchall()]

    async def _rows(self, key: str) -> list[dict[str, Any]]:
        if self._rest is not None:
            return await self._rest._list(key)  # mode api délégué
        if self._conn is None:
            raise ConnectorConfigError("Connecteur Sage non connecté.")
        sql = self.config.get("queries", {}).get(key)
        if not sql:
            raise ConnectorConfigError(f"requête Sage {key!r} non configurée.")
        return await asyncio.to_thread(self._query_sync, sql)

    def _canon(self, row: dict[str, Any]) -> dict[str, Any]:
        return self.mapping.apply(row) if self.mapping is not None else dict(row)

    async def list_employees(self, **filters: Any) -> list[Employee]:
        async with self._instrument("list_employees"):
            return [Employee(**self._canon(r)) for r in await self._rows("employees")]

    async def list_invoices(self, **filters: Any) -> list[Invoice]:
        async with self._instrument("list_invoices"):
            return [Invoice(**self._canon(r)) for r in await self._rows("invoices")]

    async def read_invoice(self, invoice_id: str) -> Invoice:
        async with self._instrument("read_invoice"):
            for inv in await self.list_invoices():
                if inv.id_externe == invoice_id:
                    return inv
            raise ConnectorConfigError(f"Facture Sage {invoice_id!r} introuvable.")

    async def list_bank_transactions(self, **filters: Any) -> list[BankTransaction]:
        async with self._instrument("list_bank_transactions"):
            return [
                BankTransaction(**self._canon(r)) for r in await self._rows("bank_transactions")
            ]
