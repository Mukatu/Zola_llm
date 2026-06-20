# SDK Custom — écrire un connecteur maison

Brancher un système interne (ERP maison, base propriétaire, API spécifique) sur
ZolaOS sans modifier le cœur. Référence : cahier des charges V2.2 §2.4.

## 1. Choisir ses capacités

Hériter uniquement des mixins correspondant aux capacités réellement supportées :

| Mixin | Méthode(s) à implémenter |
|-------|--------------------------|
| `HRConnector` | `list_employees()` |
| `InvoiceConnector` | `read_invoice()`, `list_invoices()` |
| `JournalConnector` | `push_journal_entry()` |
| `FinanceConnector` | `list_bank_transactions()` |
| `AccountingConnector` | = `InvoiceConnector` + `JournalConnector` |
| `CustomConnector` | = HR + Accounting + Finance (tout) |

Toute méthode abstraite héritée mais non implémentée → `TypeError` à
l'instanciation (garde-fou Python). Les capacités sont **dérivées
automatiquement** des mixins (`MonConnector.capabilities()`).

## 2. Squelette

```python
from zolaos.connectors.base import HRConnector, InvoiceConnector
from zolaos.connectors.models import Employee, Invoice

class MonErpConnector(HRConnector, InvoiceConnector):
    name = "mon_erp"

    async def connect(self) -> None:          # optionnel (auth, session)
        await self.auth.prepare()
        # ... ouvrir la connexion à partir de self.config ...

    async def healthcheck(self) -> bool:      # optionnel
        return True

    async def close(self) -> None:            # optionnel
        ...

    async def list_employees(self, **filters):
        async with self._instrument("list_employees"):
            rows = ...  # appel système maison
            data = [self.mapping.apply(r) if self.mapping else r for r in rows]
            return [Employee(**d) for d in data]

    async def read_invoice(self, invoice_id: str):
        ...

    async def list_invoices(self, **filters):
        ...
```

## 3. Enregistrer et utiliser

```python
from zolaos.connectors.registry import register_connector, create_connector

register_connector("mon_erp", MonErpConnector)

conn = create_connector({
    "type": "mon_erp",
    "config": {"host": "10.0.0.5", "port": 8069},
    "auth": {"type": "basic", "username": "svc", "password": "***"},
    "mapping": "chemin/vers/mapping.yaml",
})
async with conn:
    employes = await conn.list_employees()
```

## 4. Règles

- **Secrets** : jamais en clair ; le registry enveloppe les valeurs sensibles en
  `SecretStr`. Préférer des secrets injectés par l'environnement.
- **Lecture seule par défaut** ; toute écriture (`push_journal_entry`) doit être
  explicite et auditée.
- **Multi-pays** : renseigner `country` via le mapping (`country_default`), jamais
  en dur.
- **Instrumentation** : envelopper chaque opération dans `async with
  self._instrument("<op>")` pour les métriques/audit.

Voir `example.py` pour un connecteur minimal fonctionnel.
