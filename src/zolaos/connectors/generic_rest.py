"""Connecteur REST générique configurable (V2.2 §2.4, §4.4 — livré en standard).

Branche n'importe quelle API REST (style OpenAPI) via configuration déclarative :
endpoints, pagination, chemin des items, auth pluggable, mapping.

Config attendue :
    {
      "base_url": "https://erp.client.cg/api",
      "endpoints": {
        "employees": "/employees",
        "invoices": "/invoices",
        "invoice_by_id": "/invoices/{id}",
        "bank_transactions": "/bank/transactions",
        "journal": "/journal/entries",
        "health": "/health"
      },
      "pagination": {"type": "page", "page_param": "page", "size_param": "page_size",
                     "size": 100, "items_path": "data", "max_pages": 100},
      "response_id_path": "id",
      "timeout_seconds": 30
    }
"""

from __future__ import annotations

from typing import Any

import httpx

from zolaos.connectors.base import (
    AccountingConnector,
    ConnectorConfigError,
    ConnectorConnectionError,
    FinanceConnector,
    HRConnector,
)
from zolaos.connectors.models import BankTransaction, Employee, Invoice, JournalEntry
from zolaos.core.logging import get_logger

_log = get_logger("zolaos.connectors.generic_rest")


class GenericRestConnector(HRConnector, AccountingConnector, FinanceConnector):
    """Connecteur REST piloté par configuration."""

    name = "generic_rest"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._client: httpx.AsyncClient | None = None

    # -- cycle de vie ---------------------------------------------------------

    async def connect(self) -> None:
        await self.auth.prepare()  # OAuth2 : fetch token
        base_url = self.config.get("base_url")
        if not base_url:
            raise ConnectorConfigError("config['base_url'] obligatoire.")
        headers: dict[str, str] = {"Accept": "application/json"}
        self.auth.apply_headers(headers)
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            headers=headers,
            timeout=httpx.Timeout(self.config.get("timeout_seconds", 30.0), connect=5.0),
            **self.auth.httpx_kwargs(),
        )

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def healthcheck(self) -> bool:
        ep = self.config.get("endpoints", {}).get("health")
        if not ep or self._client is None:
            return self._client is not None
        try:
            r = await self._client.get(ep)
            return r.status_code < 400
        except httpx.HTTPError:
            return False

    # -- helpers HTTP ---------------------------------------------------------

    def _endpoint(self, key: str) -> str:
        ep = self.config.get("endpoints", {}).get(key)
        if not ep:
            raise ConnectorConfigError(f"endpoint {key!r} non configuré.")
        return ep

    @staticmethod
    def _dig(payload: Any, path: str | None) -> Any:
        if not path:
            return payload
        cur = payload
        for part in path.split("."):
            cur = cur[part]
        return cur

    async def _get(self, endpoint: str, params: dict[str, Any] | None = None) -> Any:
        if self._client is None:
            raise ConnectorConfigError("Connecteur non connecté (appeler connect()).")
        try:
            r = await self._client.get(endpoint, params=params)
        except httpx.HTTPError as exc:
            raise ConnectorConnectionError(f"GET {endpoint} échec: {exc}") from exc
        if r.status_code >= 400:
            raise ConnectorConnectionError(f"GET {endpoint} -> {r.status_code}: {r.text[:200]}")
        return r.json()

    async def _list(self, endpoint_key: str) -> list[dict[str, Any]]:
        endpoint = self._endpoint(endpoint_key)
        pg = self.config.get("pagination", {"type": "none"})
        items_path = pg.get("items_path")
        if pg.get("type") != "page":
            return list(self._dig(await self._get(endpoint), items_path))
        out: list[dict[str, Any]] = []
        page = pg.get("start", 1)
        for _ in range(pg.get("max_pages", 100)):
            params = {pg.get("page_param", "page"): page, pg.get("size_param", "page_size"): pg.get("size", 100)}
            batch = list(self._dig(await self._get(endpoint, params), items_path))
            if not batch:
                break
            out.extend(batch)
            if len(batch) < pg.get("size", 100):
                break
            page += 1
        return out

    def _canon(self, row: dict[str, Any]) -> dict[str, Any]:
        return self.mapping.apply(row) if self.mapping is not None else dict(row)

    # -- interface unique -----------------------------------------------------

    async def list_employees(self, **filters: Any) -> list[Employee]:
        async with self._instrument("list_employees"):
            return [Employee(**self._canon(r)) for r in await self._list("employees")]

    async def list_invoices(self, **filters: Any) -> list[Invoice]:
        async with self._instrument("list_invoices"):
            return [Invoice(**self._canon(r)) for r in await self._list("invoices")]

    async def read_invoice(self, invoice_id: str) -> Invoice:
        async with self._instrument("read_invoice"):
            ep = self._endpoint("invoice_by_id").format(id=invoice_id)
            return Invoice(**self._canon(await self._get(ep)))

    async def list_bank_transactions(self, **filters: Any) -> list[BankTransaction]:
        async with self._instrument("list_bank_transactions"):
            return [BankTransaction(**self._canon(r)) for r in await self._list("bank_transactions")]

    async def push_journal_entry(self, entry: JournalEntry) -> str:
        if self._client is None:
            raise ConnectorConfigError("Connecteur non connecté (appeler connect()).")
        ep = self._endpoint("journal")
        async with self._instrument("push_journal_entry"):
            try:
                r = await self._client.post(ep, json=entry.model_dump(mode="json"))
            except httpx.HTTPError as exc:
                raise ConnectorConnectionError(f"POST {ep} échec: {exc}") from exc
            if r.status_code >= 400:
                raise ConnectorConnectionError(f"POST {ep} -> {r.status_code}: {r.text[:200]}")
            return str(self._dig(r.json(), self.config.get("response_id_path", "id")))
