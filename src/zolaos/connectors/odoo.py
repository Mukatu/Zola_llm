"""Connecteur Odoo (V2.2 §2.4, §4.4 — connecteur standard).

Odoo expose une API XML-RPC (`/xmlrpc/2/common` + `/xmlrpc/2/object`).
Implémentation fonctionnelle via `xmlrpc.client` (stdlib, aucune dépendance
ajoutée), appels synchrones déportés dans un thread.

Config attendue :
    {
      "url": "https://odoo.client.cg",
      "db": "client_prod",
      "username": "integration@client.cg",
      "password": SecretStr("..."),
      "models": {                      # surcharge optionnelle des modèles Odoo
        "employee": "hr.employee",
        "invoice": "account.move",
        "bank_line": "account.bank.statement.line"
      }
    }

Le mapping déclaratif (`self.mapping`) traduit les champs Odoo → canonique ;
sinon des champs par défaut Odoo sont tentés.
"""

from __future__ import annotations

import asyncio
from typing import Any
from xmlrpc.client import ServerProxy

from pydantic import SecretStr

from zolaos.connectors.base import (
    AccountingConnector,
    ConnectorAuthError,
    ConnectorConfigError,
    ConnectorConnectionError,
    FinanceConnector,
    HRConnector,
)
from zolaos.connectors.models import BankTransaction, Employee, Invoice, JournalEntry
from zolaos.core.logging import get_logger

_log = get_logger("zolaos.connectors.odoo")


class OdooConnector(HRConnector, AccountingConnector, FinanceConnector):
    """Connecteur Odoo XML-RPC."""

    name = "odoo"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._uid: int | None = None
        self._models: ServerProxy | None = None

    def _pwd(self) -> str:
        pwd = self.config.get("password")
        return pwd.get_secret_value() if isinstance(pwd, SecretStr) else str(pwd or "")

    def _model(self, key: str, default: str) -> str:
        return self.config.get("models", {}).get(key, default)

    # -- cycle de vie ---------------------------------------------------------

    def _authenticate_sync(self) -> int:
        url = self.config.get("url")
        if not url or not self.config.get("db") or not self.config.get("username"):
            raise ConnectorConfigError("config url/db/username obligatoires pour Odoo.")
        common = ServerProxy(f"{url.rstrip('/')}/xmlrpc/2/common", allow_none=True)
        uid = common.authenticate(self.config["db"], self.config["username"], self._pwd(), {})
        if not uid:
            raise ConnectorAuthError("Authentification Odoo refusée (uid vide).")
        return int(uid)

    async def connect(self) -> None:
        await self.auth.prepare()
        self._uid = await asyncio.to_thread(self._authenticate_sync)
        url = self.config["url"].rstrip("/")
        self._models = ServerProxy(f"{url}/xmlrpc/2/object", allow_none=True)

    async def healthcheck(self) -> bool:
        try:
            if self._uid is None:
                await self.connect()
            return self._uid is not None
        except Exception:  # noqa: BLE001
            return False

    # -- exécution ------------------------------------------------------------

    def _execute_kw_sync(self, model: str, method: str, args: list[Any], kw: dict[str, Any]) -> Any:
        if self._models is None or self._uid is None:
            raise ConnectorConfigError("Connecteur Odoo non connecté.")
        try:
            return self._models.execute_kw(
                self.config["db"], self._uid, self._pwd(), model, method, args, kw
            )
        except Exception as exc:  # noqa: BLE001  (xmlrpc Fault, socket…)
            raise ConnectorConnectionError(f"Odoo {model}.{method} échec: {exc}") from exc

    async def _search_read(self, model: str, domain: list[Any], fields: list[str]) -> list[dict[str, Any]]:
        return await asyncio.to_thread(
            self._execute_kw_sync, model, "search_read", [domain], {"fields": fields}
        )

    def _canon(self, row: dict[str, Any], fallback: dict[str, str]) -> dict[str, Any]:
        if self.mapping is not None:
            return self.mapping.apply(row)
        return {canon: row.get(src) for canon, src in fallback.items() if row.get(src) is not None}

    # -- interface unique -----------------------------------------------------

    async def list_employees(self, **filters: Any) -> list[Employee]:
        async with self._instrument("list_employees"):
            rows = await self._search_read(
                self._model("employee", "hr.employee"), [], ["id", "name", "job_title", "work_email"]
            )
            fb = {"id_externe": "id", "nom_complet": "name", "poste": "job_title", "email": "work_email"}
            return [Employee(**{**self._canon(r, fb), "id_externe": str(r.get("id"))}) for r in rows]

    async def list_invoices(self, **filters: Any) -> list[Invoice]:
        async with self._instrument("list_invoices"):
            model = self._model("invoice", "account.move")
            rows = await self._search_read(
                model, [["move_type", "=", "out_invoice"]],
                ["id", "name", "partner_id", "invoice_date", "amount_untaxed", "amount_total"],
            )
            return [self._invoice_from_row(r) for r in rows]

    async def read_invoice(self, invoice_id: str) -> Invoice:
        async with self._instrument("read_invoice"):
            model = self._model("invoice", "account.move")
            rows = await self._search_read(
                model, [["id", "=", int(invoice_id)]],
                ["id", "name", "partner_id", "invoice_date", "amount_untaxed", "amount_total"],
            )
            if not rows:
                raise ConnectorConfigError(f"Facture Odoo {invoice_id!r} introuvable.")
            return self._invoice_from_row(rows[0])

    def _invoice_from_row(self, r: dict[str, Any]) -> Invoice:
        if self.mapping is not None:
            return Invoice(**self.mapping.apply(r))
        partner = r.get("partner_id")
        tiers = partner[1] if isinstance(partner, list) and len(partner) > 1 else str(partner)
        return Invoice(
            id_externe=str(r.get("id")),
            numero=r.get("name") or str(r.get("id")),
            tiers=tiers or "inconnu",
            date_emission=r.get("invoice_date"),
            montant_ht_xaf=r.get("amount_untaxed") or 0,
            montant_ttc_xaf=r.get("amount_total") or 0,
        )

    async def push_journal_entry(self, entry: JournalEntry) -> str:
        async with self._instrument("push_journal_entry"):
            model = self._model("invoice", "account.move")
            line_ids = [
                (0, 0, {"account_id": l.compte, "name": l.libelle,
                        "debit": float(l.debit_xaf), "credit": float(l.credit_xaf)})
                for l in entry.lignes
            ]
            vals = {"ref": entry.reference or entry.libelle, "date": entry.date_ecriture.isoformat(),
                    "line_ids": line_ids}
            new_id = await asyncio.to_thread(self._execute_kw_sync, model, "create", [vals], {})
            return str(new_id)

    async def list_bank_transactions(self, **filters: Any) -> list[BankTransaction]:
        async with self._instrument("list_bank_transactions"):
            model = self._model("bank_line", "account.bank.statement.line")
            rows = await self._search_read(model, [], ["id", "date", "payment_ref", "amount"])
            out: list[BankTransaction] = []
            for r in rows:
                if self.mapping is not None:
                    out.append(BankTransaction(**self.mapping.apply(r)))
                    continue
                amount = r.get("amount") or 0
                out.append(BankTransaction(
                    id_externe=str(r.get("id")), date_operation=r.get("date"),
                    libelle=r.get("payment_ref") or "", montant_xaf=amount,
                    sens="credit" if amount >= 0 else "debit", canal="bank",
                ))
            return out
