# Connector Framework — guide d'usage

Couche d'abstraction unique pour brancher ZolaOS à des systèmes externes (ERP,
compta, banque, paie, systèmes maison). Cahier des charges : `ZOLAOS_MASTER_PLAN_V2.md`
§2.4. Feuille de route d'implémentation : [`CONNECTOR_FRAMEWORK_ROADMAP.md`](./CONNECTOR_FRAMEWORK_ROADMAP.md).

## Principes

- **Interface unique** : `list_employees()`, `read_invoice()`, `list_invoices()`,
  `push_journal_entry()`, `list_bank_transactions()`.
- **Capacités déclarées par héritage** de mixins ; dérivées via `Connector.capabilities()`.
- **Modèles canoniques** normalisés (`Employee`, `Invoice`, `JournalEntry`,
  `BankTransaction`) avec `country` systématique (multi-pays par tagging).
- **Auth pluggable** : API key, OAuth2 (client credentials), Basic, certificat
  client, IP allowlist (entrée). Secrets toujours en `SecretStr`.
- **Mapping déclaratif YAML** : `champ_source → champ_canonique`, sans code.
- **Instrumentation** : chaque opération est mesurée (métriques Prometheus
  `zolaos_connector_calls_total` / `_duration_seconds`).
- Disponible dans **les deux profils** (`box` ET `cortex`).

## Connecteurs disponibles

| Type (`type`) | Capacités | Statut |
|---------------|-----------|--------|
| `csv_excel` | RH, factures, banque (lecture) + export écritures CSV | ✅ complet |
| `generic_rest` | RH, factures, banque, écritures | ✅ complet |
| `generic_sql` | RH, factures, banque (lecture seule, SELECT paramétrés) | ✅ complet |
| `webhook` | ingestion entrante (IP allowlist + signature HMAC) | ✅ complet |
| `odoo` | RH, factures, banque, écritures (XML-RPC) | ✅ complet |
| `erpnext` | RH, factures, banque, écritures (REST) | ✅ complet |
| `generic_soap` | RH, factures | ⚙️ dépend du paquet optionnel `zeep` |
| `sage` | RH, factures, banque | ⚙️ mode `api`, ou `odbc` via `pyodbc` optionnel |
| *(custom)* | au choix | SDK : voir `connectors/custom_sdk/README.md` |

## Usage déclaratif

```python
from zolaos.connectors.registry import create_connector

conn = create_connector({
    "type": "generic_rest",
    "config": {
        "base_url": "https://erp.client.cg/api",
        "endpoints": {"employees": "/employees", "invoices": "/invoices",
                       "invoice_by_id": "/invoices/{id}", "journal": "/journal"},
        "pagination": {"type": "page", "items_path": "data", "size": 100},
    },
    "auth": {"type": "api_key", "key": "***", "header_name": "X-API-Key"},
    "mapping": "src/zolaos/connectors/mappings/example_employee.yaml",
})

async with conn:
    employes = await conn.list_employees()
    facture = await conn.read_invoice("INV-2026-001")
```

## Mapping YAML

```yaml
entity: employee
country_default: cg
fields:
  id_externe:       { from: id }
  nom_complet:      { from: full_name, transform: strip }
  email:            { from: contact.email, transform: lower }
  salaire_base_xaf: { from: base_salary, transform: to_decimal }
```

Transformations disponibles : `strip`, `upper`, `lower`, `to_decimal`, `to_int`,
`to_date`, `to_bool`. Chemins source pointés (`contact.email`) supportés.

## Connecteur maison (SDK Custom)

Voir [`../src/zolaos/connectors/custom_sdk/README.md`](../src/zolaos/connectors/custom_sdk/README.md).

## Hors périmètre (par phase)

- Branchement des **sous-agents ERP** (RH/Finance/Compta) sur les connecteurs → jalon ERP suivant (Phase 4.1-4.3).
- Connecteurs **Mobile Money** (MTN MoMo / Airtel) → Phase 6 Fintech.
- Dépendances `zeep` / `pyodbc` → optionnelles, non installées par défaut.
