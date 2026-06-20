"""SDK Custom — connecteurs maison (V2.2 §2.4).

Un client qui possède un système interne (ERP maison, base propriétaire…)
implémente un connecteur en sous-classant `CustomConnector` et en fournissant
5-6 méthodes au plus, puis l'enregistre :

    from zolaos.connectors.custom_sdk import CustomConnector
    from zolaos.connectors.registry import register_connector

    class MonErpConnector(CustomConnector):
        name = "mon_erp"
        async def connect(self): ...           # ouverture session
        async def list_employees(self, **f): ...# capacité RH
        async def list_invoices(self, **f): ...  # capacité factures
        async def read_invoice(self, i): ...
        async def list_bank_transactions(self, **f): ...

    register_connector("mon_erp", MonErpConnector)

ZolaOS le découvre ensuite via `create_connector({"type": "mon_erp", ...})`.

Voir `README.md` (ce dossier) pour le guide complet et `example.py` pour un
connecteur minimal fonctionnel.
"""

from __future__ import annotations

from zolaos.connectors.base import (
    AccountingConnector,
    FinanceConnector,
    HRConnector,
)


class CustomConnector(HRConnector, AccountingConnector, FinanceConnector):
    """Base pratique pour un connecteur maison.

    Hérite de toutes les capacités : un connecteur réel n'implémente que les
    méthodes pertinentes ; les autres restent abstraites (Python lèvera une
    `TypeError` à l'instanciation si une capacité héritée n'est pas fournie).

    Pour ne supporter qu'une partie des capacités, hériter directement des
    mixins voulus (`HRConnector`, `InvoiceConnector`, `JournalConnector`,
    `FinanceConnector`) plutôt que de `CustomConnector`.
    """

    name = "custom"


__all__ = ["CustomConnector"]
