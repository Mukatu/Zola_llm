"""Connecteur SOAP / WSDL générique (V2.2 §2.4).

**Squelette fonctionnel à dépendance optionnelle.** SOAP est rare dans le
contexte cible (PME CG) et la lib `zeep` n'est volontairement PAS ajoutée aux
dépendances par défaut pour garder l'image légère (décision documentée dans
`docs/CONNECTOR_FRAMEWORK_ROADMAP.md` §1 jalon C). Activation :

    pip install zeep

Sans `zeep`, toute opération lève `ConnectorConfigError` explicite (jamais un
ImportError opaque).

Config attendue :
    {
      "wsdl": "https://systeme.client.cg/service?wsdl",
      "operations": {"employees": "GetEmployees", "invoices": "GetInvoices"}
    }
"""

from __future__ import annotations

import asyncio
from typing import Any

from zolaos.connectors.base import (
    ConnectorConfigError,
    HRConnector,
    InvoiceConnector,
)
from zolaos.connectors.models import Employee, Invoice
from zolaos.core.logging import get_logger

_log = get_logger("zolaos.connectors.generic_soap")


def _require_zeep() -> Any:
    try:
        import zeep  # type: ignore
    except ImportError as exc:  # pragma: no cover - chemin sans dépendance
        raise ConnectorConfigError(
            "Connecteur SOAP indisponible : le paquet optionnel 'zeep' n'est pas installé. "
            "Installer avec `pip install zeep` pour activer ce connecteur."
        ) from exc
    return zeep


class GenericSoapConnector(HRConnector, InvoiceConnector):
    """Connecteur SOAP générique (nécessite le paquet optionnel `zeep`)."""

    name = "generic_soap"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._client: Any = None

    async def connect(self) -> None:
        await self.auth.prepare()
        zeep = _require_zeep()
        wsdl = self.config.get("wsdl")
        if not wsdl:
            raise ConnectorConfigError("config['wsdl'] obligatoire pour le connecteur SOAP.")
        self._client = await asyncio.to_thread(zeep.Client, wsdl)

    def _operation(self, key: str) -> str:
        op = self.config.get("operations", {}).get(key)
        if not op:
            raise ConnectorConfigError(f"opération SOAP {key!r} non configurée.")
        return op

    async def _call(self, op: str, **kwargs: Any) -> Any:
        if self._client is None:
            raise ConnectorConfigError("Connecteur SOAP non connecté (appeler connect()).")
        service_op = getattr(self._client.service, op)
        return await asyncio.to_thread(lambda: service_op(**kwargs))

    def _canon(self, row: dict[str, Any]) -> dict[str, Any]:
        return self.mapping.apply(row) if self.mapping is not None else dict(row)

    async def list_employees(self, **filters: Any) -> list[Employee]:
        async with self._instrument("list_employees"):
            rows = await self._call(self._operation("employees"), **filters)
            return [Employee(**self._canon(dict(r))) for r in rows]

    async def list_invoices(self, **filters: Any) -> list[Invoice]:
        async with self._instrument("list_invoices"):
            rows = await self._call(self._operation("invoices"), **filters)
            return [Invoice(**self._canon(dict(r))) for r in rows]

    async def read_invoice(self, invoice_id: str) -> Invoice:
        async with self._instrument("read_invoice"):
            row = await self._call(self._operation("invoice_by_id"), id=invoice_id)
            return Invoice(**self._canon(dict(row)))
