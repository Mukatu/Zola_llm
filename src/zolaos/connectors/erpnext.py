"""Connecteur ERPNext / Frappe (V2.2 §2.4, §4.4 — connecteur standard).

ERPNext expose une API REST `/api/resource/<Doctype>`. Authentification par
token `Authorization: token <api_key>:<api_secret>`. Implémentation httpx.

Config attendue :
    {
      "base_url": "https://erp.client.cg",
      "api_key": "xxxx",
      "api_secret": SecretStr("yyyy"),
      "doctypes": {                    # surcharge optionnelle
        "employee": "Employee",
        "invoice": "Sales Invoice"
      },
      "timeout_seconds": 30
    }
"""

from __future__ import annotations

import json
from typing import Any

import httpx
from pydantic import SecretStr

from zolaos.connectors.base import (
    AccountingConnector,
    ConnectorConfigError,
    ConnectorConnectionError,
    FinanceConnector,
    HRConnector,
)
from zolaos.connectors.models import BankTransaction, Employee, Invoice, JournalEntry
from zolaos.core.logging import get_logger

_log = get_logger("zolaos.connectors.erpnext")


class ErpNextConnector(HRConnector, AccountingConnector, FinanceConnector):
    """Connecteur ERPNext REST."""

    name = "erpnext"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._client: httpx.AsyncClient | None = None

    def _doctype(self, key: str, default: str) -> str:
        return self.config.get("doctypes", {}).get(key, default)

    async def connect(self) -> None:
        await self.auth.prepare()
        base = self.config.get("base_url")
        if not base:
            raise ConnectorConfigError("config['base_url'] obligatoire pour ERPNext.")
        secret = self.config.get("api_secret")
        secret_val = secret.get_secret_value() if isinstance(secret, SecretStr) else str(secret or "")
        headers = {"Accept": "application/json"}
        if self.config.get("api_key"):
            headers["Authorization"] = f"token {self.config['api_key']}:{secret_val}"
        self._client = httpx.AsyncClient(
            base_url=base.rstrip("/"),
            headers=headers,
            timeout=httpx.Timeout(self.config.get("timeout_seconds", 30.0), connect=5.0),
        )

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def healthcheck(self) -> bool:
        if self._client is None:
            return False
        try:
            r = await self._client.get("/api/method/frappe.auth.get_logged_user")
            return r.status_code < 400
        except httpx.HTTPError:
            return False

    # -- helpers --------------------------------------------------------------

    async def _resource(self, doctype: str, *, fields: list[str], limit: int = 0) -> list[dict[str, Any]]:
        if self._client is None:
            raise ConnectorConfigError("Connecteur ERPNext non connecté.")
        params = {"fields": json.dumps(fields), "limit_page_length": limit}
        try:
            r = await self._client.get(f"/api/resource/{doctype}", params=params)
        except httpx.HTTPError as exc:
            raise ConnectorConnectionError(f"ERPNext {doctype} échec: {exc}") from exc
        if r.status_code >= 400:
            raise ConnectorConnectionError(f"ERPNext {doctype} -> {r.status_code}: {r.text[:200]}")
        return r.json().get("data", [])

    def _canon(self, row: dict[str, Any], fallback: dict[str, str]) -> dict[str, Any]:
        if self.mapping is not None:
            return self.mapping.apply(row)
        return {c: row.get(s) for c, s in fallback.items() if row.get(s) is not None}

    # -- interface unique -----------------------------------------------------

    async def list_employees(self, **filters: Any) -> list[Employee]:
        async with self._instrument("list_employees"):
            rows = await self._resource(
                self._doctype("employee", "Employee"),
                fields=["name", "employee_name", "designation", "company_email"],
            )
            fb = {"id_externe": "name", "nom_complet": "employee_name", "poste": "designation", "email": "company_email"}
            return [Employee(**self._canon(r, fb)) for r in rows]

    async def list_invoices(self, **filters: Any) -> list[Invoice]:
        async with self._instrument("list_invoices"):
            rows = await self._resource(
                self._doctype("invoice", "Sales Invoice"),
                fields=["name", "customer_name", "posting_date", "net_total", "grand_total"],
            )
            return [self._invoice_from_row(r) for r in rows]

    async def read_invoice(self, invoice_id: str) -> Invoice:
        async with self._instrument("read_invoice"):
            if self._client is None:
                raise ConnectorConfigError("Connecteur ERPNext non connecté.")
            doctype = self._doctype("invoice", "Sales Invoice")
            r = await self._client.get(f"/api/resource/{doctype}/{invoice_id}")
            if r.status_code >= 400:
                raise ConnectorConfigError(f"Facture ERPNext {invoice_id!r}: {r.status_code}")
            return self._invoice_from_row(r.json().get("data", {}))

    def _invoice_from_row(self, r: dict[str, Any]) -> Invoice:
        if self.mapping is not None:
            return Invoice(**self.mapping.apply(r))
        return Invoice(
            id_externe=str(r.get("name")),
            numero=str(r.get("name")),
            tiers=r.get("customer_name") or "inconnu",
            date_emission=r.get("posting_date"),
            montant_ht_xaf=r.get("net_total") or 0,
            montant_ttc_xaf=r.get("grand_total") or 0,
        )

    async def push_journal_entry(self, entry: JournalEntry) -> str:
        async with self._instrument("push_journal_entry"):
            if self._client is None:
                raise ConnectorConfigError("Connecteur ERPNext non connecté.")
            accounts = [
                {"account": l.compte, "debit_in_account_currency": float(l.debit_xaf),
                 "credit_in_account_currency": float(l.credit_xaf), "user_remark": l.libelle}
                for l in entry.lignes
            ]
            doc = {"doctype": "Journal Entry", "posting_date": entry.date_ecriture.isoformat(),
                   "user_remark": entry.libelle, "accounts": accounts}
            r = await self._client.post("/api/resource/Journal Entry", json=doc)
            if r.status_code >= 400:
                raise ConnectorConnectionError(f"ERPNext push -> {r.status_code}: {r.text[:200]}")
            return str(r.json().get("data", {}).get("name", ""))

    async def list_bank_transactions(self, **filters: Any) -> list[BankTransaction]:
        async with self._instrument("list_bank_transactions"):
            rows = await self._resource(
                self._doctype("bank_transaction", "Bank Transaction"),
                fields=["name", "date", "description", "deposit", "withdrawal"],
            )
            out: list[BankTransaction] = []
            for r in rows:
                if self.mapping is not None:
                    out.append(BankTransaction(**self.mapping.apply(r)))
                    continue
                deposit = r.get("deposit") or 0
                withdrawal = r.get("withdrawal") or 0
                montant = deposit - withdrawal
                out.append(BankTransaction(
                    id_externe=str(r.get("name")), date_operation=r.get("date"),
                    libelle=r.get("description") or "", montant_xaf=montant,
                    sens="credit" if montant >= 0 else "debit", canal="bank",
                ))
            return out
