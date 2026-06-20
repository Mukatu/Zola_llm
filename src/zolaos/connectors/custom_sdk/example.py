"""Exemple minimal de connecteur maison (SDK Custom).

Connecteur in-memory de démonstration : il ne contacte aucun système externe,
sert de gabarit copiable et de support de test. Implémente la capacité RH
uniquement (hérite de `HRConnector`, pas de `CustomConnector`, pour ne déclarer
que `list_employees`).
"""

from __future__ import annotations

from typing import Any

from zolaos.connectors.base import HRConnector
from zolaos.connectors.models import Employee


class ExampleMemoryConnector(HRConnector):
    """Connecteur d'exemple : renvoie des salariés depuis `config['rows']`."""

    name = "example_memory"

    async def list_employees(self, **filters: Any) -> list[Employee]:
        async with self._instrument("list_employees"):
            rows = self.config.get("rows", [])
            canon = (
                [self.mapping.apply(r) for r in rows] if self.mapping is not None else rows
            )
            return [Employee(**r) for r in canon]
